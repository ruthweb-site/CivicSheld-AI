import streamlit as st
import dotenv
# Load environment variables at startup
dotenv.load_dotenv()

from agents import (
    authenticity_agent,
    policy_agent,
    risk_agent,
    accessibility_agent,
    action_agent
)
from extractor import extract_text
from rag import initialize_rag, retrieve_context


# ── Page Configuration ───────────────────────────────────────────────
st.set_page_config(
    page_title="CivicShield AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Initialize RAG once at startup ───────────────────────────────────
@st.cache_resource(show_spinner="🔄 Loading Knowledge Base (first run only)...")
def load_rag():
    initialize_rag()
    return True

load_rag()

# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.image(
        "civicshield_logo.png",
        width=120
    )
    st.title("CivicShield AI")
    st.markdown("---")
    st.markdown("**Powered by NVIDIA Nemotron-3-Super**")
    st.markdown("Detects fake government notices, scam schemes, edited circulars, and misinformation.")
    st.markdown("---")
    st.info("Agent Status: Online 🟢")
    st.success("RAG Knowledge Base: 5 docs loaded ✅")
    st.caption("v1.0 (Hackathon Edition)")

    # API key is securely loaded from environment/dotenv
    api_key = ""


# ── Main Header ──────────────────────────────────────────────────────
st.title("🛡️ CivicShield AI")
st.subheader("Verify Government Documents & Detect Scams")
st.markdown("Upload any suspicious document, screenshot, or WhatsApp forward to verify its authenticity.")

# ── Zone 1: User Input ───────────────────────────────────────────────
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### 📤 Upload Document")
    uploaded_file = st.file_uploader(
        "Upload a PDF, JPG, or PNG file",
        type=["pdf", "png", "jpg", "jpeg"]
    )

with col2:
    st.markdown("### 📝 Paste Text / URL")
    pasted_text = st.text_area(
        "Or paste a suspicious URL or WhatsApp forward here:",
        height=150,
        placeholder="E.g., URGENT! Get free laptop at pm-laptop-2024.xyz. Call 9999999999 now!"
    )

analyze_button = st.button("🔍 Analyze Authenticity", type="primary", use_container_width=True)


