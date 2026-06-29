"""
database.py
-----------
All SQLite access lives here. Plain sqlite3 (no ORM) to keep dependencies light
and the code easy to read for a capstone review.

Tables
  rfps           -> one row per uploaded RFP + client details + status + metrics
  requirements   -> extracted requirements per RFP (from F1 parser)
  draft_sections -> generated draft sections + sources + flags (from F4)
  pricing        -> live/mock pricing line items (from Agent 2)
  knowledge_base -> internal documents the RAG agent searches (Agent 1)
  audit_log      -> who did what, when (human-in-the-loop trail)
"""

import sqlite3
from datetime import datetime
from config import DB_PATH

def get_conn():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False,
    )

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")

    return conn

def init_db():
    """Create all tables if they do not already exist."""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS rfps (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_name       TEXT NOT NULL,
            client_name     TEXT,
            region          TEXT,
            deadline        TEXT,
            contact_email   TEXT,
            notes           TEXT,
            file_name       TEXT,
            raw_text        TEXT,
            status          TEXT DEFAULT 'Uploaded',
            assigned_role   TEXT,
            assigned_to     TEXT,
            num_requirements INTEGER DEFAULT 0,
            num_flags       INTEGER DEFAULT 0,
            use_web_search  INTEGER DEFAULT 1,
            created_at      TEXT,
            updated_at      TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS requirements (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            rfp_id    INTEGER,
            section   TEXT,
            text      TEXT,
            FOREIGN KEY (rfp_id) REFERENCES rfps(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS draft_sections (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            rfp_id        INTEGER,
            section_title TEXT,
            content       TEXT,
            source        TEXT,
            flag_type     TEXT,      -- 'compliance' | 'hallucination' | 'missing' | NULL
            flag_note     TEXT,
            confidence    TEXT,
            FOREIGN KEY (rfp_id) REFERENCES rfps(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pricing (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            rfp_id     INTEGER,
            item       TEXT,
            qty        TEXT,
            unit_price REAL,
            total      REAL,
            fetched_at TEXT,
            source     TEXT,
            stale      INTEGER DEFAULT 0,
            FOREIGN KEY (rfp_id) REFERENCES rfps(id)
        )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS evaluation_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rfp_id INTEGER,
        proposal_completeness REAL,
        average_confidence REAL,
        context_coverage REAL,
        hallucination_flags INTEGER,
        pricing_freshness REAL,
        sections_generated INTEGER,
        requirements_extracted INTEGER,
        evaluated_at TEXT,
        runtime_seconds REAL,
        knowledge_documents INTEGER,
        pricing_items INTEGER,
        llm_calls INTEGER,
        demo_mode INTEGER,
        faithfulness REAL,
        answer_relevancy REAL,
        context_precision REAL,
        context_recall REAL,
        mrr REAL,
        hit_rate REAL,
        chunk_overlap REAL,
        FOREIGN KEY (rfp_id) REFERENCES rfps(id)
)
""")

    c.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            title    TEXT,
            doc_type TEXT,
            content  TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            rfp_id    INTEGER,
            action    TEXT,
            actor     TEXT,
            detail    TEXT,
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()


# --------------------------------------------------------------------------- #
#  RFP CRUD
# --------------------------------------------------------------------------- #
def create_rfp(deal_name, client_name, region, deadline, contact_email,
               notes, file_name, raw_text, assigned_role, assigned_to,
               use_web_search):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO rfps (deal_name, client_name, region, deadline, contact_email,
                          notes, file_name, raw_text, status, assigned_role,
                          assigned_to, use_web_search, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (deal_name, client_name, region, deadline, contact_email, notes,
          file_name, raw_text, "Drafting", assigned_role, assigned_to,
          1 if use_web_search else 0, now, now))
    rfp_id = cur.lastrowid
    conn.commit()
    conn.close()
    return rfp_id


def update_rfp_metrics(rfp_id, num_requirements, num_flags, status):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_conn()
    conn.execute("""
        UPDATE rfps SET num_requirements=?, num_flags=?, status=?, updated_at=?
        WHERE id=?
    """, (num_requirements, num_flags, status, now, rfp_id))
    conn.commit()
    conn.close()


def update_rfp_status(rfp_id, status):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_conn()
    conn.execute("UPDATE rfps SET status=?, updated_at=? WHERE id=?",
                 (status, now, rfp_id))
    conn.commit()
    conn.close()


def update_rfp_assignment(rfp_id, assigned_role, assigned_to):
    conn = get_conn()
    conn.execute("UPDATE rfps SET assigned_role=?, assigned_to=? WHERE id=?",
                 (assigned_role, assigned_to, rfp_id))
    conn.commit()
    conn.close()


def get_rfp(rfp_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM rfps WHERE id=?", (rfp_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_rfps():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM rfps ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_rfp(rfp_id):
    conn = get_conn()
    for t in ("requirements", "draft_sections", "pricing", "evaluation_metrics", "audit_log"):
        conn.execute(f"DELETE FROM {t} WHERE rfp_id=?", (rfp_id,))
    conn.execute("DELETE FROM rfps WHERE id=?", (rfp_id,))
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------- #
#  Requirements
# --------------------------------------------------------------------------- #
def save_requirements(rfp_id, requirements):
    conn = get_conn()
    conn.execute("DELETE FROM requirements WHERE rfp_id=?", (rfp_id,))
    for r in requirements:
        conn.execute("INSERT INTO requirements (rfp_id, section, text) VALUES (?,?,?)",
                     (rfp_id, r.get("section", ""), r.get("text", "")))
    conn.commit()
    conn.close()


def get_requirements(rfp_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM requirements WHERE rfp_id=?", (rfp_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
#  Draft sections
# --------------------------------------------------------------------------- #
def save_draft_sections(rfp_id, sections):
    conn = get_conn()
    conn.execute("DELETE FROM draft_sections WHERE rfp_id=?", (rfp_id,))
    for s in sections:
        conn.execute("""
            INSERT INTO draft_sections
              (rfp_id, section_title, content, source, flag_type, flag_note, confidence)
            VALUES (?,?,?,?,?,?,?)
        """, (rfp_id, s.get("section_title"), s.get("content"), s.get("source"),
              s.get("flag_type"), s.get("flag_note"), s.get("confidence")))
    conn.commit()
    conn.close()


def get_draft_sections(rfp_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM draft_sections WHERE rfp_id=?", (rfp_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_draft_section(section_id, content):
    conn = get_conn()
    conn.execute("UPDATE draft_sections SET content=? WHERE id=?", (content, section_id))
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------- #
#  Pricing
# --------------------------------------------------------------------------- #
def save_pricing(rfp_id, items):
    conn = get_conn()
    conn.execute("DELETE FROM pricing WHERE rfp_id=?", (rfp_id,))
    for p in items:
        conn.execute("""
            INSERT INTO pricing (rfp_id, item, qty, unit_price, total, fetched_at, source, stale)
            VALUES (?,?,?,?,?,?,?,?)
        """, (rfp_id, p["item"], p["qty"], p["unit_price"], p["total"],
              p["fetched_at"], p["source"], 1 if p.get("stale") else 0))
    conn.commit()
    conn.close()


def get_pricing(rfp_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM pricing WHERE rfp_id=?", (rfp_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Evaluation Metrics
def save_evaluation_metrics(rfp_id, metrics):
    """
    Store evaluation metrics for an RFP.
    """

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    conn = get_conn()

    conn.execute(
        "DELETE FROM evaluation_metrics WHERE rfp_id=?",
        (rfp_id,),
    )

    conn.execute("""
        INSERT INTO evaluation_metrics (
            rfp_id,
            proposal_completeness,
            average_confidence,
            context_coverage,
            hallucination_flags,
            pricing_freshness,
            sections_generated,
            requirements_extracted,
            runtime_seconds,
            knowledge_documents,
            pricing_items,
            llm_calls,
            demo_mode,
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
            mrr,
            hit_rate,
            chunk_overlap,
            evaluated_at
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", 
        (
        rfp_id,
        metrics["proposal_completeness"],
        metrics["average_confidence"],
        metrics["context_coverage"],
        metrics["hallucination_flags"],
        metrics["pricing_freshness"],
        metrics["sections_generated"],
        metrics["requirements"],
        metrics["runtime_seconds"],
        metrics["knowledge_documents"],
        metrics["pricing_items"],
        metrics["llm_calls"],
        1 if metrics["demo_mode"] else 0,
        metrics["faithfulness"],
        metrics["answer_relevancy"],
        metrics["context_precision"],
        metrics["context_recall"],
        metrics["mrr"],
        metrics["hit_rate"],
        metrics["chunk_overlap"],
        now
    ))

    conn.commit()
    conn.close()

def get_evaluation_metrics(rfp_id):
    conn = get_conn()

    row = conn.execute(
        """
        SELECT *
        FROM evaluation_metrics
        WHERE rfp_id=?
        """,
        (rfp_id,),
    ).fetchone()

    conn.close()

    return dict(row) if row else None



# --------------------------------------------------------------------------- #
#  Knowledge base (Agent 1 searches this)
# --------------------------------------------------------------------------- #
def add_kb_doc(title, doc_type, content):
    conn = get_conn()
    conn.execute("INSERT INTO knowledge_base (title, doc_type, content) VALUES (?,?,?)",
                 (title, doc_type, content))
    conn.commit()
    conn.close()


def get_kb_docs():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM knowledge_base").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def kb_count():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) AS n FROM knowledge_base").fetchone()["n"]
    conn.close()
    return n


# --------------------------------------------------------------------------- #
#  Audit log
# --------------------------------------------------------------------------- #
def log_action(rfp_id, action, actor, detail=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_conn()
    conn.execute("""
        INSERT INTO audit_log (rfp_id, action, actor, detail, timestamp)
        VALUES (?,?,?,?,?)
    """, (rfp_id, action, actor, detail, now))
    conn.commit()
    conn.close()


def get_audit_log(rfp_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM audit_log WHERE rfp_id=? ORDER BY id DESC",
                        (rfp_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
