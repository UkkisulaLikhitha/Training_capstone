"""
config.py
---------
Central configuration for SmartRFP. Reads values from environment / .env file.

This loader is deliberately forgiving so the Groq key is picked up even with the
common Windows mistakes:
  * file saved by Notepad as `.env.txt` instead of `.env`
  * `.env` placed in the wrong folder (we also look next to this file)
  * the key typed into `.env.example` directly (used as a last resort)
A real environment variable (set in the shell) always takes precedence.
"""

import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Values that are placeholders, not real keys — treated as "no key".
_PLACEHOLDERS = {
    "", "gsk_your_key_here", "gsk_your_real_key_here", "your_key_here",
    "gsk_xxxxxxxxxxxxxxxxxxxx", "gsk_xxx", "changeme",
    "lsv2_pt_your_key_here",
    "lsv2_pt_xxxxxxxxx",
}


def _candidate_env_paths():
    """Files we will try to load, in priority order."""
    names_real = [".env", ".env.txt", ".env.local"]
    dirs = [BASE_DIR, os.getcwd()]
    paths = []
    for d in dirs:
        for n in names_real:
            paths.append(os.path.join(d, n))
    # last resort: the example file, in case the key was typed there directly
    for d in dirs:
        paths.append(os.path.join(d, ".env.example"))
    # de-duplicate, keep order
    seen, out = set(), []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


# Load the first env file that exists (without overriding real shell vars).
ENV_FILE = ""
ENV_SEARCHED = []
for _p in _candidate_env_paths():
    exists = os.path.isfile(_p)
    ENV_SEARCHED.append((_p, exists))
    if exists and not ENV_FILE:
        load_dotenv(_p, override=False)
        ENV_FILE = _p


def _clean(value: str) -> str:
    """Strip whitespace and accidental surrounding quotes from an env value."""
    v = (value or "").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1].strip()
    return v


# ---- Paths -----------------------------------------------------------------
DB_PATH = os.path.join(BASE_DIR, "smartrfp.db")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

# ---- Groq LLM --------------------------------------------------------------
# Get a free key at https://console.groq.com/keys and put it in .env as:
#   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
GROQ_API_KEY = _clean(os.getenv("GROQ_API_KEY", ""))
if GROQ_API_KEY in _PLACEHOLDERS:
    GROQ_API_KEY = ""

# Model id. Groq rotates model availability, so this is configurable.
# Good current choices (June 2026): "openai/gpt-oss-20b" (fast, free tier),
# "openai/gpt-oss-120b" (higher quality), "qwen/qwen3.6-27b".
GROQ_MODEL = _clean(os.getenv("GROQ_MODEL", "")) or "openai/gpt-oss-20b"

#LangSmith integration
# ---- LangSmith -------------------------------------------------------------

LANGSMITH_API_KEY = _clean(os.getenv("LANGSMITH_API_KEY", ""))
if LANGSMITH_API_KEY in _PLACEHOLDERS:
    LANGSMITH_API_KEY = ""

LANGSMITH_PROJECT = (
    _clean(os.getenv("LANGSMITH_PROJECT", ""))
    or "SmartRFP"
)

LANGSMITH_ENDPOINT = (
    _clean(os.getenv("LANGSMITH_ENDPOINT", ""))
    or "https://api.smith.langchain.com"
)

LANGSMITH_TRACING = (
    _clean(os.getenv("LANGSMITH_TRACING", "true")).lower()
    == "true"
)

# ---- App constants ---------------------------------------------------------
APP_NAME = "SmartRFP"
APP_TAGLINE = "AI-Powered RFP Analysis & Proposal Intelligence"
MAX_UPLOAD_MB = 50
SUPPORTED_TYPES = ["pdf", "docx", "txt"]

REVIEWER_ROLES = ["Junior Reviewer", "Senior Reviewer", "Supervisor", "SME (Subject Matter Expert)"]
STATUSES = ["Uploaded", "Drafting", "In Review", "Approved", "Rejected"]
RAG_TOP_K = 3
