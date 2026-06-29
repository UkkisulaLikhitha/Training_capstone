"""
agents/extractor.py  (Feature F1 - RFP Parser & Requirement Extractor)
---------------------------------------------------------------------
Turns the cleaned RFP text into a list of answerable requirements.

Two paths:
  1. If a Groq key is set, ask the LLM to extract structured requirements (JSON).
  2. Otherwise (or on failure), use a robust heuristic parser that splits the
     document and keeps requirement-like sentences (must / shall / should /
     required / questions / numbered items).

Either way you get: [{"section": "...", "text": "..."}, ...]
"""

import json
import re
from llm import chat, llm_available

REQUIREMENT_HINTS = re.compile(
    r"\b(must|shall|should|require|required|provide|describe|demonstrate|"
    r"support|comply|ensure|include|specify|how do you|what is your|"
    r"please describe|vendor)\b",
    re.IGNORECASE,
)

SECTION_HEADER = re.compile(r"^\s*(\d+(\.\d+)*)[\).]?\s+(.{3,80})$")


def _heuristic_extract(text: str, max_items: int = 40):
    requirements = []
    current_section = "General"
    # Split into candidate lines / sentences
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        # Detect a section header like "3.2 Security Requirements"
        m = SECTION_HEADER.match(line)
        if m and len(line.split()) <= 10:
            current_section = line
            continue

        # Break long lines into sentences
        sentences = re.split(r"(?<=[.?!])\s+", line)
        for s in sentences:
            s = s.strip()
            if len(s) < 15:
                continue
            if s.endswith("?") or REQUIREMENT_HINTS.search(s):
                requirements.append({"section": current_section, "text": s})
                if len(requirements) >= max_items:
                    return requirements

    # Fallback: if nothing matched, chunk the doc into pseudo-requirements
    if not requirements:
        chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if len(c.strip()) > 40]
        for i, ch in enumerate(chunks[:max_items], 1):
            requirements.append({"section": f"Section {i}", "text": ch[:300]})
    return requirements


def _llm_extract(text: str, max_items: int = 40):
    system = (
        "You are an RFP analyst. Extract the concrete requirements and questions "
        "a vendor must respond to. Return STRICT JSON only: a list of objects with "
        "keys 'section' and 'text'. No prose, no markdown fences."
    )
    user = (
        f"Extract up to {max_items} requirements from this RFP. "
        f"Group them by their section if visible.\n\nRFP TEXT:\n{text[:6000]}"
    )
    out = chat(system, user, temperature=0.0, max_tokens=1500)
    # Strip any accidental code fences
    out = out.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(out)
        cleaned = []
        for d in data:
            if isinstance(d, dict) and d.get("text"):
                cleaned.append({"section": str(d.get("section", "General")),
                                "text": str(d["text"])})
        return cleaned[:max_items] if cleaned else None
    except Exception:
        return None


def extract_requirements(text: str, max_items: int = 40):
    """Public entry point used by the pipeline."""
    if llm_available():
        result = _llm_extract(text, max_items)
        if result:
            return result
    # heuristic path (also the no-key default)
    return _heuristic_extract(text, max_items)
