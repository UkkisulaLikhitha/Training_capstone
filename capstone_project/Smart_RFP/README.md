# SmartRFP — AI Document Processing System (RAG + Live Pricing + Human-in-the-Loop)

An end-to-end, runnable implementation of the SmartRFP architecture and PRD:
upload an RFP → parse requirements → two agents run in parallel (RAG retrieval +
live pricing) → synthesize a draft with flags → a human approves/edits/rejects →
export to **DOCX / PDF / TXT**.

Built with **Streamlit + Groq + SQLite** (instead of OpenAI + PostgreSQL).

---

## 1. What you get

| Page | What it does |
|------|--------------|
| **Upload** | File upload (PDF/DOCX/TXT) + client details + **one "Generate Response" button** that runs the whole pipeline |
| **Dashboard** | Metric cards + a table of all RFPs, filterable by **reviewer role** (Junior / Senior / Supervisor / SME) and status; "Open" any row |
| **Review** | Full RFP details — draft sections, sources, **compliance / hallucination / missing-info flags**, requirements, pricing table, audit log — with **Approve / Edit inline / Send back / Reject** (the human gate) |
| **Export** | Appears after approval → **Download DOCX / PDF / TXT** (real files) |
| **Settings** | Groq status, knowledge base management, delete RFPs |

---

## 2. How to run (5 steps)

> ⚠️ **Keep the folder structure intact.** Always unzip the provided `smartrfp.zip`
> and run from the unzipped `smartrfp/` folder. Do **not** copy the `.py` files out
> into a single flat folder — `agents/` and `utils/` are Python packages, and
> flattening them causes `ModuleNotFoundError: No module named 'utils'`.

```bash
# 1. Go into the project folder (the one containing app.py)
cd smartrfp

# 2. (recommended) create a virtual environment
python -m venv venv
# Windows:  venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (optional but recommended) add your Groq key
cp .env.example .env          # Windows: copy .env.example .env
#   then open .env and paste your key into GROQ_API_KEY=...

# 5. Launch the app
streamlit run app.py
```

Then open the URL it prints (usually http://localhost:8501).
Prometheus Metrics available at: http://localhost:8000/metrics

> **No Groq key?** The app still runs in **demo mode** — it produces deterministic,
> source-grounded drafts so you can see the full flow. Add a key any time for real
> LLM-written drafts; nothing else changes.

### Get a free Groq key
1. Go to https://console.groq.com/keys
2. Create a key (starts with `gsk_...`)
3. Paste it into `.env` as `GROQ_API_KEY=gsk_...`

> Groq rotates models. The default is `openai/gpt-oss-20b`. If you get a
> "model not found" error, open `.env`, set `GROQ_MODEL` to a current model from
> https://console.groq.com/docs/models (e.g. `openai/gpt-oss-120b`).

---

## 3. Try it end-to-end (no UI) — proves the backend works

```bash
python test_pipeline.py
```

This creates a sample RFP, runs the pipeline, prints requirements / draft sections /
flags / pricing, and writes `exports/acme_test.{txt,docx,pdf}`.

---

## 4. Project structure

```
smartrfp/
├── app.py                 # Streamlit UI (Upload, Dashboard, Resource Cost, Human Review, Export, Settings, Help & Docs)
├── pipeline.py            # Orchestrator: parse -> [RAG || Pricing] -> synthesize
├── llm.py                 # Groq wrapper + demo-mode fallback
├── config.py              # Settings (reads .env)
├── database.py            # SQLite schema + all CRUD
├── seed_data.py          # seeds the knowledge base
├── demo_seed.py          # seeds sample RFPs so the dashboard looks populated
├── test_pipeline.py       # End-to-end backend test
├── evaluation.py          # stores all evaluatiuon metrics
├── metrics.py          # computes application run metrics
├── requirements.txt
├── .env.example
├── agents/
│   ├── extractor.py       # F1  — RFP parser / requirement extractor
│   ├── rag_agent.py       # Agent 1 — RAG retrieval (TF-IDF cosine similarity)
│   ├── pricing_agent.py   # Agent 2 — live pricing / web intelligence (mock + Tavily hook)
│   └── draft_generator.py # F4  — synthesis + flagging
└── utils/
    ├── file_handler.py    # Extract & clean text from PDF/DOCX/TXT
    └── exporter.py        # DOCX / PDF / TXT export
```

The SQLite file `smartrfp.db` is created automatically on first launch.

---

## 5. How it maps to your architecture & PRD

| Your design | This project |
|-------------|--------------|
| Frontend (Streamlit) | `app.py` |
| Backend / business logic | `pipeline.py`, `database.py` |
| LLM (OpenAI → **Groq**) | `llm.py` |
| Orchestration (LangChain/LangGraph) | `pipeline.py` (`ThreadPoolExecutor` runs the two agents in parallel) |
| Agent 1 — RAG retrieval | `agents/rag_agent.py` |
| Agent 2 — Live web/pricing | `agents/pricing_agent.py` |
| Draft Generator (F4) | `agents/draft_generator.py` |
| Human-in-the-loop review | Review page in `app.py` |
| Vector DB (pgvector/FAISS) | TF-IDF retrieval (see note below) |
| Database (PostgreSQL → **SQLite**) | `database.py` |
| Export & audit trail (F6) | `utils/exporter.py` + `audit_log` table |

### Note on the "Vector DB"
Groq has no embeddings endpoint, and to keep the project **zero-setup** the RAG
agent uses **TF-IDF + cosine similarity** (scikit-learn) for relevance search.
It behaves the same way (retrieve the most relevant internal docs per requirement)
with no model downloads. To upgrade to true semantic embeddings, swap
`TfidfVectorizer` in `agents/rag_agent.py` for `sentence-transformers`
(`all-MiniLM-L6-v2`) — the function signature stays the same.

---

## 6. Safety behaviours from the PRD (already implemented)
- **Hallucination flag** — a draft claim (e.g. an SLA %) not found in any source is flagged.
- **Compliance flag** — compliance/data-residency content is flagged for SME confirmation.
- **Missing-info marker** — a requirement with no internal match is flagged, not faked.
- **Stale pricing** — pricing older than the current quarter is marked "STALE" and excluded from the total.
- **No export without approval** — the Export page blocks download until a human approves.
- **Audit trail** — every action (upload, parse, edit, approve, reject) is logged per RFP.

---

## 7. Troubleshooting
- **`ModuleNotFoundError: No module named 'utils'` (or `'agents'`)** → you're running
  from a folder where the `utils/` and `agents/` subfolders are missing or got
  flattened. Unzip `smartrfp.zip` fresh and run `streamlit run app.py` from inside
  the resulting `smartrfp/` folder so the package folders sit next to `app.py`.
- **`'source' is not recognized…` (Windows)** → use `venv\Scripts\activate`, not
  `source venv/bin/activate` (that's macOS/Linux syntax).
- **`streamlit: command not found`** → activate your venv, or run `python -m streamlit run app.py`.
- **Groq "model not found"** → update `GROQ_MODEL` in `.env` (see §2).
- **Legacy `.doc` upload fails** → convert to `.docx`, `.pdf`, or `.txt` first.
- **Want a clean slate** → delete `smartrfp.db` and restart.
```
