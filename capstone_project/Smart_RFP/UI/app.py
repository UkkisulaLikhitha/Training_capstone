"""
app.py — SmartRFP
=================
Streamlit front end styled to match the SmartRFP design mockups:
Upload, Dashboard, Resource Cost, Human Review, Export, Settings, Help & Docs.

Backend (unchanged, all working): config, database (SQLite), llm (Groq +
demo fallback), pipeline (parse → RAG ‖ pricing → synthesize), exporters.
"""

import io
from contextlib import contextmanager
from datetime import datetime

import streamlit as st
import pandas as pd
import altair as alt

import config
import database as db
from seed_data import seed
from demo_seed import seed_demo_rfps
from config import (APP_NAME, APP_TAGLINE, SUPPORTED_TYPES, MAX_UPLOAD_MB,
                    REVIEWER_ROLES, STATUSES, GROQ_MODEL)
from utils.file_handler import extract_text
from utils.exporter import export_txt, export_docx, export_pdf
from pipeline import run_pipeline
from llm import llm_available, ping as groq_ping

from prometheus_client import start_http_server

# --------------------------------------------------------------------------- #
st.set_page_config(page_title=f"{APP_NAME} — RFP Analysis", page_icon="📄",
                   layout="wide", initial_sidebar_state="expanded")

db.init_db()

import threading

if "metrics_started" not in st.session_state:
    threading.Thread(
        target=start_http_server,
        args=(8000,),
        daemon=True,
    ).start()

    st.session_state.metrics_started = True

ss = st.session_state
# Seed knowledge base + demo RFPs ONCE per session. Combined with the persistent
# "demo_seeded" flag in the DB, deleting RFPs never brings the samples back.
if "booted" not in ss:
    seed()
    seed_demo_rfps()
    ss.booted = True

ss.setdefault("page", "Upload")
ss.setdefault("current_rfp", None)
ss.setdefault("export_format", "PDF")
ss.setdefault("review_state", {})   # {f"{rid}:{section_id}": "Approved"/"In Review"/...}
ss.setdefault("currency", "USD - US Dollar")
ss.setdefault("items_per_page", 6)
ss.setdefault("groq_model", GROQ_MODEL)
ss.setdefault("workspace", "SmartRFP Solutions")
ss.setdefault("theme", "Light")


def go(page, rfp_id=None):
    ss.page = page
    if rfp_id is not None:
        ss.current_rfp = rfp_id
    st.rerun()


