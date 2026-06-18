import streamlit as st
import time

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="Agentic AI Pipeline",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------- CUSTOM CSS ----------------
st.markdown("""
<style>

/* Background */
.stApp {
    background: linear-gradient(135deg, #0f172a, #1e1b4b, #0f172a);
    color: white;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #0b1220;
}

/* Title */
.title {
    font-size: 34px;
    font-weight: 700;
    text-align: center;
    margin-bottom: 0px;
}

/* Subtitle */
.subtitle {
    text-align: center;
    color: #a5b4fc;
    margin-bottom: 30px;
}

/* Input box */
.stTextArea textarea {
    background-color: #111827;
    color: white;
    border-radius: 12px;
    border: 1px solid #374151;
}

/* Button */
.stButton button {
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
    color: white;
    border-radius: 10px;
    padding: 10px 20px;
    border: none;
    font-weight: 600;
}

/* Cards */
.card {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 20px;
    border-radius: 16px;
    box-shadow: 0 8px 20px rgba(0,0,0,0.3);
}

/* Status pills */
.badge {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
}

.thinking { background: #f59e0b; color: black; }
.waiting { background: #6b7280; }
.done { background: #22c55e; color: black; }

.pipeline {
    display: flex;
    gap: 10px;
    justify-content: center;
    margin-top: 20px;
}

</style>
""", unsafe_allow_html=True)

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.title("🔑 Groq API Key")
    api_key = st.text_input("Enter API Key", type="password")

    st.markdown("---")

    st.title("🧠 Model")
    model = st.selectbox(
        "Choose Model",
        ["llama-3.3-70b-versatile", "mixtral-8x7b", "gemma-7b"]
    )

    st.markdown("---")
    st.caption("⚡ Agentic AI System v1")

# ---------------- HEADER ----------------
st.markdown("<div class='title'>🧠 Agentic AI Pipeline</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Planner • Executor • Validator — powered by Groq</div>", unsafe_allow_html=True)

# ---------------- INPUT ----------------
query = st.text_area("Give more info about your task", height=120)

col1, col2 = st.columns([1,1])

run = col1.button("🚀 Run Agents")
clear = col2.button("🧹 Clear")

if clear:
    st.rerun()

# ---------------- PIPELINE UI ----------------
def card(title, status, content):
    st.markdown(f"""
    <div class="card">
        <h3>{title}</h3>
        <span class="badge {status}">{status.upper()}</span>
        <p style="margin-top:10px">{content}</p>
    </div>
    """, unsafe_allow_html=True)

# ---------------- SIMULATED FLOW ----------------
if run and query:

    # STEP 1: Planner
    with st.spinner("Planner thinking..."):
        time.sleep(1)
        plan = [
            "Break task into subtasks",
            "Identify required tools",
            "Define execution steps"
        ]

    # STEP 2: Executor
    with st.spinner("Executor running..."):
        time.sleep(1)
        results = [
            "Fetched knowledge base",
            "Searched web sources",
            "Extracted structured info"
        ]

    # STEP 3: Validator
    with st.spinner("Validator checking..."):
        time.sleep(1)
        verdict = "Output is consistent and valid."

    # ---------------- PIPELINE DISPLAY ----------------
    st.markdown("## 🔷 Pipeline Status")

    c1, c2, c3 = st.columns(3)

    with c1:
        card("Planner Agent", "done", "<br>".join(plan))

    with c2:
        card("Executor Agent", "done", "<br>".join(results))

    with c3:
        card("Validator Agent", "done", verdict)

    # ---------------- FINAL OUTPUT ----------------
    st.markdown("---")
    st.markdown("## 🏁 Final Output")
    st.success("Agent pipeline executed successfully!")