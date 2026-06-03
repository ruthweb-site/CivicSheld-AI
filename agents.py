import json
import os
from openai import OpenAI
from rag import retrieve_context
import dotenv

# Load environment variables from a .env file (if present)
dotenv.load_dotenv()

# Retrieve API key from environment variable
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")


def call_nim(prompt: str, system_msg: str, api_key: str = "") -> dict:
    """Helper function to call NVIDIA NIM and enforce JSON output."""
    # Use hardcoded key if no key passed from the UI
    resolved_key = api_key if api_key else NVIDIA_API_KEY
    if not resolved_key:
        return None # Fallback to mock data if no real key is provided
        
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=resolved_key
    )
    
    try:
        completion = client.chat.completions.create(
            model="meta/llama-3.1-8b-instruct",
            messages=[
                {"role": "system", "content": system_msg + " You must respond ONLY with valid JSON. Do not include markdown blocks or any other text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            top_p=0.7,
            max_tokens=1024,
        )
        content = completion.choices[0].message.content
        
        # Clean up Markdown formatting if the model accidentally included it
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].strip()
            
        return json.loads(content)
    except Exception as e:
        print(f"Error calling NIM or parsing JSON: {e}")
        return None

def authenticity_agent(text: str, api_key: str = "") -> dict:
    """Agent 1: Checks for fake URLs, domains, and grammar."""
    sys_msg = "You are an AI Fraud detection agent. Analyze the text for suspicious URLs (e.g. .xyz instead of .gov.in), unrealistic promises, and grammar errors. Output a JSON containing: 'score' (0-100, where 100 is highly authentic) and 'red_flags' (a list of string explanations)."
    
    result = call_nim(f"Analyze this document text:\n{text}", sys_msg, api_key)
    
    if result: return result
    
    # Mock Fallback
    return {
        "score": 32,
        "red_flags": [
            "Non-Government URL: The domain is not an official '.gov.in' domain.",
            "Suspicious Promises: The offer promises unrealistic benefits to create urgency."
        ]
    }

def policy_agent(text: str, context: str = "", api_key: str = "") -> dict:
    """Agent 2: Compares text against verified RAG context from knowledge_base/."""
    sys_msg = (
        "You are a Policy Verification agent. Compare the document text against the provided official context retrieved from verified government sources.\n"
        "Look ONLY for actual, active contradictions or mismatches (such as fake deadlines, fake eligibility criteria, fake contact details, or fake domains claiming to be official).\n"
        "CRITICAL RULES:\n"
        "1. If the input text is a short, simple, benign status update, receipt, confirmation message, or OTP notification that does NOT make any active policy claims, you MUST set 'policy_mismatch' to false and keep 'red_flags' empty.\n"
        "2. Do NOT flag a mismatch just because a short text lacks details like a deadline or full eligibility guidelines. Missing details in a short status alert is normal and expected, not a policy mismatch.\n"
        "Output JSON with: 'policy_mismatch' (boolean) and 'red_flags' (list of strings explaining the actual mismatches found)."
    )

    # ── Pull real context from RAG ──
    rag_context, source_names = retrieve_context(text)

    # Merge RAG context with metadata context from extractor
    full_context = f"{rag_context}\n\nAdditional metadata:\n{context}" if context else rag_context

    prompt = f"Official Verified Context:\n{full_context}\n\nDocument Text to Verify:\n{text}"
    result = call_nim(prompt, sys_msg, api_key)

    if result:
        result["source_references"] = source_names if source_names else ["Official Domain Guidelines"]
        # If the NIM model returned policy_mismatch but there are no actual red flags, override it to False
        if not result.get("red_flags"):
            result["policy_mismatch"] = False
        return result

    # Mock Fallback
    # Smart fallback: if the input is very short and doesn't contain standard scam indicators, don't flag as mismatch
    is_short_alert = len(text.split()) < 30 and not any(k in text.lower() for k in ["urgent", "free", "winner", "laptop", ".xyz", "cash"])
    return {
        "policy_mismatch": False if is_short_alert else True,
        "red_flags": [] if is_short_alert else ["Deadline Mismatch: The stated deadline contradicts official government records."],
        "source_references": source_names if source_names else ["National Scholarship Portal Guidelines", "Official Domain Registry"]
    }

def risk_agent(auth_data: dict, policy_data: dict, api_key: str = "") -> dict:
    """Agent 3: Assesses overall risk based on previous agents."""
    score = auth_data.get("score", 100)
    policy_mismatch = policy_data.get("policy_mismatch", False)
    
    # Smart classification logic based on both structural authenticity score & policy mismatch findings
    if score >= 70:
        if policy_mismatch:
            risk_level = "SUSPICIOUS"  # Structure is authentic, but there is a specific mismatch
        else:
            risk_level = "SAFE"
    elif score >= 40:
        risk_level = "SUSPICIOUS"
    else:
        risk_level = "HIGH RISK / SCAM LIKELY"
        
    all_red_flags = auth_data.get("red_flags", []) + policy_data.get("red_flags", [])
    
    return {
        "risk_level": risk_level,
        "total_score": score,
        "all_red_flags": all_red_flags,
        "source_references": policy_data.get("source_references", [])
    }

def accessibility_agent(risk_data: dict, api_key: str = "") -> dict:
    """Agent 4: Translates complex findings into simple language."""
    sys_msg = "You are a helpful accessibility agent. Translate the provided risk data into a very simple, 2-sentence explanation that a non-technical parent would understand. Output JSON with a single key: 'parent_friendly_summary'."
    
    result = call_nim(f"Risk Data:\n{json.dumps(risk_data)}", sys_msg, api_key)
    
    if result: return result
    
    # Mock Fallback
    if risk_data["risk_level"] == "HIGH RISK / SCAM LIKELY":
        summary = "This notice is likely fake because the website link does not belong to the real government, and the deadline does not match official records."
    else:
        summary = "This document appears to be authentic based on our checks."
        
    return {"parent_friendly_summary": summary}

def action_agent(risk_data: dict, api_key: str = "") -> dict:
    """Agent 5: Recommends actionable next steps."""
    sys_msg = "You are a civic tech agent. Based on the risk level, suggest 3-4 highly actionable next steps for the user (e.g., report to cyber cell, do not click links). Output JSON with a single key: 'recommended_actions' (a list of strings)."
    
    result = call_nim(f"Risk Data:\n{json.dumps(risk_data)}", sys_msg, api_key)
    
    if result: return result
    
    # Mock Fallback
    if risk_data["risk_level"] == "HIGH RISK / SCAM LIKELY":
        actions = [
            "Do not share personal or banking information.",
            "Do not click on any links in the message.",
            "Report this to the Cyber Crime Portal (cybercrime.gov.in)."
        ]
    else:
        actions = ["You can safely proceed with this document."]
        
    return {"recommended_actions": actions}

def run_agentic_pipeline(text: str, context: str = "", api_key: str = "") -> dict:
    """
    Orchestrator that chains the 5 agents together.
    Returns a unified JSON payload for the UI.
    """
    print("Running Authenticity Agent...")
    auth_data = authenticity_agent(text, api_key)
    
    print("Running Policy Agent...")
    policy_data = policy_agent(text, context, api_key)
    
    print("Running Risk Agent...")
    risk_data = risk_agent(auth_data, policy_data, api_key)
    
    print("Running Accessibility Agent...")
    accessibility_data = accessibility_agent(risk_data, api_key)
    
    print("Running Action Agent...")
    action_data = action_agent(risk_data, api_key)
    
    # Combine everything for the Streamlit UI
    final_report = {
        "trust_score": risk_data.get("total_score", 0),
        "risk_level": risk_data.get("risk_level", "UNKNOWN"),
        "red_flags": risk_data.get("all_red_flags", []),
        "source_references": risk_data.get("source_references", []),
        "summary": accessibility_data.get("parent_friendly_summary", "No summary available."),
        "actions": action_data.get("recommended_actions", [])
    }
    
    return final_report
