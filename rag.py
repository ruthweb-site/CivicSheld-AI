"""
Zone 3: Knowledge & Verification Layer
RAG engine using FAISS + sentence-transformers.
Loads all .txt files from the knowledge_base/ folder,
chunks them, embeds them, and provides a retrieve_context() function.
"""

import os
import json
import pickle
import numpy as np
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────
KB_DIR       = Path(__file__).parent / "knowledge_base"
CACHE_FILE   = Path(__file__).parent / "knowledge_base" / "rag_cache.pkl"
CHUNK_SIZE   = 300   # words per chunk
CHUNK_OVERLAP = 50   # word overlap between chunks
TOP_K        = 3     # number of chunks to retrieve

# ── Lazy globals (loaded once per session) ───────────────────────────
_index   = None
_chunks  = []
_model   = None


# ── Step 1: Load & Chunk Documents ───────────────────────────────────
def _load_documents() -> list[dict]:
    """Load every .txt file from knowledge_base/ and split into chunks."""
    docs = []
    for txt_file in KB_DIR.glob("*.txt"):
        text = txt_file.read_text(encoding="utf-8")
        words = text.split()
        # Sliding window chunking
        for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
            chunk_words = words[i : i + CHUNK_SIZE]
            if len(chunk_words) < 20:   # skip tiny tail chunks
                continue
            docs.append({
                "text":   " ".join(chunk_words),
                "source": txt_file.stem.replace("_", " ").title(),
                "file":   txt_file.name,
            })
    return docs


# ── Step 2: Embed & Index ─────────────────────────────────────────────
def _build_index(chunks: list[dict]):
    """Embed all chunks and build a FAISS index. Cache to disk."""
    import faiss
    from sentence_transformers import SentenceTransformer

    global _model
    print("[RAG] Loading embedding model (first run only, may take ~30s)...")
    _model = SentenceTransformer("all-MiniLM-L6-v2")   # small, fast, offline

    texts = [c["text"] for c in chunks]
    embeddings = _model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    embeddings = embeddings.astype("float32")

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    # Cache to disk so next startup is instant
    with open(CACHE_FILE, "wb") as f:
        pickle.dump({"chunks": chunks, "embeddings": embeddings}, f)

    print(f"[RAG] Index built: {len(chunks)} chunks indexed from {KB_DIR}")
    return index


# ── Step 3: Load from Cache (fast path) ──────────────────────────────
def _load_from_cache():
    """Load pre-built index from disk cache."""
    import faiss
    from sentence_transformers import SentenceTransformer

    global _model
    with open(CACHE_FILE, "rb") as f:
        data = pickle.load(f)

    chunks     = data["chunks"]
    embeddings = data["embeddings"].astype("float32")
    _model     = SentenceTransformer("all-MiniLM-L6-v2")

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    return index, chunks


# ── Step 4: Initialize (called once at app startup) ───────────────────
def initialize_rag():
    """
    Build or load the FAISS index.
    Call this once from app.py before any retrieve_context() calls.
    """
    global _index, _chunks

    if _index is not None:
        return  # Already initialized

    chunks = _load_documents()
    if not chunks:
        print("[RAG] WARNING: No documents found in knowledge_base/. RAG disabled.")
        return

    # Use cache if it exists AND knowledge base hasn't changed
    if CACHE_FILE.exists():
        try:
            _index, _chunks = _load_from_cache()
            # Validate chunk count matches (cache stale check)
            if len(_chunks) == len(chunks):
                print(f"[RAG] Loaded from cache: {len(_chunks)} chunks")
                return
        except Exception:
            pass  # Cache corrupt — rebuild below

    _chunks = chunks
    _index  = _build_index(_chunks)


# ── Step 5: Retrieve Context ──────────────────────────────────────────
def retrieve_context(query: str, top_k: int = TOP_K) -> tuple[str, list[str]]:
    """
    Given a query string, returns:
    - context_text: the top-K chunks joined as a string (for the agent prompt)
    - source_names: list of source document names (for Groundedness panel)
    """
    global _index, _chunks, _model

    if _index is None or not _chunks:
        return "No official documents available for verification.", []

    query_embedding = _model.encode([query], convert_to_numpy=True).astype("float32")
    distances, indices = _index.search(query_embedding, min(top_k, len(_chunks)))

    results      = []
    source_names = []

    for idx, dist in zip(indices[0], distances[0]):
        if idx == -1:
            continue
        chunk  = _chunks[idx]
        # Only include chunks that are at least somewhat relevant (L2 distance < 3.0)
        if dist < 3.0:
            results.append(f"[Source: {chunk['source']}]\n{chunk['text']}")
            source_names.append(chunk["source"])

    if not results:
        return "No closely matching official documents found.", []

    context_text = "\n\n---\n\n".join(results)
    # Deduplicate source names while preserving order
    seen = set()
    unique_sources = []
    for s in source_names:
        if s not in seen:
            seen.add(s)
            unique_sources.append(s)

    return context_text, unique_sources
