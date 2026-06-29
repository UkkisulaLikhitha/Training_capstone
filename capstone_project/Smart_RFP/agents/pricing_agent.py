"""
agents/pricing_agent.py  (Agent 2 - Live Pricing & Cost Intelligence)
--------------------------------------------------------------------
The PRD describes Agent 2 as fetching live pricing/cost data at draft time and
flagging stale numbers instead of inventing them (Scenario B).

This implementation returns deterministic, timestamped pricing derived from the
RFP content so the whole pipeline runs with NO external API key. It also
demonstrates the "stale price" safety flag from the PRD.

Hooks for real data:
  * Set TAVILY_API_KEY in .env to additionally pull a live web insight (optional).
  * Replace _mock_pricing() with calls to your real pricing REST APIs.
"""

import os
import random
from datetime import datetime, timedelta
from langsmith import traceable

from metrics import (
    PRICING_REQUESTS,
    PRICING_ITEMS,
)

# A tiny rate card used to build a realistic, deterministic estimate.
RATE_CARD = {
    "cloud":      ("Compute / Cloud SKU (x12)", 12, 17833.0, "pricing-api"),
    "migration":  ("Migration Labor (480 hrs)", 480, 400.0, "pricing-api"),
    "security":   ("Security Hardening Package", 1, 38500.0, "pricing-api"),
    "support":    ("Managed Support (12 mo)", 12, 4200.0, "pricing-api"),
    "data":       ("Data Platform Setup", 1, 64000.0, "pricing-api"),
    "license":    ("Software Licenses (annual)", 1, 52000.0, "pricing-api"),
}
DEFAULT_LINE = ("Professional Services (est.)", 1, 45000.0, "pricing-api")


def _keywords_in(text: str):
    t = (text or "").lower()
    return [k for k in RATE_CARD if k in t]

@traceable(
    name="Pricing Engine",
    run_type="tool",
)
def _mock_pricing(rfp_text: str):
    """Build pricing lines based on keywords found in the RFP text."""
    now = datetime.now()
    keys = _keywords_in(rfp_text) or []
    lines = []

    chosen = keys[:4] if keys else []
    if not chosen:
        # nothing matched -> at least give a base estimate line
        item, qty, unit, src = DEFAULT_LINE
        lines.append(_line(item, qty, unit, src, now, stale=False))
    else:
        for i, k in enumerate(chosen):
            item, qty, unit, src = RATE_CARD[k]
            # Deterministically mark ONE line as stale to demonstrate the flag
            stale = (i == len(chosen) - 1 and len(chosen) >= 2)
            lines.append(_line(item, qty, unit, src, now, stale=stale))

    # Add a margin line (18%) computed on the subtotal of non-stale items
    subtotal = sum(l["total"] for l in lines if not l["stale"])
    margin = round(subtotal * 0.18, 2)
    lines.append(_line("Margin (18%)", "-", margin, "pricing-api", now, stale=False,
                       precomputed_total=margin))
    return lines


def _line(item, qty, unit_price, source, now, stale=False, precomputed_total=None):
    if stale:
        fetched = (now - timedelta(days=95)).strftime("%d %b %Y")  # last quarter
    else:
        fetched = now.strftime("%d %b %Y")
    qty_num = qty if isinstance(qty, (int, float)) else 1
    total = precomputed_total if precomputed_total is not None else round(unit_price * qty_num, 2)
    return {
        "item": item,
        "qty": str(qty),
        "unit_price": float(unit_price),
        "total": float(total),
        "fetched_at": fetched,
        "source": source,
        "stale": bool(stale),
    }

@traceable(
    name="Pricing Web Search",
    run_type="tool",
)
def _optional_web_insight(rfp_text: str):
    """If TAVILY_API_KEY is set, fetch one live web insight. Otherwise return None."""
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key:
        return None
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=key)
        # very small query derived from the doc
        topic = " ".join(rfp_text.split()[:8])
        res = client.search(query=f"latest pricing trends {topic}", max_results=2)
        snippets = [r.get("content", "")[:200] for r in res.get("results", [])]
        return " | ".join(s for s in snippets if s)[:400] or None
    except Exception as e:
        print(f"[pricing] Tavily web insight failed: {e}")
        return None

@traceable(
    name="Pricing Agent",
    run_type="chain",
)
def fetch_pricing(rfp_text: str):
    PRICING_REQUESTS.inc()
    """
    Public entry point. Returns (pricing_lines, web_insight_or_None).
    """
    lines = _mock_pricing(rfp_text)
    insight = _optional_web_insight(rfp_text)
    PRICING_ITEMS.observe(len(lines))
    return lines, insight