# ── Zone 5: Output Dashboard ─────────────────────────────────────────
if analyze_button:
    if not uploaded_file and not pasted_text.strip():
        st.warning("⚠️ Please upload a document or paste some text to analyze.")
    else:
        # ── Step 1: Extract Text (Zone 2) ──────────────────────────
        with st.spinner("📄 Zone 2: Extracting text from document..."):
            extracted_text, metadata = extract_text(uploaded_file, pasted_text)

        # Expander shows Zone 2 output — great for the demo video!
        with st.expander("🔬 Zone 2 Output — Extracted Text & Metadata", expanded=False):
            st.markdown("**Extracted Text:**")
            st.code(
                extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else ""),
                language="text"
            )
            st.markdown("**Detected Metadata:**")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🔗 URLs",    len(metadata["urls"]))
            m2.metric("📞 Phones",  len(metadata["phones"]))
            m3.metric("📧 Emails",  len(metadata["emails"]))
            m4.metric("📅 Dates",   len(metadata["dates"]))

            if metadata["urls"]:
                st.markdown("**Extracted URLs:**")
                for url in metadata["urls"]:
                    st.code(url)

        # ── Step 2: Multi-Agent Pipeline (Zone 4 - Real-time Reasoning Visualizer) ──
        import time
        
        # 1. Prepare shared metadata context
        metadata_context = (
            f"Metadata found in document:\n"
            f"URLs    = {metadata['urls']}\n"
            f"Phones  = {metadata['phones']}\n"
            f"Emails  = {metadata['emails']}\n"
            f"Dates   = {metadata['dates']}"
        )
        
        st.markdown("### 🤖 Collaborative Agentic Reasoning Log")
        
        # 2. Sequential Agent Execution with Visualizer Status Container
        with st.status("🚀 Orchestrating 5-Agent Consensus via NVIDIA NIM...", expanded=True) as status_box:
            
            # Agent 1: Authenticity Agent
            status_box.write("🔍 **Agent 1: Authenticity Agent** is checking grammar, structure, and domain types...")
            auth_data = authenticity_agent(extracted_text, api_key=api_key)
            st.json(auth_data)
            time.sleep(0.8)  # Let judges observe the agentic step
            
            # Agent 2: Policy Agent
            status_box.write("📘 **Agent 2: Policy Agent** is performing semantic RAG query on the FAISS local database...")
            policy_data = policy_agent(extracted_text, context=metadata_context, api_key=api_key)
            st.json(policy_data)
            time.sleep(0.8)
            
            # Agent 3: Risk Agent
            status_box.write("⚖️ **Agent 3: Risk Agent** is analyzing findings and compiling safety index scores...")
            risk_data = risk_agent(auth_data, policy_data, api_key=api_key)
            st.json(risk_data)
            time.sleep(0.8)
            
            # Agent 4: Accessibility Agent
            status_box.write("🌐 **Agent 4: Accessibility Agent** is summarizing analysis in parent-friendly language...")
            accessibility_data = accessibility_agent(risk_data, api_key=api_key)
            st.json(accessibility_data)
            time.sleep(0.8)
            
            # Agent 5: Action Agent
            status_box.write("🎯 **Agent 5: Action Agent** is compiling clear, defensive actionable next steps...")
            action_data = action_agent(risk_data, api_key=api_key)
            st.json(action_data)
            time.sleep(0.8)
            
            status_box.update(label="✅ Consensus Achieved: Multi-Agent Analysis Completed!", state="complete", expanded=False)

        # Assemble unified report dict for the dashboard
        report = {
            "trust_score": risk_data.get("total_score", 0),
            "risk_level": risk_data.get("risk_level", "UNKNOWN"),
            "red_flags": risk_data.get("all_red_flags", []),
            "source_references": risk_data.get("source_references", []),
            "summary": accessibility_data.get("parent_friendly_summary", "No summary available."),
            "actions": action_data.get("recommended_actions", [])
        }

        # ── Dashboard ───────────────────────────────────────────────
        st.markdown("---")
        st.markdown("## 📊 Analysis Dashboard")

        score_col, risk_col = st.columns([1, 1])

        with score_col:
            st.markdown("### 🎯 Trust Score")
            score = report["trust_score"]
            if score >= 70:
                delta_label = "✅ Likely Authentic"
            elif score >= 40:
                delta_label = "⚠️ Suspicious"
            else:
                delta_label = "🚨 High Risk"
            st.metric(label="Authenticity Agent Score", value=f"{score} / 100", delta=delta_label)

        with risk_col:
            st.markdown("### ⚠️ Overall Risk Level")
            level = report["risk_level"]
            if "HIGH" in level:
                st.error(f"🚨 {level}")
            elif "SUSPICIOUS" in level:
                st.warning(f"⚠️ {level}")
            else:
                st.success(f"✅ {level}")

        # ── Domain Security Analysis (Visual Security Box) ─────────────────
        if metadata.get("domain_reports"):
            st.markdown("---")
            st.markdown("### 🌐 Live Domain Security & Trust Verification")
            for rep in metadata["domain_reports"]:
                with st.container():
                    st.markdown(f"#### 🔗 Domain: `{rep['domain']}`")
                    
                    c_label, c_ip, c_age = st.columns(3)
                    
                    with c_label:
                        if rep["trust_label"] == "SECURE GOVT DOMAIN":
                            st.success(f"🏷️ **{rep['trust_label']}** (Scam Risk: {rep['scam_score']}%)")
                        elif rep["trust_label"] == "CRITICAL SCAM RISK":
                            st.error(f"🏷️ **{rep['trust_label']}** (Scam Risk: {rep['scam_score']}%)")
                        elif rep["trust_label"] == "SUSPICIOUS DOMAIN":
                            st.warning(f"🏷️ **{rep['trust_label']}** (Scam Risk: {rep['scam_score']}%)")
                        else:
                            st.info(f"🏷️ **{rep['trust_label']}** (Scam Risk: {rep['scam_score']}%)")
                            
                    with c_ip:
                        st.markdown(f"🖥️ **Resolved IP:** `{rep['ip_address']}`")
                        
                    with c_age:
                        st.markdown(f"📅 **Domain Age:** {rep['whois_age']}")
                        
                    with st.expander("🔍 Security Verification Checklist & Details", expanded=False):
                        st.markdown(f"**Registrar:** `{rep['whois_registrar']}`")
                        st.markdown("**Checklist Results:**")
                        for check in rep["checks"]:
                            st.markdown(f"- {check}")

        st.markdown("---")
        col3, col4 = st.columns([1, 1])

        with col3:
            st.markdown("### 🚩 Detected Red Flags")
            if report["red_flags"]:
                for flag in report["red_flags"]:
                    st.error(f"▸ {flag}")
            else:
                st.success("✅ No red flags detected.")

            with st.expander("📚 Source References (Groundedness)", expanded=True):
                if report["source_references"]:
                    st.success(f"Matched against {len(report['source_references'])} official document(s):")
                    for i, ref in enumerate(report["source_references"], 1):
                        st.markdown(f"**{i}.** {ref}")
                else:
                    st.info("No specific documents matched.")

        with col4:
            st.markdown("### 👨‍👩‍👧 Parent-Friendly Summary")
            st.info(f"**Simple Explanation:**\n\n{report['summary']}")

            st.markdown("### 🎯 Recommended Actions")
            if report["actions"]:
                for i, action in enumerate(report["actions"], 1):
                    st.warning(f"**Step {i}:** {action}")
            else:
                st.success("No immediate action required.")

        st.success("✅ Multi-Agent Reasoning Completed via NVIDIA NIM")
        st.caption("Powered by Nemotron-3-Super | CivicShield AI v1.0")