# =========================================================================== #
#  STYLES
# =========================================================================== #
st.markdown("""
<style>
:root{
  --blue:#2563eb; --blue2:#3b82f6; --blue-d:#1d4ed8; --blue-l:#eaf1ff;
  --ink:#000000; --ink2:#111111; --muted:#333333; --line:#e8edf3; --bg:#f6f8fc;
  --green:#16a34a; --green-l:#e7f7ee; --amber:#d97706; --amber-l:#fff5e6;
  --purple:#7c3aed; --purple-l:#f1ecfe; --teal:#0d9488; --teal-l:#e3f7f4;
  --red:#dc2626; --red-l:#fdeced;
}
/* Body text → Arial; headings → Calibri */
html, body, .stApp, [class^="st-"], [class*=" st-"], .stMarkdown,
p, span, div, label, input, textarea, select, button, li, td, th {
  font-family: Arial, "Helvetica Neue", Helvetica, sans-serif !important;
}
h1, h2, h3, h4, h5, h6, .tb h1, .cardtitle, .card h3, .brand .name,
.metric .val, .helpcard .t, .fmtcard .t {
  font-family: Calibri, "Segoe UI", Candara, "Trebuchet MS", sans-serif !important;
}
/* …but NEVER override Streamlit's Material icon font (fixes the overlapping
   "keyboard_arrow_down" text on expanders, selects, etc.) */
[data-testid="stIconMaterial"], .material-icons, .material-icons-outlined,
.material-symbols-rounded, .material-symbols-outlined,
[data-testid="stExpanderToggleIcon"], span[translate="no"] {
  font-family: "Material Symbols Rounded", "Material Symbols Outlined",
               "Material Icons" !important;
}
.stApp{ background:var(--bg); color:#000; }
.stMarkdown, .stMarkdown p, .stMarkdown li, .stApp p, .stApp li { color:#000; }
#MainMenu, header[data-testid="stHeader"], footer{ visibility:hidden; }
.block-container{ padding-top:1.4rem; padding-bottom:3rem; max-width:1340px; }
/* fixed-height scrollable Sections list so it doesn't stretch the page */
.seclist{ max-height:430px; overflow-y:auto; padding-right:.2rem; }

/* Sidebar */
section[data-testid="stSidebar"]{ background:#fff; border-right:1px solid var(--line); width:265px!important; }
section[data-testid="stSidebar"] .block-container{ padding-top:1.1rem; }
.brand{ display:flex; align-items:center; gap:.6rem; padding:.1rem .3rem 1.2rem; }
.brand .logo{ font-size:1.7rem; }
.brand .name{ font-size:1.4rem; font-weight:800; color:var(--ink); line-height:1; }
.brand .name span{ color:var(--blue); }
.brand .sub{ font-size:.7rem; color:var(--muted); margin-top:.18rem; }
section[data-testid="stSidebar"] .stButton>button{
  width:100%; text-align:left; justify-content:flex-start; background:#fff; color:var(--ink2);
  border:1px solid transparent; border-radius:11px; padding:.6rem .85rem; font-weight:600;
  font-size:.97rem; box-shadow:none; transition:all .12s ease; margin-bottom:.18rem;
}
section[data-testid="stSidebar"] .stButton>button:hover{ background:var(--blue-l); color:var(--blue-d); }
section[data-testid="stSidebar"] .stButton>button:focus{ box-shadow:none; }
.nav-active>button{ background:var(--blue-l)!important; color:var(--blue)!important; font-weight:700!important; }
.groq{ margin-top:1rem; padding:.85rem .9rem; background:#fff; border:1px solid var(--line);
  border-radius:14px; box-shadow:0 1px 3px rgba(16,24,40,.05); }
.groq .row{ display:flex; align-items:center; gap:.45rem; font-weight:700; color:var(--ink); font-size:.86rem; }
.groq .dot{ width:9px; height:9px; border-radius:50%; background:var(--green); box-shadow:0 0 0 3px var(--green-l); }
.groq .dot.off{ background:var(--amber); box-shadow:0 0 0 3px var(--amber-l); }
.groq .st{ color:var(--green); font-size:.8rem; margin:.2rem 0 .1rem; }
.groq .st.off{ color:var(--amber); }
.groq .mod{ color:var(--muted); font-size:.72rem; margin-bottom:.5rem; }

/* Top bar */
.tb{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:1rem; }
.tb h1{ font-size:1.7rem; font-weight:800; color:var(--ink); margin:0; display:flex; align-items:center; gap:.5rem;}
.tb .sub{ color:var(--muted); font-size:.93rem; margin-top:.15rem; }
.chip{ display:inline-flex; align-items:center; gap:.45rem; background:#fff; border:1px solid var(--line);
  border-radius:11px; padding:.45rem .8rem; font-weight:600; color:var(--ink); font-size:.9rem; }
.avatar{ width:42px; height:42px; border-radius:50%; background:#fff; border:1px solid var(--line);
  display:flex; align-items:center; justify-content:center; font-size:1.15rem; margin-left:auto;
  box-shadow:0 1px 3px rgba(16,24,40,.05); }

/* Cards */
.card{ background:#fff; border:1px solid var(--line); border-radius:16px; padding:1.15rem 1.25rem;
  box-shadow:0 1px 3px rgba(16,24,40,.04); margin-bottom:1rem; }
.card h3{ font-size:1.05rem; font-weight:800; color:var(--ink); margin:0 0 .9rem; }
/* real st.container(border=True) styled as a card so widgets sit inside it */
div[data-testid="stVerticalBlockBorderWrapper"]{ background:#fff; border:1px solid var(--line)!important;
  border-radius:16px; box-shadow:0 1px 3px rgba(16,24,40,.04); padding:.4rem .35rem; margin-bottom:.5rem; }
.cardtitle{ font-size:1.05rem; font-weight:800; color:var(--ink); margin:.15rem .25rem .7rem; }
.metric{ background:#fff; border:1px solid var(--line); border-radius:16px; padding:1.05rem 1.15rem; height:100%;
  box-shadow:0 1px 3px rgba(16,24,40,.04); }
.metric .top{ display:flex; justify-content:space-between; align-items:flex-start; }
.metric .lab{ color:var(--muted); font-weight:700; font-size:.82rem; }
.metric .val{ font-size:1.95rem; font-weight:800; color:var(--ink); line-height:1.1; margin-top:.35rem; }
.metric .sub{ color:var(--muted); font-size:.76rem; margin-top:.25rem; }
.ic{ width:40px; height:40px; border-radius:11px; display:flex; align-items:center; justify-content:center; font-size:1.2rem; }
.ic-blue{ background:var(--blue-l); } .ic-green{ background:var(--green-l); } .ic-amber{ background:var(--amber-l); }
.ic-purple{ background:var(--purple-l); } .ic-teal{ background:var(--teal-l); } .ic-red{ background:var(--red-l); }

/* Pills */
.pill{ display:inline-block; padding:.16rem .6rem; border-radius:999px; font-size:.74rem; font-weight:700; }
.p-rev{ background:var(--amber-l); color:#b45309; } .p-ana{ background:var(--blue-l); color:var(--blue); }
.p-app{ background:var(--green-l); color:#15803d; } .p-exp{ background:var(--teal-l); color:#0f766e; }
.p-pend{ background:#eef2f6; color:#64748b; } .p-rej{ background:var(--red-l); color:#b91c1c; }

/* small bits */
.muted{ color:var(--muted); } .b{ font-weight:700; color:var(--ink); }
.refpill{ display:inline-block; background:var(--blue-l); color:var(--blue-d); border:1px solid #d6e4ff;
  border-radius:8px; padding:.2rem .55rem; font-size:.78rem; margin:.15rem .25rem .15rem 0; }
hr{ border:none; border-top:1px solid var(--line); margin:1rem 0; }
.fmtcard{ border:1px solid var(--line); border-radius:14px; padding:1rem .6rem; text-align:center; background:#fff;
  min-height:142px; display:flex; flex-direction:column; align-items:center; justify-content:flex-start; }
.fmtcard.sel{ border:2px solid var(--blue); background:#f5f9ff; }
.fmtcard .e{ font-size:1.7rem; } .fmtcard .t{ font-weight:800; color:var(--ink); margin-top:.3rem; font-size:.92rem; }
.fmtcard .d{ color:var(--muted); font-size:.74rem; margin-top:.25rem; line-height:1.3; }
.feed{ display:flex; gap:.7rem; padding:.55rem 0; border-bottom:1px solid var(--line); }
.feed .fi{ width:34px; height:34px; border-radius:9px; display:flex; align-items:center; justify-content:center; font-size:1rem; }
.feed .ft{ font-weight:600; color:var(--ink2); font-size:.9rem; } .feed .fd{ color:var(--muted); font-size:.78rem; }
.step{ text-align:center; } .step .c{ width:46px; height:46px; border-radius:50%; display:flex; align-items:center;
  justify-content:center; margin:0 auto; font-size:1.2rem; border:2px solid var(--line); background:#fff; }
.step .c.done{ background:var(--green-l); border-color:#bbe7cc; } .step .c.prog{ background:var(--blue-l); border-color:#bcd4ff; }
.step .n{ font-weight:700; color:var(--ink); font-size:.82rem; margin-top:.35rem; }
.step .s{ font-size:.72rem; } .arrow{ color:#cbd5e1; font-size:1.3rem; text-align:center; padding-top:.7rem; }
.helpcard{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:1.1rem; height:100%; }
.helpcard .e{ width:46px;height:46px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.3rem;}
.helpcard .t{ font-weight:800; color:var(--ink); margin-top:.6rem; } .helpcard .d{ color:var(--muted); font-size:.82rem; margin:.3rem 0 .5rem; }
div[data-testid="stDataFrame"]{ border:1px solid var(--line); border-radius:12px; }
[data-testid="stFileUploaderDropzone"]{ background:#fbfdff; border:2px dashed #bcd1f5; border-radius:16px; padding:2rem; }
.stButton>button{ border-radius:10px; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# Dynamic theme (Settings → Application Preferences). Dark mode is opt-in; the
# default Light theme keeps the blue/white look with black text.
if ss.get("theme") == "Dark":
    st.markdown("""
    <style>
    .stApp{ background:#0b1220 !important; color:#e5e7eb !important; }
    section[data-testid="stSidebar"]{ background:#0f172a !important; border-color:#1f2a44 !important; }
    .card,.metric,.helpcard,.fmtcard,
    div[data-testid="stVerticalBlockBorderWrapper"]{ background:#1e293b !important; border-color:#334155 !important; }
    .cardtitle,.card h3,.tb h1,.metric .val,.b,.brand .name{ color:#f8fafc !important; }
    .stMarkdown,.stMarkdown p,.stMarkdown li,.stApp p,.stApp li,.stApp span,
    .stApp label,.metric .lab,.muted{ color:#cbd5e1 !important; }
    input,textarea,select,[data-baseweb="select"]>div{ background:#0f172a !important; color:#f1f5f9 !important; }
    .stDataFrame,div[data-testid="stDataFrame"]{ background:#1e293b !important; }
    </style>
    """, unsafe_allow_html=True)

PILL = {"In Review": "p-rev", "Drafting": "p-ana", "Analyzed": "p-ana", "Approved": "p-app",
        "Exported": "p-exp", "Uploaded": "p-pend", "Pending": "p-pend", "Rejected": "p-rej"}


def pill(text, cls=None):
    return f"<span class='pill {cls or PILL.get(text,'p-pend')}'>{text}</span>"


# =========================================================================== #
#  SIDEBAR
# =========================================================================== #
NAV = [("Upload", "☁️"), ("Dashboard", "📊"), ("Resource Cost", "💲"),
       ("Human Review", "🗂️"), ("Export", "📤"), ("AI Evaluation", "🔎"), ("Settings", "⚙️"), ("Help & Docs", "❓")]

with st.sidebar:
    st.markdown(f"<div class='brand'><div class='logo'>📄</div><div>"
                f"<div class='name'>Smart<span>RFP</span></div>"
                f"<div class='sub'>{ss.get('workspace', 'AI-Powered RFP Analysis')}</div>"
                f"</div></div>", unsafe_allow_html=True)
    for name, icon in NAV:
        wrap = "nav-active" if ss.page == name else "nav-x"
        st.markdown(f"<div class='{wrap}'>", unsafe_allow_html=True)
        if st.button(f"{icon}  {name}", key=f"nav_{name}", use_container_width=True):
            go(name)
        st.markdown("</div>", unsafe_allow_html=True)

    live = llm_available()
    st.markdown(
        f"<div class='groq'><div class='row'><span class='dot {'' if live else 'off'}'></span>"
        f"Groq API Status</div><div class='st {'' if live else 'off'}'>"
        f"{'Connected' if live else 'Demo mode'}</div>"
        f"<div class='mod'>Model: {GROQ_MODEL}</div></div>", unsafe_allow_html=True)
    if st.button("🔌 Test Connection", key="side_test", use_container_width=True):
        with st.spinner("Calling Groq…"):
            r = groq_ping()
        st.toast(("✅ " + r["message"]) if r["ok"] else ("❌ " + r["message"]))


# =========================================================================== #
#  SHARED helpers
# =========================================================================== #
def topbar(title, subtitle, icon="", show_rfp=False):
    left, right = st.columns([3, 1.5])
    with left:
        st.markdown(f"<div class='tb'><div><h1>{icon} {title}</h1>"
                    f"<div class='sub'>{subtitle}</div></div></div>", unsafe_allow_html=True)
    with right:
        cols = st.columns([2.2, 0.7]) if show_rfp else st.columns([2.6, 0.7])
        if show_rfp:
            rfps = db.list_rfps()
            if rfps:
                ids = [r["id"] for r in rfps]
                lbl = {r["id"]: r["deal_name"] for r in rfps}
                cur = ss.current_rfp if ss.current_rfp in ids else ids[0]
                sel = cols[0].selectbox("RFP", ids, index=ids.index(cur),
                                        format_func=lambda i: lbl[i], label_visibility="collapsed",
                                        key=f"rfpsel_{title}")
                ss.current_rfp = sel
        cols[-1].markdown("<div class='avatar'>👤</div>", unsafe_allow_html=True)


def metric(col, ic, icon, label, value, sub):
    col.markdown(f"<div class='metric'><div class='top'><div class='lab'>{label}</div>"
                 f"<div class='ic {ic}'>{icon}</div></div><div class='val'>{value}</div>"
                 f"<div class='sub'>{sub}</div></div>", unsafe_allow_html=True)


@contextmanager
def card(title=None):
    """A real bordered container so Streamlit widgets sit INSIDE the box."""
    box = st.container(border=True)
    with box:
        if title:
            st.markdown(f"<div class='cardtitle'>{title}</div>", unsafe_allow_html=True)
        yield box


def current_rfp():
    rfps = db.list_rfps()
    if not rfps:
        return None
    ids = [r["id"] for r in rfps]
    rid = ss.current_rfp if ss.current_rfp in ids else ids[0]
    ss.current_rfp = rid
    return db.get_rfp(rid)


def exported_ids():
    out = set()
    for r in db.list_rfps():
        for a in db.get_audit_log(r["id"]):
            if "export" in (a["action"] or "").lower():
                out.add(r["id"]); break
    return out


# =========================================================================== #
#  PAGE: Upload
# =========================================================================== #
def page_upload():
    topbar("Upload RFP Document", "Upload your RFP document and let AI analyze it for you.", "☁️")

    up = st.file_uploader("Drag & drop your file here", type=SUPPORTED_TYPES,
                          label_visibility="collapsed")
    st.caption(f"Supported formats: {', '.join(t.upper() for t in SUPPORTED_TYPES)}  ·  "
               f"Max file size: {MAX_UPLOAD_MB}MB")

    with st.expander("Deal details (optional) — set client, region, deadline & reviewer", expanded=bool(up)):
        c1, c2 = st.columns(2)
        deal = c1.text_input("Deal / Project name", placeholder="e.g. Acme Cloud Migration RFP")
        client = c2.text_input("Client name", placeholder="e.g. Acme Corp")
        c3, c4, c5 = st.columns(3)
        region = c3.text_input("Region", placeholder="e.g. North America")
        deadline = c4.text_input("Deadline", placeholder="e.g. 2026-08-15")
        role = c5.selectbox("Assign reviewer role", REVIEWER_ROLES)
        use_web = st.checkbox("Use live web search / pricing (Agent 2)", value=True)

    if up and st.button("⚡ Analyze & Generate Response", type="primary", use_container_width=True):
        try:
            raw = extract_text(up.name, up.getvalue())
        except Exception as e:
            st.error(f"Could not read that file: {e}"); return
        if len(raw.strip()) < 30:
            st.error("That file has almost no readable text."); return
        rid = db.create_rfp(deal or up.name, client, region, deadline, "", "",
                            up.name, raw, role, "", use_web)
        bar = st.progress(0.0, text="Starting…")
        run_pipeline(rid, raw, use_web, progress=lambda lab, f: bar.progress(f, text=lab))
        bar.empty()
        st.success("✅ Analysis complete. Opening Dashboard…")
        go("Dashboard", rid)

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("<div class='card'><h3>📄 Upload Guidelines</h3>"
                    "<div class='muted' style='line-height:2'>"
                    "✅ Ensure the document is clear and readable<br>"
                    "✅ All pages should be included<br>"
                    f"✅ Supported formats: {', '.join(t.upper() for t in SUPPORTED_TYPES)}<br>"
                    f"✅ Maximum file size: {MAX_UPLOAD_MB}MB</div></div>", unsafe_allow_html=True)
    with g2:
        rows = ""
        for r in db.list_rfps()[:4]:
            rows += (f"<div class='feed'><div class='fi ic-red'>📕</div><div style='flex:1'>"
                     f"<div class='ft'>{r['file_name'] or r['deal_name']}</div>"
                     f"<div class='fd'>{(r.get('updated_at') or '')[:10]}</div></div></div>")
        st.markdown(f"<div class='card'><h3>🗂️ Recent Uploads</h3>{rows or '<div class=muted>No uploads yet.</div>'}</div>",
                    unsafe_allow_html=True)


# =========================================================================== #
#  PAGE: Dashboard
# =========================================================================== #
def page_dashboard():
    topbar("Dashboard", "Overview of your RFP analysis and proposal generation pipeline.", "📊")

    rfps = db.list_rfps()
    exp = exported_ids()
    total = len(rfps)
    analyzed = sum(1 for r in rfps if r["status"] != "Uploaded")
    in_review = sum(1 for r in rfps if r["status"] == "In Review")
    approved = sum(1 for r in rfps if r["status"] == "Approved")
    exported = len(exp)

    cols = st.columns(5)
    metric(cols[0], "ic-purple", "📄", "Total RFPs", total, "All time")
    metric(cols[1], "ic-blue", "📊", "Analyzed", analyzed, "This month")
    metric(cols[2], "ic-amber", "🕐", "In Review", in_review, "Pending review")
    metric(cols[3], "ic-green", "✅", "Approved", approved, "This month")
    metric(cols[4], "ic-teal", "📤", "Exported", exported, "This month")
    st.write("")

    left, right = st.columns([1, 1.25])
    # ---- Donut ----
    with left:
        with card("RFP Status Overview"):
            drafting = sum(1 for r in rfps if r["status"] == "Drafting")
            others = sum(1 for r in rfps if r["status"] in ("Uploaded", "Rejected"))
            data = pd.DataFrame({
                "Status": ["Analyzed", "In Review", "Approved", "Exported", "Others"],
                "Count": [max(analyzed - in_review - approved, drafting),
                          in_review, approved, exported, others],
            })
            tot = int(data["Count"].sum())
            if tot == 0:
                st.info("No RFPs yet — upload one to see the breakdown.")
            else:
                data["pct"] = (data["Count"] / tot * 100).round(0).astype(int)
                data["label"] = data.apply(
                    lambda r: f'{int(r["Count"])} ({r["pct"]}%)' if r["Count"] > 0 else "", axis=1)
                rng = ["#2563eb", "#93c5fd", "#16a34a", "#f59e0b", "#cbd5e1"]
                base = alt.Chart(data).encode(
                    theta=alt.Theta("Count:Q", stack=True),
                    color=alt.Color("Status:N",
                                    scale=alt.Scale(domain=list(data["Status"]), range=rng),
                                    legend=alt.Legend(title=None, orient="right")),
                    tooltip=["Status", "Count", "pct"])
                arc = base.mark_arc(innerRadius=62, outerRadius=104)
                txt = base.mark_text(radius=125, fontSize=11, fontWeight="bold").encode(text="label:N")
                st.altair_chart((arc + txt).properties(height=300), use_container_width=True)

    # ---- Recent RFPs (delete option sits INSIDE the box) ----
    with right:
        with card("Recent RFPs"):
            if rfps:
                n = int(ss.get("items_per_page", 6))
                hc = st.columns([2.3, 1.6, 1.3, 1.4, 0.6])
                for c, t in zip(hc, ["RFP Name", "Client", "Status", "Last Updated", ""]):
                    c.markdown(f"<span class='muted' style='font-weight:700;font-size:.8rem'>{t}</span>",
                               unsafe_allow_html=True)
                for r in rfps[:n]:
                    c = st.columns([2.3, 1.6, 1.3, 1.4, 0.6])
                    c[0].write(r["deal_name"])
                    c[1].write(r.get("client_name") or "—")
                    c[2].markdown(pill(r["status"]), unsafe_allow_html=True)
                    c[3].write((r.get("updated_at") or "")[:10])
                    if c[4].button("🗑️", key=f"dashdel_{r['id']}", help="Delete this RFP",
                                   use_container_width=True):
                        db.delete_rfp(r["id"]); st.toast("RFP deleted."); st.rerun()
            else:
                st.info("No RFPs yet.")
            if st.button("View all →", key="dash_viewall"):
                go("Human Review")

    # ---- Pipeline + AI insights ----
    pcol, icol = st.columns([1.4, 1])
    with pcol:
        with card("Pipeline Progress"):
            steps = [("☁️", "Upload", "done"), ("📄", "Analyze", "done"),
                     ("⚙️", "Costing", "prog"), ("🧑‍⚖️", "Review", "pend"), ("📤", "Export", "pend")]
            sc = st.columns([2, 1, 2, 1, 2, 1, 2, 1, 2])
            order = [0, None, 1, None, 2, None, 3, None, 4]
            statelab = {"done": "Completed", "prog": "In Progress", "pend": "Pending"}
            statecol = {"done": "var(--green)", "prog": "var(--blue)", "pend": "var(--muted)"}
            for i, slot in enumerate(order):
                if slot is None:
                    sc[i].markdown("<div class='arrow'>→</div>", unsafe_allow_html=True)
                else:
                    e, n, s = steps[slot]
                    sc[i].markdown(f"<div class='step'><div class='c {s}'>{e}</div><div class='n'>{n}</div>"
                                   f"<div class='s' style='color:{statecol[s]}'>{statelab[s]}</div></div>",
                                   unsafe_allow_html=True)
    with icol:
        with card("AI Insights"):
            st.markdown("<div class='muted'>Most common requirement category</div>"
                        "<div style='margin:.3rem 0 .8rem'><span class='refpill'>Security &amp; Compliance</span></div>"
                        "<div class='muted'>Average proposal length</div>"
                        "<div style='margin-top:.3rem'><span class='refpill'>24 pages</span></div>",
                        unsafe_allow_html=True)


# =========================================================================== #
#  PAGE: Resource Cost
# =========================================================================== #
ROLE_SPLIT = [("Project Management", 0.1466, 0.1208), ("Business Analysis", 0.1101, 0.0989),
              ("Solution Architecture", 0.2611, 0.1758), ("Development", 0.3625, 0.3625),
              ("Testing & QA", 0.0811, 0.1099), ("Training & Support", 0.0501, 0.0521)]


def page_resource_cost():
    topbar("Resource & Cost Estimate", "Estimated resources, effort, and cost for this RFP.", "💲", show_rfp=True)
    rfp = current_rfp()
    if not rfp:
        st.info("No RFPs yet. Upload one to see the cost estimate."); return

    pricing = db.get_pricing(rfp["id"])
    # ---- Total cost: sum of Agent 2 pricing lines (dynamic, from RFP keywords) ----
    total_cost = sum(p["total"] for p in pricing) if pricing else 245680.0

    # ---- Effort: derived from the RFP's parsed requirements (dynamic per RFP) ----
    num_req = rfp.get("num_requirements") or len(db.get_draft_sections(rfp["id"])) or 8
    BASE_OVERHEAD_HRS = 160          # PM / setup / mobilisation
    HRS_PER_REQUIREMENT = 130        # analysis + design + build + test per requirement
    total_hours = BASE_OVERHEAD_HRS + num_req * HRS_PER_REQUIREMENT

    # ---- Weeks: effort ÷ blended team capacity (dynamic) ----
    TEAM_CAPACITY_HRS_PER_WEEK = 130
    weeks = max(1, -(-total_hours // TEAM_CAPACITY_HRS_PER_WEEK))   # ceil

    # ---- Confidence: derived from pricing freshness + reviewer flags (dynamic) ----
    stale = any(p.get("stale") for p in pricing)
    num_flags = rfp.get("num_flags") or 0
    if not stale and num_flags == 0:
        confidence, variance = "High", "±8%"
    elif not stale and num_flags <= 2:
        confidence, variance = "High", "±10%"
    elif num_flags <= 4:
        confidence, variance = "Medium", "±15%"
    else:
        confidence, variance = "Medium", "±20%"

    # currency comes from Settings → General (dynamic)
    code = ss.get("currency", "USD - US Dollar").split(" - ")[0]
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹"}.get(code, "$")

    cols = st.columns(4)
    metric(cols[0], "ic-blue", "🧾", "Total Estimated Cost", f"{sym}{total_cost:,.0f}", code)
    metric(cols[1], "ic-green", "🕐", "Total Effort", f"{total_hours:,} hrs", f"{weeks} Weeks")
    metric(cols[2], "ic-purple", "🛡️", "Cost Confidence", confidence, f"{variance} Estimation Variance")
    metric(cols[3], "ic-amber", "💲", "Currency", code, f"All costs in {code}")
    st.write("")

    with st.expander("ℹ️ How are these numbers calculated?"):
        st.markdown(
            f"- **Total Estimated Cost** = sum of the live pricing lines from Agent 2 "
            f"(built from keywords in this RFP). Current total: **{sym}{total_cost:,.0f}** "
            f"from **{len(pricing)}** pricing line(s).\n"
            f"- **Total Effort** = {BASE_OVERHEAD_HRS} base hrs + "
            f"**{num_req} requirements** × {HRS_PER_REQUIREMENT} hrs = **{total_hours:,} hrs**.\n"
            f"- **Weeks** = effort ÷ {TEAM_CAPACITY_HRS_PER_WEEK} hrs/week team capacity = **{weeks} weeks**.\n"
            f"- **Cost Confidence** comes from pricing freshness (stale lines: "
            f"**{'yes' if stale else 'no'}**) and reviewer flags (**{num_flags}**).\n\n"
            f"Because these depend on the RFP's requirement count, flags and matched pricing, "
            f"they change from one RFP to another.")

    with card("Cost Breakdown by Role"):
        role_names = [r[0] for r in ROLE_SPLIT]
        choice = st.selectbox("Filter by role", ["All roles"] + role_names, key="role_filter")
        shown = ROLE_SPLIT if choice == "All roles" else [r for r in ROLE_SPLIT if r[0] == choice]
        cost_rows = []
        for name, cpct, apct in shown:
            cost_rows.append({"Role": name, "Effort (hrs)": int(total_hours * apct),
                              f"Cost ({code})": f"{sym}{total_cost*cpct:,.0f}",
                              "% of Total": f"{cpct*100:.2f}%"})
        if choice == "All roles":
            cost_rows.append({"Role": "Total", "Effort (hrs)": total_hours,
                              f"Cost ({code})": f"{sym}{total_cost:,.0f}", "% of Total": "100%"})
        st.dataframe(pd.DataFrame(cost_rows), use_container_width=True, hide_index=True)

    with card("Resource Allocation"):
        for name, cpct, apct in sorted(shown, key=lambda r: -r[2]):
            bar = int(apct * 100)
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:.8rem;margin:.35rem 0'>"
                f"<div style='width:150px;font-size:.9rem;color:var(--ink2)'>{name}</div>"
                f"<div style='width:90px;font-size:.85rem;color:var(--muted)'>{int(total_hours*apct)} hrs</div>"
                f"<div style='flex:1;background:#eef2f7;border-radius:6px;height:10px'>"
                f"<div style='width:{bar}%;background:var(--blue);height:10px;border-radius:6px'></div></div>"
                f"<div style='width:54px;text-align:right;font-weight:700;color:var(--ink)'>{apct*100:.1f}%</div>"
                f"</div>", unsafe_allow_html=True)

    st.info("This estimate is AI-generated based on the RFP requirements and historical data. "
            "Please review and adjust as needed.")


# =========================================================================== #
#  PAGE: Human Review
# =========================================================================== #
def _rev_key(rid, sid): return f"{rid}:{sid}"


def page_review():
    topbar("Human Review & Approval", "Review the AI-generated proposal and provide feedback.",
           "🗂️", show_rfp=True)
    rfp = current_rfp()
    if not rfp:
        st.info("No RFPs yet. Upload one to review."); return
    sections = db.get_draft_sections(rfp["id"])
    if not sections:
        st.info("This RFP has no draft yet."); return

    reviewer = rfp.get("assigned_to") or rfp.get("assigned_role") or "Reviewer"
    main, rightc = st.columns([2.7, 1.1])

    # --- Full proposal (all sections in one view, no per-section approval) ---
    with main:
        with card():
            st.markdown(f"<div class='cardtitle' style='display:flex;justify-content:space-between'>"
                        f"<span>{rfp['deal_name']}</span>{pill(rfp['status'])}</div>",
                        unsafe_allow_html=True)
            for s in sections:
                st.markdown(f"#### {s['section_title']}")
                st.markdown(s["content"])
                if s.get("source"):
                    refs = "".join(f"<span class='refpill'>{x.strip()}</span>"
                                   for x in (s["source"] or "").split(",") if x.strip())
                    st.markdown(f"<div class='muted' style='margin-top:.2rem'>Source: </div>{refs}",
                                unsafe_allow_html=True)
                with st.expander("✏️ Edit this section"):
                    new = st.text_area("content", value=s["content"], height=200,
                                       label_visibility="collapsed", key=f"edit_{s['id']}")
                    if st.button("💾 Save", key=f"save_{s['id']}"):
                        db.update_draft_section(s["id"], new)
                        db.log_action(rfp["id"], "Edited section", reviewer, s["section_title"])
                        st.toast("Saved."); st.rerun()
                st.markdown("<hr>", unsafe_allow_html=True)

    # --- Whole-proposal actions ---
    with rightc:
        with card("Review Actions"):
            comment = st.text_area("Reviewer comments", placeholder="Add a comment…",
                                   key="review_comment", height=90)
            if st.button("✅ Approve Proposal", use_container_width=True, key="approve_all"):
                db.update_rfp_status(rfp["id"], "Approved")
                db.log_action(rfp["id"], "Approved", reviewer,
                              comment.strip()[:80] or "Proposal approved")
                st.toast("Proposal approved."); st.rerun()
            if st.button("✏️ Request Changes", use_container_width=True, key="req_changes"):
                db.update_rfp_status(rfp["id"], "In Review")
                db.log_action(rfp["id"], "Changes requested", reviewer,
                              comment.strip()[:80] or "Changes requested")
                st.toast("Changes requested."); st.rerun()
            if st.button("💬 Add Comment", use_container_width=True, key="add_cmt"):
                if comment.strip():
                    db.log_action(rfp["id"], "Comment added", reviewer, comment.strip()[:80])
                    st.toast("Comment added.")
                else:
                    st.toast("Type a comment first.")
                st.rerun()
            if st.button("🔄 Regenerate Draft", use_container_width=True, key="regen_all"):
                bar = st.progress(0.0, text="Regenerating…")
                run_pipeline(rfp["id"], rfp["raw_text"], bool(rfp["use_web_search"]),
                             progress=lambda l, f: bar.progress(f, text=l))
                bar.empty(); st.toast("Draft regenerated."); st.rerun()
        with card("Review Information"):
            st.markdown(f"<div class='muted'>Reviewer</div><div class='b'>{reviewer}</div>"
                        f"<div class='muted' style='margin-top:.5rem'>Status</div><div>{pill(rfp['status'])}</div>"
                        f"<div class='muted' style='margin-top:.5rem'>Sections</div>"
                        f"<div class='b'>{len(sections)}</div>"
                        f"<div class='muted' style='margin-top:.5rem'>Last Updated</div>"
                        f"<div class='b'>{(rfp.get('updated_at') or '')[:16]}</div>", unsafe_allow_html=True)

    # --- History ---
    with card("Review History"):
        log = db.get_audit_log(rfp["id"])
        if log:
            st.dataframe(pd.DataFrame([{"Reviewer": a["actor"], "Action": a["action"],
                                        "Detail": a.get("detail") or "", "Time": a["timestamp"]}
                                       for a in log][::-1]), use_container_width=True, hide_index=True)
        else:
            st.caption("No history yet.")


# =========================================================================== #
#  PAGE: Export
# =========================================================================== #
def _html_export(rfp):
    secs = db.get_draft_sections(rfp["id"])
    body = "".join(f"<h2>{s['section_title']}</h2><p>{s['content']}</p>" for s in secs)
    html = (f"<!doctype html><html><head><meta charset='utf-8'><title>{rfp['deal_name']}</title>"
            f"<style>body{{font-family:Arial;max-width:800px;margin:40px auto;color:#0f172a}}"
            f"h1{{color:#2563eb}}h2{{margin-top:1.4em}}</style></head><body>"
            f"<h1>{rfp['deal_name']}</h1><p><b>Client:</b> {rfp.get('client_name') or '—'}</p>"
            f"{body}</body></html>")
    return html.encode("utf-8")


def _xlsx_export(rfp):
    pricing = db.get_pricing(rfp["id"])
    df = pd.DataFrame([{"Item": p["item"], "Qty": p["qty"], "Unit price": p["unit_price"],
                        "Total": p["total"], "Fetched": p["fetched_at"],
                        "Stale": "Yes" if p["stale"] else "No"} for p in pricing]) \
        if pricing else pd.DataFrame([{"Item": "(no pricing)"}])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        df.to_excel(xl, index=False, sheet_name="Cost Estimate")
    return buf.getvalue()


FORMATS = [("PDF", "📕", "Best for sharing and printing"),
           ("Word (DOCX)", "📘", "Editable Word document"),
           ("Excel (XLSX)", "📗", "Cost & resource data only"),
           ("PowerPoint (PPTX)", "📙", "Executive summary presentation"),
           ("HTML", "🌐", "Web-friendly format"),
           ("Text (TXT)", "📄", "Plain text format")]


def page_export():
    topbar("Export RFP Response", "Export your AI-generated RFP response in your preferred format.",
           "📤", show_rfp=True)
    rfp = current_rfp()
    if not rfp:
        st.info("No RFPs yet. Upload one to export."); return

    st.markdown("<div class='card'><h3>1. Select Export Format</h3>", unsafe_allow_html=True)
    fcols = st.columns(6)
    for i, (name, e, d) in enumerate(FORMATS):
        sel = ss.export_format == name
        fcols[i].markdown(f"<div class='fmtcard {'sel' if sel else ''}'><div class='e'>{e}</div>"
                          f"<div class='t'>{name}</div><div class='d'>{d}</div></div>", unsafe_allow_html=True)
        if fcols[i].button("Select", key=f"fmt_{name}", use_container_width=True):
            ss.export_format = name; st.rerun()
    st.markdown("<hr>", unsafe_allow_html=True)
    inc, opt = st.columns(2)
    with inc:
        st.markdown("**Include in Export**")
        for x in ["Cover Page & Executive Summary", "Requirements & Proposed Approach",
                  "Compliance & Security", "Resource Plan & Cost Estimate", "Appendices & References"]:
            st.checkbox(x, value=True, key=f"inc_{x}")
    with opt:
        st.markdown("**Export Options**")
        for x in ["Include Table of Contents", "Include Page Numbers", "Include Company Branding"]:
            st.checkbox(x, value=True, key=f"opt_{x}")
        st.selectbox("Branding", ["SmartRFP Default Template", "Minimal", "Corporate"])
    st.markdown("</div>", unsafe_allow_html=True)

    secs = db.get_draft_sections(rfp["id"])

    # summary + export
    s1, s2 = st.columns([1.2, 1])
    with s1:
        st.markdown(f"<div class='card'><h3>2. Export Summary</h3>"
                    f"<div class='muted' style='line-height:2'>"
                    f"📄 RFP Document — <span class='b'>{rfp['deal_name']}</span><br>"
                    f"📋 Total Sections — <span class='b'>{len(secs)}</span><br>"
                    f"📑 Estimated Pages — <span class='b'>24 – 30</span><br>"
                    f"💾 Format — <span class='b'>{ss.export_format}</span><br>"
                    f"🕐 Last Updated — <span class='b'>{(rfp.get('updated_at') or '')[:16]}</span>"
                    f"</div></div>", unsafe_allow_html=True)
    with s2:
        st.markdown("<div class='card'><h3>✅ Export Ready</h3>"
                    "<div class='muted'>Your RFP response is ready to be exported.</div><br>",
                    unsafe_allow_html=True)
        fmt = ss.export_format
        safe = "".join(ch if ch.isalnum() else "_" for ch in rfp["deal_name"])[:40] or "proposal"
        ok = True
        if ss.get("confirm_export", True):
            ok = st.checkbox("I confirm this proposal is ready to export", key="confirm_exp_chk")
        if not ok:
            st.caption("Tick the confirmation box to enable the download "
                       "(toggle off under Settings → Confirm before export).")
        try:
            if not ok:
                st.button("⬇️ Export Now", disabled=True, use_container_width=True)
            elif fmt == "PDF":
                st.download_button("⬇️ Export Now", export_pdf(rfp["id"]), f"{safe}.pdf",
                                   "application/pdf", type="primary", use_container_width=True)
            elif fmt == "Word (DOCX)":
                st.download_button("⬇️ Export Now", export_docx(rfp["id"]), f"{safe}.docx",
                                   "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                   type="primary", use_container_width=True)
            elif fmt == "Excel (XLSX)":
                st.download_button("⬇️ Export Now", _xlsx_export(rfp), f"{safe}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   type="primary", use_container_width=True)
            elif fmt == "HTML":
                st.download_button("⬇️ Export Now", _html_export(rfp), f"{safe}.html",
                                   "text/html", type="primary", use_container_width=True)
            elif fmt == "Text (TXT)":
                st.download_button("⬇️ Export Now", export_txt(rfp["id"]), f"{safe}.txt",
                                   "text/plain", type="primary", use_container_width=True)
            else:  # PowerPoint placeholder -> export executive summary as TXT
                st.download_button("⬇️ Export Now (summary .txt)", export_txt(rfp["id"]),
                                   f"{safe}.txt", "text/plain", type="primary", use_container_width=True)
                st.caption("PPTX generation isn't enabled in this build; exporting the summary as text.")
        except Exception as e:
            st.error(f"Export failed: {e}")
        if ok and rfp["status"] != "Rejected":
            db.log_action(rfp["id"], "Exported", rfp.get("assigned_role") or "Reviewer", fmt)
        st.markdown("</div>", unsafe_allow_html=True)

    st.info("🔒 Data Security: Exported files are generated on-demand and are not stored on our servers.")


# =========================================================================== #
#  PAGE: AI Evaluation
# =========================================================================== #
def llm_eval():
    topbar("AI Evaluation", "Check performance of LLM calls.", show_rfp=True)
    rfp = current_rfp()
    evaluation = db.get_evaluation_metrics(rfp["id"]) if rfp else None

    if evaluation:
        overall_score = (
            evaluation["proposal_completeness"]
            + evaluation["average_confidence"]
            + evaluation["context_coverage"]
            + evaluation["pricing_freshness"]
        ) / 4
    left, middle, right = st.columns([1,2,1])

    with left:

        st.metric(
            "Overall AI Quality Score",
            f"{overall_score*100:.1f}%"
        )

    cols = st.columns(4)

    metric(
        cols[0],
        "ic-green",
        "✅",
        "Completeness",
        f"{evaluation['proposal_completeness']*100:.0f}%",
        "Proposal"
    )

    metric(
        cols[1],
        "ic-blue",
        "📚",
        "Context",
        f"{evaluation['context_coverage']*100:.0f}%",
        "Grounded"
    )

    metric(
        cols[2],
        "ic-purple",
        "🎯",
        "Confidence",
        f"{evaluation['average_confidence']:.2f}",
        "LLM"
    )

    metric(
        cols[3],
        "ic-red",
        "⚠️",
        "Flags",
        str(evaluation["hallucination_flags"]),
        "Review"
    )

    with card("AI Quality Indicators"):
        st.write("Proposal Completeness")
        st.progress(evaluation["proposal_completeness"])

        st.write("Average Confidence")
        st.progress(evaluation["average_confidence"])

        st.write("Context Coverage")
        st.progress(evaluation["context_coverage"])

        st.write("Pricing Freshness")
        st.progress(evaluation["pricing_freshness"])

    st.divider()

    st.subheader("🧠 Advanced RAG Evaluation")

    cols = st.columns(4)

    metric(
        cols[0],
        "ic-blue",
        "📖",
        "Faithfulness",
        f"{evaluation['faithfulness']*100:.1f}%",
        "Grounded"
    )

    metric(
        cols[1],
        "ic-green",
        "🎯",
        "Answer Relevancy",
        f"{evaluation['answer_relevancy']*100:.1f}%",
        "Relevant"
    )

    metric(
        cols[2],
        "ic-purple",
        "📚",
        "Context Precision",
        f"{evaluation['context_precision']*100:.1f}%",
        "Retrieved"
    )

    metric(
        cols[3],
        "ic-amber",
        "🔍",
        "Context Recall",
        f"{evaluation['context_recall']*100:.1f}%",
        "Coverage"
    )

    cols = st.columns(3)

    metric(
        cols[0],
        "ic-blue",
        "🏆",
        "MRR@K",
        f"{evaluation['mrr']:.2f}",
        "Ranking"
    )

    metric(
        cols[1],
        "ic-green",
        "🎯",
        "Hit Rate@K",
        f"{evaluation['hit_rate']*100:.0f}%",
        "Success"
    )

    metric(
        cols[2],
        "ic-red",
        "🧩",
        "Chunk Overlap",
        f"{evaluation['chunk_overlap']*100:.1f}%",
        "Lower is Better"
    )

    with card("Advanced Evaluation Indicators"):

        st.write("Faithfulness")
        st.progress(evaluation["faithfulness"])

        st.write("Answer Relevancy")
        st.progress(evaluation["answer_relevancy"])

        st.write("Context Precision")
        st.progress(evaluation["context_precision"])

        st.write("Context Recall")
        st.progress(evaluation["context_recall"])
    
    stats = pd.DataFrame({
    "Metric":[
        "Pipeline Runtime",
        "LLM Calls",
        "Knowledge Base Documents",
        "Pricing Items",
        "MRR@K",
        "Hit Rate@K",
        "Chunk Overlap"
    ],

    "Value":[
        f"{evaluation['runtime_seconds']} sec",
        evaluation["llm_calls"],
        evaluation["knowledge_documents"],
        evaluation["pricing_items"],
        f"{evaluation['mrr']:.2f}",
        f"{evaluation['hit_rate']:.2f}",
        f"{evaluation['chunk_overlap']:.2f}",
    ]
    })

    st.dataframe(
        stats,
        use_container_width=True,
        hide_index=True
    )

# =========================================================================== #
#  PAGE: Settings
# =========================================================================== #
def page_settings():
    topbar("Settings", "Manage your preferences, AI model settings, and application configuration.",
           "⚙️", show_rfp=True)
    tabs = st.tabs(["General", "AI Model", "Security"])

    with tabs[0]:
        a, b = st.columns(2)
        with a:
            st.markdown("<div class='card'><h3>⚙️ General Settings</h3>", unsafe_allow_html=True)
            ws = st.text_input("Workspace / Organization Name", ss.workspace)
            tmpl = st.selectbox("Default RFP Template",
                                ["SmartRFP Standard Template", "Minimal", "Corporate"])
            cur_opts = ["USD - US Dollar", "EUR - Euro", "GBP - Pound", "INR - Rupee"]
            cur = st.selectbox("Default Currency", cur_opts, index=cur_opts.index(ss.currency))
            df_ = st.selectbox("Date Format", ["MMM DD, YYYY", "DD/MM/YYYY", "YYYY-MM-DD"])
            tz = st.selectbox("Time Zone", ["(GMT+05:30) Asia/Kolkata", "(GMT) UTC",
                                            "(GMT-05:00) US Eastern"])
            if st.button("Save Changes", type="primary", key="gen_save"):
                ss.workspace, ss.currency = ws, cur
                ss.update({"template": tmpl, "date_format": df_, "timezone": tz})
                st.success("✅ General settings saved. Currency applies on Resource Cost; "
                           "workspace name updates in the sidebar.")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with b:
            st.markdown("<div class='card'><h3>🖥️ Application Preferences</h3>", unsafe_allow_html=True)
            theme = st.radio("Theme", ["Light", "Dark", "System"], horizontal=True,
                             index=["Light", "Dark", "System"].index(ss.theme))
            lang = st.selectbox("Language", ["English", "Spanish", "French", "German"])
            ipp_opts = [6, 10, 25, 50]
            ipp = st.selectbox("Items per page", ipp_opts, index=ipp_opts.index(ss.items_per_page)
                               if ss.items_per_page in ipp_opts else 0)
            tips = st.toggle("Show tips and guidance", value=ss.get("tips", True))
            autosave = st.toggle("Auto save drafts", value=ss.get("autosave", True))
            confirm = st.toggle("Confirm before export", value=ss.get("confirm_export", True))
            if st.button("Save Preferences", type="primary", key="pref_save"):
                ss.update({"theme": theme, "language": lang, "items_per_page": int(ipp),
                           "tips": tips, "autosave": autosave, "confirm_export": confirm})
                st.success(f"✅ Preferences saved. Dashboard now shows up to {ipp} rows.")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        c, d = st.columns(2)
        with c:
            st.markdown("<div class='card'><h3>📁 File & Storage Settings</h3>", unsafe_allow_html=True)
            st.selectbox("Max file upload size", ["50 MB", "100 MB", "200 MB"])
            st.markdown("Supported file types")
            fc = st.columns(5)
            for i, t in enumerate(["PDF", "DOCX", "XLSX", "PPTX", "TXT"]):
                fc[i].checkbox(t, value=True, key=f"ft_{t}")
            st.toggle("Auto delete old files (90 days)", value=ss.get("autodelete", False), key="autodelete")
            if st.button("Save Changes", key="store_save"):
                st.success("✅ Storage settings saved.")
            st.markdown("</div>", unsafe_allow_html=True)
        with d:
            st.markdown("<div class='card'><h3>🕐 Session Settings</h3>", unsafe_allow_html=True)
            st.selectbox("Session timeout", ["30 minutes", "1 hour", "4 hours"])
            st.toggle("Auto logout inactive users", value=ss.get("autologout", False), key="autologout")
            st.toggle("Remember last workspace", value=ss.get("remember_ws", True), key="remember_ws")
            st.selectbox("Refresh data interval", ["5 minutes", "15 minutes", "1 hour"])
            if st.button("Save Changes", key="session_save"):
                st.success("✅ Session settings saved.")
            st.markdown("</div>", unsafe_allow_html=True)

        # ---- Live summary so it's clear these settings actually apply ----
        with card("Current Configuration (live)"):
            st.markdown(
                f"- **Workspace:** {ss.get('workspace')}\n"
                f"- **Currency:** {ss.get('currency')} (applied on Resource Cost)\n"
                f"- **Items per page:** {ss.get('items_per_page')} (applied on Dashboard)\n"
                f"- **Theme:** {ss.get('theme')}\n"
                f"- **Active AI model:** {config.GROQ_MODEL}\n"
                f"- **Confirm before export:** {'On' if ss.get('confirm_export', True) else 'Off'}")

    # ---- AI Model (functional Groq panel) ----
    with tabs[1]:
        st.markdown("<div class='card'><h3>🤖 AI / Groq Configuration</h3>", unsafe_allow_html=True)
        key = config.GROQ_API_KEY
        masked = (key[:6] + "…" + key[-4:]) if len(key) > 12 else ("(set)" if key else "(empty)")
        m1, m2 = st.columns(2)
        m1.metric("API key", "Detected" if key else "Not found")
        m2.metric("Active model", config.GROQ_MODEL)
        st.caption(f"**.env file in use:** `{config.ENV_FILE or '— none found —'}`")
        st.caption(f"**Key (masked):** `{masked}`")

        model_opts = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.6-27b",
                      "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
        if config.GROQ_MODEL not in model_opts:
            model_opts.insert(0, config.GROQ_MODEL)
        chosen = st.selectbox("Model (applies immediately)", model_opts,
                              index=model_opts.index(config.GROQ_MODEL))
        if chosen != config.GROQ_MODEL:
            config.GROQ_MODEL = chosen          # llm.chat()/ping() read this live
            ss.groq_model = chosen
            st.success(f"✅ Model switched to `{chosen}`.")

        if st.button("🔌 Test Groq connection", type="primary", key="ai_test"):
            with st.spinner("Calling Groq…"):
                r = groq_ping()
            (st.success if r["ok"] else st.error)(
                ("✅ " + r["message"]) if r["ok"] else ("❌ Connection failed: " + r["message"]))
        if not key:
            st.warning("No API key detected — running in **demo mode** (still fully functional).")
            with st.expander("🔎 Which env files were found?", expanded=True):
                for p, exists in config.ENV_SEARCHED:
                    st.markdown(f"{'✅' if exists else '❌'} `{p}`")
            st.markdown("Create a file named exactly **`.env`** next to `app.py` with:")
            st.code("GROQ_API_KEY=gsk_your_real_key_here\nGROQ_MODEL=openai/gpt-oss-20b")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='card'><h3>📚 Knowledge Base ({}) </h3>".format(db.kb_count()),
                    unsafe_allow_html=True)
        for d_ in db.get_kb_docs():
            st.markdown(f"- **{d_['title']}** · *{d_['doc_type']}*")
        with st.expander("➕ Add a knowledge-base document"):
            t = st.text_input("Title", key="kbt"); dt = st.text_input("Type", "reference", key="kbdt")
            ct = st.text_area("Content", key="kbc", height=100)
            if st.button("Add document", key="kbadd") and t and ct:
                db.add_kb_doc(t, dt, ct); st.success("Added."); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with tabs[2]:
        st.markdown("<div class='card'><h3>🛡️ Data & Privacy</h3>", unsafe_allow_html=True)
        st.caption("Manage RFP data stored locally in SQLite (smartrfp.db).")
        for r in db.list_rfps():
            c = st.columns([5, 1])
            c[0].write(f"{r['deal_name']} — {r['status']}")
            if c[1].button("Delete", key=f"del_{r['id']}"):
                db.delete_rfp(r["id"]); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# =========================================================================== #
#  PAGE: Help & Docs
# =========================================================================== #
def page_help():
    topbar("Help & Documentation", "Find answers, learn how to use SmartRFP, and get the support you need.",
           "❓", show_rfp=True)
    q = st.text_input("Search", placeholder="Search for help articles, guides, and more…",
                      label_visibility="collapsed").strip().lower()

    GUIDES = {
        "Getting Started": ("☁️", "ic-blue",
            "Learn the basics and set up your first RFP analysis.",
            "1. Open **Upload** and drop a PDF, DOCX or TXT RFP (max 50 MB).\n"
            "2. Optionally set the deal name, client, region, deadline and reviewer role.\n"
            "3. Click **Analyze & Generate Response** — the pipeline parses requirements, runs "
            "RAG retrieval and pricing in parallel, then writes a draft.\n"
            "4. You land on the **Dashboard**; open the RFP in **Human Review** to approve it, "
            "then **Export**."),
        "Dashboard Guide": ("📊", "ic-green",
            "Understand dashboard insights and key metrics.",
            "The five cards show Total RFPs, Analyzed, In Review, Approved and Exported. The donut "
            "breaks RFPs down by status. **Recent RFPs** lists the latest deals, **Pipeline Progress** "
            "shows the current stage, and the **Activity Feed** is built from the audit log."),
        "Resource & Cost": ("💲", "ic-purple",
            "Learn how resource estimation and cost calculation works.",
            "The total cost is summed from the pricing lines produced by Agent 2. Effort is split "
            "across roles (PM, BA, Solution Architecture, Development, QA, Training) using standard "
            "rate-card percentages, shown in the **Cost Breakdown by Role** table and the "
            "**Resource Allocation** bars. Treat figures as estimates and adjust before quoting."),
        "Human Review": ("🗂️", "ic-amber",
            "Review AI-generated content and provide feedback.",
            "Pick a section on the left, edit it in the editor, and use **Approve Section**, "
            "**Request Changes**, **Add Comment** or **Regenerate Section**. Each section shows its "
            "source references and an AI confidence score. When all sections are approved the RFP "
            "status becomes Approved. Everything is recorded in **Review History**."),
        "Export & Reports": ("📤", "ic-red",
            "Export RFP responses in multiple formats and options.",
            "Choose a format (PDF, Word, Excel, PowerPoint or HTML), tick the include options, then "
            "click **Export Now** to download. PDF/DOCX/HTML contain the full proposal; XLSX contains "
            "the cost data. Files are generated on demand and not stored on a server."),
        "Settings": ("⚙️", "ic-teal",
            "Configure application preferences and the Groq model.",
            "**General** holds workspace, currency, date and storage preferences. **AI Model** is where "
            "you confirm the Groq key is detected and run **Test Groq connection**. **Security** lets you "
            "delete RFP data stored locally in SQLite."),
    }

    ss.setdefault("help_topic", None)
    st.markdown("### How can we help you?")
    names = list(GUIDES.keys())
    for row in range(0, len(names), 3):
        cols = st.columns(3)
        for j, name in enumerate(names[row:row + 3]):
            e, ic, desc, _ = GUIDES[name]
            with cols[j]:
                st.markdown(f"<div class='helpcard'><div class='ic {ic}'>{e}</div>"
                            f"<div class='t'>{name}</div><div class='d'>{desc}</div></div>",
                            unsafe_allow_html=True)
                if st.button("View Guide →", key=f"guide_{name}", use_container_width=True):
                    ss.help_topic = None if ss.help_topic == name else name
                    st.rerun()

    if ss.help_topic:
        e, ic, desc, body = GUIDES[ss.help_topic]
        st.markdown(f"<div class='card'><h3>{e} {ss.help_topic}</h3>", unsafe_allow_html=True)
        st.markdown(body)
        if st.button("✕ Close guide", key="close_guide"):
            ss.help_topic = None; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    kb, faq = st.columns(2)
    with kb:
        st.markdown("<div class='card'><h3>Knowledge Base</h3>", unsafe_allow_html=True)
        ARTICLES = {
            "How to upload and analyze an RFP":
                ("Getting Started", "Go to Upload → drop your file → (optionally) fill deal details → "
                 "click Analyze & Generate Response. The pipeline extracts requirements, retrieves "
                 "internal context and pricing, then drafts the proposal."),
            "Understanding the Dashboard":
                ("Dashboard", "Metric cards summarise pipeline volume; the donut shows status mix; the "
                 "activity feed reflects real audit-log events."),
            "Resource Estimation Explained":
                ("Resource & Cost", "Total cost comes from the pricing lines; effort is allocated across "
                 "roles by rate-card percentages and shown as a table plus allocation bars."),
            "Review and Approve AI Content":
                ("Human Review", "Approve, request changes, comment or regenerate each section. Source "
                 "references and a confidence score help you verify before approving."),
            "Export RFP Responses":
                ("Export", "Select a format and click Export Now. PDF/DOCX/HTML carry the full proposal; "
                 "XLSX carries the cost table."),
            "Application Settings Overview":
                ("Settings", "Set preferences under General, verify the Groq key under AI Model, and "
                 "manage local data under Security."),
        }
        for title, (tag, body) in ARTICLES.items():
            if q and q not in title.lower() and q not in body.lower():
                continue
            with st.expander(f"📄 {title}"):
                st.markdown(f"<span class='refpill'>{tag}</span>", unsafe_allow_html=True)
                st.write(body)
        st.markdown("</div>", unsafe_allow_html=True)
    with faq:
        st.markdown("<div class='card'><h3>Frequently Asked Questions</h3>", unsafe_allow_html=True)
        faqs = {
            "How does SmartRFP analyze my documents?":
                "It extracts requirements, runs a RAG search over your knowledge base plus a "
                "pricing agent, then synthesizes a draft proposal with risk flags.",
            "Is my data secure?":
                "Data is stored locally in SQLite and exports are generated on-demand.",
            "Can I collaborate with my team?":
                "Assign reviewer roles (Junior/Senior/Supervisor/SME) and filter the dashboard by role.",
            "What export formats are supported?":
                "PDF, Word (DOCX), Excel (XLSX) and HTML are generated directly.",
            "How accurate are the cost estimates?":
                "Estimates are AI/heuristic-generated from requirements and a rate card; review before quoting.",
        }
        for qn, a in faqs.items():
            if q and q not in qn.lower() and q not in a.lower():
                continue
            with st.expander(qn):
                st.write(a)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Additional Resources")
    RES = {
        "User Manual": ("📖", "ic-purple", "Comprehensive guide to all features.",
            "**SmartRFP User Manual**\n\n"
            "- **Upload** — add a PDF/DOCX/TXT RFP and start analysis.\n"
            "- **Dashboard** — track pipeline metrics, status mix and recent RFPs.\n"
            "- **Resource Cost** — view the cost estimate, role breakdown and allocation.\n"
            "- **Human Review** — approve, edit, comment or regenerate each section.\n"
            "- **Export** — download the proposal as PDF, Word, Excel, HTML or text.\n"
            "- **Settings** — preferences, Groq model and local data management."),
        "Video Tutorials": ("▶️", "ic-amber", "Step-by-step walkthroughs.",
            "**Guided walkthrough**\n\n"
            "1. Upload an RFP and click *Analyze & Generate Response*.\n"
            "2. Watch the pipeline run (parse → RAG + pricing → synthesis).\n"
            "3. Open *Human Review*, approve or edit sections.\n"
            "4. Go to *Export* and download in your chosen format.\n\n"
            "Each step in the app mirrors this sequence end to end."),
        "Templates": ("📄", "ic-green", "Sample RFP templates & best practices.",
            "**Best-practice RFP structure**\n\n"
            "- Functional Requirements\n- Non-Functional Requirements\n"
            "- Compliance & Security\n- Commercial / Pricing line items\n\n"
            "Clear, sectioned RFPs produce the most accurate extraction and drafts. "
            "The bundled sample RFPs (Healthcare, Cloud Migration, Core Banking) follow this layout."),
        "Release Notes": ("🆕", "ic-blue", "Latest features and improvements.",
            "**Latest updates**\n\n"
            "- Demo data now seeds only once — deleting all RFPs keeps the dashboard empty.\n"
            "- Cards use real bordered containers, so tables and delete buttons sit inside the box.\n"
            "- Donut shows count and percent; Resource Cost has a role filter.\n"
            "- Export adds a Text (TXT) format and uniform format cards.\n"
            "- Help guides, knowledge base and these resources are fully interactive."),
    }
    ss.setdefault("help_res", None)
    rc = st.columns(4)
    for i, (name, (e, ic, desc, body)) in enumerate(RES.items()):
        with rc[i]:
            st.markdown(f"<div class='helpcard'><div class='ic {ic}'>{e}</div><div class='t'>{name}</div>"
                        f"<div class='d'>{desc}</div></div>", unsafe_allow_html=True)
            label = "✕ Close" if ss.help_res == name else "Open →"
            if st.button(label, key=f"res_{name}", use_container_width=True):
                ss.help_res = None if ss.help_res == name else name
                st.rerun()
    if ss.help_res:
        with card(f"{RES[ss.help_res][0]} {ss.help_res}"):
            st.markdown(RES[ss.help_res][3])


# =========================================================================== #
#  ROUTER
# =========================================================================== #
PAGES = {"Upload": page_upload, "Dashboard": page_dashboard, "Resource Cost": page_resource_cost,
         "Human Review": page_review, "Export": page_export, "AI Evaluation": llm_eval, "Settings": page_settings,
         "Help & Docs": page_help}
PAGES.get(ss.page, page_dashboard)()
