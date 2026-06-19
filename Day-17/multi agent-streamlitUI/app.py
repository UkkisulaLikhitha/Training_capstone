import streamlit as st
import operator
import os
import time
from typing import Annotated, List, TypedDict, Literal
from pydantic import BaseModel, Field

st.set_page_config(
    page_title="VoiceEmo · Realtime Pipeline",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
:root {
  --bg:#0a0a12; --surface:#12121f; --card:#1a1a2e; --border:#2a2a45;
  --accent:#7c3aed; --accent2:#a78bfa; --green:#10b981; --warn:#f59e0b;
  --text:#e2e8f0; --muted:#64748b;
}
html,body,[data-testid="stAppViewContainer"]{background:var(--bg)!important;font-family:'Space Grotesk',sans-serif!important;color:var(--text)!important;}
[data-testid="stSidebar"]{background:var(--surface)!important;border-right:1px solid var(--border)!important;}
h1,h2,h3{font-family:'Space Grotesk',sans-serif!important;color:var(--text)!important;}
.main-title{font-size:2.2rem;font-weight:700;background:linear-gradient(135deg,#a78bfa,#7c3aed);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.stButton>button{background:linear-gradient(135deg,#7c3aed,#5b21b6)!important;color:white!important;border:none!important;border-radius:8px!important;font-weight:600!important;}
.stButton>button:hover{background:linear-gradient(135deg,#6d28d9,#4c1d95)!important;box-shadow:0 4px 20px rgba(124,58,237,0.4)!important;}
.stTextArea textarea{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:8px!important;color:var(--text)!important;}
.stTextInput input{background:var(--card)!important;border:1px solid var(--border)!important;color:var(--text)!important;}

.pipeline-step{display:flex;align-items:flex-start;gap:12px;padding:12px 16px;border-radius:10px;margin-bottom:8px;border:1px solid var(--border);background:rgba(255,255,255,0.02);transition:all 0.3s;}
.pipeline-step.active{border-color:var(--accent);background:rgba(124,58,237,0.08);box-shadow:0 0 12px rgba(124,58,237,0.15);}
.pipeline-step.done{border-color:var(--green);background:rgba(16,185,129,0.05);}
.pipeline-step.error{border-color:#ef4444;background:rgba(239,68,68,0.05);}
.step-icon{font-size:1.3rem;min-width:28px;}
.step-body{flex:1;}
.step-title{font-size:0.8rem;font-family:'Space Mono',monospace;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:3px;}
.step-title.supervisor{color:#a78bfa;}
.step-title.researcher{color:#34d399;}
.step-title.writer{color:#fbbf24;}
.step-msg{font-size:0.82rem;color:var(--muted);}
.step-status{font-size:0.7rem;font-family:'Space Mono',monospace;padding:2px 8px;border-radius:10px;}
.status-running{background:rgba(124,58,237,0.2);color:#a78bfa;animation:blink 1s infinite;}
.status-done{background:rgba(16,185,129,0.2);color:#34d399;}
.status-wait{background:rgba(100,116,139,0.15);color:#64748b;}
@keyframes blink{0%,100%{opacity:1;}50%{opacity:0.5;}}

.result-box{background:linear-gradient(135deg,rgba(124,58,237,0.08),rgba(124,58,237,0.02));border:1px solid rgba(124,58,237,0.25);border-radius:12px;padding:1.5rem;margin-top:1rem;}
.token-bar{height:8px;border-radius:4px;background:var(--border);overflow:hidden;margin-top:4px;}
.token-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,#10b981,#f59e0b,#ef4444);transition:width 0.3s;}
.metric-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px 16px;text-align:center;}
.metric-val{font-size:1.4rem;font-weight:700;color:var(--accent2);font-family:'Space Mono',monospace;}
.metric-lbl{font-size:0.65rem;color:var(--muted);text-transform:uppercase;letter-spacing:0.1em;font-family:'Space Mono',monospace;}
.divider{border:none;border-top:1px solid var(--border);margin:1.2rem 0;}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──
with st.sidebar:
    st.markdown('<div class="main-title" style="font-size:1.4rem;">🎙️ VoiceEmo</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.65rem;font-family:Space Mono;color:#4a5568;margin-bottom:1.2rem;">REALTIME EMOTION PIPELINE</div>', unsafe_allow_html=True)

    st.markdown("### 🔑 API Keys")
    groq_key   = st.text_input("Groq API Key",   type="password", placeholder="gsk_...")
    tavily_key = st.text_input("Tavily API Key",  type="password", placeholder="tvly-dev-...")

    st.markdown('<hr style="border-color:#2a2a45;margin:1rem 0;">', unsafe_allow_html=True)
    st.markdown("### ⚙️ Settings")
    model_choice = st.selectbox("Model", [
        "llama-3.1-8b-instant",        # fastest, fewest tokens
        "llama-3.3-70b-versatile",     # best quality
        "llama-3.1-70b-versatile",
        "gemma2-9b-it",
    ], index=0, help="llama-3.1-8b-instant uses ~5x fewer tokens — great for free tier")

    st.markdown('<hr style="border-color:#2a2a45;margin:1rem 0;">', unsafe_allow_html=True)
    st.markdown("""<div style="font-size:0.68rem;font-family:Space Mono;color:#4a5568;line-height:1.9;">
    🔁 LangGraph pipeline<br>
    🧠 Supervisor → Researcher → Writer<br>
    🔍 Tavily web search<br>
    ⚡ Groq inference<br>
    💡 Free tier: ~20 runs/day
    </div>""", unsafe_allow_html=True)

# ── Header ──
st.markdown('<div class="main-title">Voice Emotion Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div style="color:#64748b;font-family:Space Mono;font-size:0.85rem;margin-bottom:1.5rem;">End-to-end realtime pipeline · LangGraph + Groq + Tavily</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
for col, icon, title, desc in [
    (c1, "🔬", "RESEARCHER", "Searches Tavily for vocal biomarkers & emotion-speech science"),
    (c2, "🧠", "SUPERVISOR", "Routes between agents until the report is ready"),
    (c3, "✍️", "WRITER",     "Produces structured emotion report with confidence scores"),
]:
    col.markdown(f"""<div class="metric-card" style="text-align:left;">
    <div style="font-size:1.2rem;margin-bottom:4px;">{icon}</div>
    <div style="font-size:0.65rem;font-family:Space Mono;color:#a78bfa;letter-spacing:0.1em;">{title}</div>
    <div style="font-size:0.8rem;color:#64748b;margin-top:4px;">{desc}</div>
    </div>""", unsafe_allow_html=True)

st.markdown('<hr style="border-color:#2a2a45;margin:1.2rem 0;">', unsafe_allow_html=True)

# ── Input ──
st.markdown("### 🎤 Voice / Speech Input")
input_mode = st.radio("", ["Vocal Description", "Speech Transcript", "Scenario"], horizontal=True, label_visibility="collapsed")

examples = {
    "Vocal Description": "Speaker's voice is trembling slightly, pitch is elevated, speech rate is fast with frequent mid-sentence pauses. Volume drops sharply at end of sentences. Occasional voice cracks.",
    "Speech Transcript": "I... I don't know what to do anymore. [long pause] Everything just feels so overwhelming. I'm fine, really. [voice breaks] No, actually I'm not fine at all.",
    "Scenario": "Customer service call: caller starts calm, tone shifts to clipped short answers when told the refund is denied, then goes completely silent for 8 seconds before saying 'fine' in a flat voice."
}

col_input, col_ex = st.columns([5, 1])
with col_ex:
    if st.button("📋 Example", use_container_width=True):
        st.session_state["load_example"] = input_mode

default_val = examples.get(st.session_state.get("load_example", ""), "")
if st.session_state.get("load_example"):
    st.session_state.pop("load_example")

voice_input = st.text_area("", height=110,
    value=default_val,
    placeholder=f"Enter {input_mode.lower()} here...",
    label_visibility="collapsed")

run_btn = st.button("🚀  Analyse Emotion — Start Pipeline", use_container_width=True)

# ── LangGraph types ──
class AgentState(TypedDict):
    task: str
    research_notes: Annotated[List[str], operator.add]
    draft: str
    next_node: str
    retry_count: int
    revision_feedback: str

class Router(BaseModel):
    next_worker: Literal["researcher", "writer", "FINISH"] = Field(description="Next node")
    instructions: str = Field(description="Instructions for the worker")
    is_critical: bool = Field(default=False)

def build_graph(groq_api_key, tavily_api_key, model):
    from langchain_groq import ChatGroq
    from langchain_community.tools.tavily_search import TavilySearchResults
    from langgraph.graph import StateGraph, END

    os.environ["GROQ_API_KEY"]   = groq_api_key
    os.environ["TAVILY_API_KEY"] = tavily_api_key

    llm         = ChatGroq(model_name=model, temperature=0, groq_api_key=groq_api_key, max_tokens=800)
    search_tool = TavilySearchResults(k=2, tavily_api_key=tavily_api_key)

    def researcher(state: AgentState):
        # Compact query to save tokens
        query = f"voice emotion detection acoustic features {state['task'][:80]}"
        results = search_tool.invoke(query)
        # Truncate results to save tokens
        note = str(results)[:1200]
        return {"research_notes": [note], "retry_count": state["retry_count"] + 1}

    def writer(state: AgentState):
        # Compact context — truncate research to 600 chars
        context = "\n".join(state["research_notes"])[:600]
        prompt = f"""Analyse this voice input for emotions. Be concise.

INPUT ({input_mode}): {state['task'][:300]}

RESEARCH: {context}

Respond with:
## Primary Emotion
Name + confidence %

## Secondary Emotions
Bullet list with %

## Acoustic Evidence
Key vocal cues observed

## Intensity
Low/Moderate/High/Extreme + 1 sentence why

## Psychological Profile
2-3 sentences

## Recommended Response
2-3 actionable tips"""
        res = llm.invoke(prompt)
        return {"draft": res.content}

    def supervisor(state: AgentState):
        structured_llm = llm.with_structured_output(Router)
        has_notes = len(state["research_notes"]) > 0
        has_draft = bool(state.get("draft", ""))
        # Minimal prompt to save tokens
        prompt = f"""Pipeline supervisor. notes={len(state['research_notes'])}, draft={'yes' if has_draft else 'no'}.
Rule: no notes→researcher. notes+no draft→writer. draft→FINISH."""
        decision = structured_llm.invoke(prompt)
        return {"next_node": decision.next_worker, "revision_feedback": decision.instructions}

    builder = StateGraph(AgentState)
    builder.add_node("supervisor", supervisor)
    builder.add_node("researcher", researcher)
    builder.add_node("writer",     writer)
    builder.set_entry_point("supervisor")
    builder.add_conditional_edges("supervisor", lambda x: x["next_node"],
        {"researcher": "researcher", "writer": "writer", "FINISH": END})
    builder.add_edge("researcher", "supervisor")
    builder.add_edge("writer",     "supervisor")
    return builder.compile()

# ── Pipeline execution ──
if run_btn:
    if not groq_key or not tavily_key:
        st.error("⚠️ Enter both API keys in the sidebar.")
        st.stop()
    if not voice_input.strip():
        st.error("⚠️ Please enter a voice description.")
        st.stop()

    st.markdown('<hr style="border-color:#2a2a45;margin:1.2rem 0;">', unsafe_allow_html=True)
    st.markdown("### ⚡ Live Pipeline")

    # Pipeline step UI
    steps_placeholder = st.empty()
    metrics_placeholder = st.empty()
    result_placeholder = st.empty()

    steps = [
        {"id": "supervisor_1", "role": "supervisor", "icon": "🧠", "title": "Supervisor",  "msg": "Evaluating task...",        "status": "wait"},
        {"id": "researcher",   "role": "researcher", "icon": "🔬", "title": "Researcher",  "msg": "Searching Tavily...",       "status": "wait"},
        {"id": "supervisor_2", "role": "supervisor", "icon": "🧠", "title": "Supervisor",  "msg": "Reviewing research...",     "status": "wait"},
        {"id": "writer",       "role": "writer",     "icon": "✍️", "title": "Writer",      "msg": "Generating report...",      "status": "wait"},
        {"id": "supervisor_3", "role": "supervisor", "icon": "🧠", "title": "Supervisor",  "msg": "Final check → FINISH",      "status": "wait"},
    ]

    def render_steps(active_idx=None, done_up_to=None, msgs=None):
        html = ""
        for i, s in enumerate(steps):
            if done_up_to is not None and i < done_up_to:
                cls = "done"; status_cls = "status-done"; status_txt = "✓ done"
            elif i == active_idx:
                cls = "active"; status_cls = "status-running"; status_txt = "● running"
            else:
                cls = ""; status_cls = "status-wait"; status_txt = "○ waiting"
            msg = (msgs or {}).get(s["id"], s["msg"])
            html += f"""<div class="pipeline-step {cls}">
              <div class="step-icon">{s['icon']}</div>
              <div class="step-body">
                <div class="step-title {s['role']}">{s['title']}</div>
                <div class="step-msg">{msg}</div>
              </div>
              <div class="step-status {status_cls}">{status_txt}</div>
            </div>"""
        steps_placeholder.markdown(html, unsafe_allow_html=True)

    render_steps(active_idx=0)

    final_draft = ""
    research_note = ""
    step_count = 0
    start_time = time.time()
    step_msgs = {}

    try:
        graph = build_graph(groq_key, tavily_key, model_choice)
        initial = {
            "task": voice_input, "research_notes": [],
            "draft": "", "next_node": "", "retry_count": 0, "revision_feedback": ""
        }
        config = {"configurable": {"thread_id": f"ve_{int(time.time())}"}}

        for event in graph.stream(initial, config, stream_mode="values"):
            step_count += 1

            if "next_node" in event and event["next_node"]:
                node = event["next_node"]
                fb   = event.get("revision_feedback", "")[:60]

                if node == "researcher":
                    render_steps(active_idx=1, done_up_to=1)
                    step_msgs["supervisor_1"] = f"Routing → Researcher | {fb}"
                elif node == "writer":
                    render_steps(active_idx=3, done_up_to=3)
                    step_msgs["supervisor_2"] = f"Routing → Writer | {fb}"
                elif node == "FINISH":
                    render_steps(active_idx=4, done_up_to=4)
                    step_msgs["supervisor_3"] = "Pipeline complete → FINISH"

                render_steps(active_idx=None, done_up_to=step_count, msgs=step_msgs)

            if "research_notes" in event and event["research_notes"]:
                research_note = event["research_notes"][-1]
                preview = research_note[:80].replace("\n", " ")
                step_msgs["researcher"] = f"✓ Found: {preview}..."
                render_steps(active_idx=2, done_up_to=2, msgs=step_msgs)

            if "draft" in event and event["draft"]:
                final_draft = event["draft"]
                step_msgs["writer"] = f"✓ Report written — {len(final_draft)} chars"
                render_steps(active_idx=None, done_up_to=5, msgs=step_msgs)

        elapsed = round(time.time() - start_time, 1)

        # Metrics row
        metrics_placeholder.markdown(f"""
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:1rem 0;">
          <div class="metric-card"><div class="metric-val">{step_count}</div><div class="metric-lbl">Steps</div></div>
          <div class="metric-card"><div class="metric-val">{elapsed}s</div><div class="metric-lbl">Duration</div></div>
          <div class="metric-card"><div class="metric-val">{len(final_draft)}</div><div class="metric-lbl">Report chars</div></div>
          <div class="metric-card"><div class="metric-val" style="color:#34d399;">✓</div><div class="metric-lbl">Status</div></div>
        </div>
        """, unsafe_allow_html=True)

        if final_draft:
            result_placeholder.markdown(f"""
            <div class="result-box">
            {"final_draft_placeholder"}
            </div>
            """.replace("final_draft_placeholder", ""), unsafe_allow_html=True)

            st.markdown('<div class="result-box">', unsafe_allow_html=True)
            st.markdown("### 🧬 Emotion Analysis Report")
            st.markdown(final_draft)
            st.markdown('</div>', unsafe_allow_html=True)

            if research_note:
                with st.expander("📚 Raw Research Data", expanded=False):
                    st.text(research_note[:1000])

            st.download_button("⬇️ Download Report", data=final_draft,
                               file_name="emotion_report.md", mime="text/markdown")
        else:
            st.warning("No report generated. Try again in a moment.")

    except Exception as e:
        err = str(e)
        if "429" in err or "rate_limit" in err.lower():
            # Extract wait time if present
            wait_hint = ""
            if "try again in" in err.lower():
                try:
                    wait_hint = err.split("try again in")[1].split(".")[0].strip()
                except:
                    wait_hint = "a few minutes"
            st.error(f"⏳ **Rate limit hit.** {'Wait ' + wait_hint + ' then try again.' if wait_hint else 'Please wait a few minutes.'}")
            st.info("💡 **Tips:** Switch to `llama-3.1-8b-instant` in the sidebar (uses 5x fewer tokens). Or use a second Groq API key.")
        else:
            st.error(f"Pipeline error: {err}")
            st.code(err)

st.markdown('<hr style="border-color:#2a2a45;margin:1.5rem 0;">', unsafe_allow_html=True)
st.markdown('<div style="font-size:0.7rem;font-family:Space Mono;color:#4a5568;">⚡ LangGraph · 🧠 Groq · 🔍 Tavily · 🎙️ VoiceEmo v2</div>', unsafe_allow_html=True)
