"""
agents/draft_generator.py  (Feature F4 - Draft Generator / synthesis)
--------------------------------------------------------------------
Combines Agent 1 (internal RAG context) + Agent 2 (pricing/web) into a
structured proposal draft that mirrors a real RFP response document, using the
same section structure as the reference proposal:

    Executive Summary
    Company Overview
    Understanding of Requirements
    Proposed Technical Solution
    Implementation Plan
    Security
    Deliverables
    Timeline
    Pricing
    Conclusion

Prose sections are written by the LLM (grounded in retrieved context); the
structural sections (Implementation Plan, Deliverables, Timeline) use clean
deterministic content so the output always looks right, even in demo mode.
Each section carries the reviewer safety flags (compliance / hallucination /
missing-info) from the PRD.
"""

import re
from llm import chat
from langsmith import traceable

# --------------------------------------------------------------------------- #
#  Prompts
# --------------------------------------------------------------------------- #
SYSTEM = (
    "You are a senior bid writer producing a formal, client-facing proposal in "
    "response to an enterprise RFP. Write in confident, professional prose using "
    "ONLY the supplied context. Do NOT invent specific numbers, SLAs, percentages "
    "or certifications that are not present in the context."
)
P_EXEC = ("Write a polished Executive Summary (4-6 sentences) describing how the "
          "vendor will deliver a secure, scalable, compliant solution for this RFP.")
P_OVERVIEW = ("Write a short Company Overview (3-4 sentences) describing the vendor's "
              "relevant expertise and delivery track record for this type of engagement. "
              "Do not invent client names or awards.")
P_TECH = ("Write a 'Proposed Technical Solution' section: one short intro sentence, then "
          "5-8 concrete solution components or approaches as markdown bullets using '- '. "
          "Ground them in the context provided.")
P_SECURITY = ("Write a 'Security' section: one short intro sentence, then 4-6 markdown "
              "bullets ('- ') covering security and compliance measures (standards, access "
              "control, encryption, monitoring) grounded in the context.")
P_CONCLUSION = ("Write a short Conclusion (3-4 sentences) thanking the client for the "
                "opportunity and summarising why the vendor is a strong, low-risk partner.")

RISKY_CLAIM = re.compile(r"\b(\d{2,3}\.\d{1,2}\s*%|99\.9\d*%|SLA|guarantee|certified|"
                         r"ISO\s?\d+|SOC\s?2)\b", re.IGNORECASE)
COMPLIANCE_TERMS = re.compile(r"\b(complian|data residency|data-residency|regulation|gdpr|"
                              r"certif|security|privacy|audit)\b", re.IGNORECASE)


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _ctx(docs):
    if not docs:
        return "(no matching internal document found)"
    return "\n\n".join(f"[{d['title']} | {d['doc_type']}] {d['content']}" for d in docs)

@traceable(
    name="LLM Prompt",
    run_type="prompt",
)
def _ask(prompt, context, max_tokens=420, temperature=0.4):
    user = f"CONTEXT:\n{context}\n\n{prompt}"
    return chat(SYSTEM, user, temperature=temperature, max_tokens=max_tokens).strip()


def _flag(content, has_sources):
    if not has_sources:
        return ("missing", "No matching internal document found for this section.", "low")
    risky = RISKY_CLAIM.findall(content or "")
    if risky:
        return ("hallucination",
                f"Claim {risky[0]!r} is not grounded in a source document. Verify before sending.",
                "low")
    if COMPLIANCE_TERMS.search(content or ""):
        return ("compliance",
                "Compliance/security content auto-drafted; an SME should confirm it matches "
                "this client's region and requirements.", "medium")
    return (None, None, "high")

def _sec(
    title,
    content,
    source,
    flag=(None,None,"high"),
    retrieved_docs=None,
    prompt_context="",
    requirement=None,
):
    return {
        "section_title": title,
        "content": content,
        "source": source,

        "retrieved_docs": retrieved_docs or [],
        "prompt_context": prompt_context,
        "requirement": requirement,

        "flag_type": flag[0],
        "flag_note": flag[1],
        "confidence": flag[2],
    }

# --------------------------------------------------------------------------- #
#  Main
# --------------------------------------------------------------------------- #
@traceable(
    name="Draft Generator",
    run_type="chain",
)
def generate_draft(requirements, rag_agent, pricing_lines, web_insight=None,
                   max_sections=12):
    
    print(">>> generate_draft entered")
    print(type(generate_draft))
    print(generate_draft)
    sections = []
    all_reqs = "\n".join(f"- {r['text']}" for r in requirements[:14]) or "(no requirements parsed)"

    # ---- Executive Summary ------------------------------------------------ #
    sections.append(_sec("Executive Summary",
                         _ask(P_EXEC, all_reqs, max_tokens=320),
                         "Synthesised from RFP requirements", (None, None, "medium")))

    # ---- Company Overview ------------------------------------------------- #
    sections.append(_sec("Company Overview",
                         _ask(P_OVERVIEW, all_reqs, max_tokens=240),
                         "Synthesised", (None, None, "medium")))

    # ---- Understanding of Requirements (deterministic recap) -------------- #
    bullets = "\n".join(f"- {r['text']}" for r in requirements[:max_sections]) \
        or "- Requirements will appear here once an RFP is analysed."
    sections.append(_sec("Understanding of Requirements",
                         "Based on the RFP, we understand the project requires the following:\n\n"
                         + bullets,
                         "RFP (parsed by Extractor)", (None, None, "high")))

    # ---- Proposed Technical Solution (LLM, grounded) ---------------------- #
    tech_query = "technical solution architecture platform"

    tech_ctx = rag_agent.retrieve(tech_query)

    tech = _ask(P_TECH, _ctx(tech_ctx), max_tokens=460)

    sections.append(
        _sec(
            "Proposed Technical Solution",
            tech,
            ", ".join(d["title"] for d in tech_ctx) if tech_ctx else "Synthesised",
            _flag(tech, bool(tech_ctx)),
            retrieved_docs=tech_ctx,
            prompt_context=_ctx(tech_ctx),
            requirement="technical solution architecture platform"
        )
    )

    # ---- Implementation Plan (deterministic, phased) ---------------------- #
    plan = ("Our delivery follows a structured, phased approach to minimise risk:\n\n"
            "- **Phase 1 — Assessment & Discovery**\n"
            "- **Phase 2 — Solution & Migration Planning**\n"
            "- **Phase 3 — Environment / Infrastructure Setup**\n"
            "- **Phase 4 — Build & Data / Application Migration**\n"
            "- **Phase 5 — Integration & Configuration**\n"
            "- **Phase 6 — Testing & Quality Assurance**\n"
            "- **Phase 7 — Go Live & Handover**")
    sections.append(_sec("Implementation Plan", plan, "Standard delivery methodology"))

    # ---- Security (LLM, grounded, compliance-flagged) --------------------- #
    sec_ctx = rag_agent.retrieve("security compliance data protection certification")
    security = _ask(P_SECURITY, _ctx(sec_ctx), max_tokens=420)
    sflag = _flag(security, bool(sec_ctx))
    if sflag[0] is None:
        sflag = ("compliance", "Security content should be confirmed by an SME for this client.",
                 "medium")
    sections.append(_sec("Security", security,
                         ", ".join(d["title"] for d in sec_ctx) if sec_ctx else "Synthesised",
                         sflag))

    # ---- Deliverables (deterministic) ------------------------------------- #
    sections.append(_sec("Deliverables",
                         "The engagement will produce the following deliverables:\n\n"
                         "- Solution Design & Architecture\n"
                         "- Implementation / Migration Scripts\n"
                         "- Test Plan & Test Report\n"
                         "- Training Documentation\n"
                         "- Deployment & Support Guide\n"
                         "- Final Proposal & Audit Trail",
                         "Standard deliverables"))

    # ---- Timeline (deterministic) ----------------------------------------- #
    sections.append(_sec("Timeline",
                         "The estimated delivery duration is approximately **16 weeks**:\n\n"
                         "- Week 1–2: Discovery & Assessment\n"
                         "- Week 3–5: Infrastructure / Setup\n"
                         "- Week 6–10: Build & Migration\n"
                         "- Week 11–14: Testing & QA\n"
                         "- Week 15–16: Go Live & Handover",
                         "Estimated schedule"))

    # ---- Pricing (from Agent 2) ------------------------------------------- #
    if pricing_lines:
        total = sum(l["total"] for l in pricing_lines if not l["stale"])
        any_stale = any(l["stale"] for l in pricing_lines)
        body = (f"Our itemised commercial proposal is summarised below.\n\n"
                f"**Total Estimated Cost: ${total:,.0f}** (excluding any stale lines), "
                f"based on current pricing and valid for 90 days. The full line-item "
                f"breakdown is available in the pricing table.")
        flag = ("compliance", "One or more pricing lines are stale; refresh before the "
                "commercial table is finalised.", "low") if any_stale else (None, None, "high")
        sections.append(_sec("Pricing", body, "Agent 2 · Live Pricing", flag))
    else:
        sections.append(_sec("Pricing",
                             "Pricing will be itemised here once the pricing agent has run.",
                             "Agent 2 · Live Pricing"))

    # ---- Optional live web insight ---------------------------------------- #
    if web_insight:
        sections.append(_sec("Market / Web Insight (live)", web_insight,
                             "Agent 2 · Web Search", (None, None, "medium")))

    # ---- Conclusion ------------------------------------------------------- #
    sections.append(_sec("Conclusion", _ask(P_CONCLUSION, all_reqs, max_tokens=220),
                         "Synthesised", (None, None, "medium")))

    return sections
