"""
pipeline.py
-----------
The orchestration layer (the "LangGraph" role in the PRD diagram, implemented
plainly so it is easy to follow):

    parse (F1)  ->  [ Agent 1 RAG  ||  Agent 2 Pricing ]  ->  synthesize (F4)

It runs the two agents in parallel with a thread pool, then synthesizes the draft
and persists everything to SQLite. A progress callback lets the UI show steps.
"""

from concurrent.futures import ThreadPoolExecutor

from agents.extractor import extract_requirements
from agents.rag_agent import RAGAgent
from agents.pricing_agent import fetch_pricing
from agents.draft_generator import generate_draft
import database as db

from langsmith import traceable, trace
from evaluation import evaluate_pipeline

import time

from metrics import (
    PIPELINE_RUNS,
    PIPELINE_FAILURES,
    PIPELINE_RUNTIME,
    REQUIREMENTS_EXTRACTED,
    SECTIONS_GENERATED,
    HALLUCINATION_FLAGS,
)

@traceable(
    name="SmartRFP Pipeline",
    run_type="chain",
)
def run_pipeline(rfp_id, raw_text, use_web_search=True, progress=None):
    try:
        PIPELINE_RUNS.inc()
        start_time = time.perf_counter()

        """
        Execute the full end-to-end flow for one RFP.
        `progress` is an optional callable(step_label, fraction) for UI updates.
        Returns a summary dict.
        """
        def step(label, frac):
            if progress:
                progress(label, frac)

        # ---- F1: parse & extract requirements ---------------------------------
        step("Parsing & extracting requirements (F1)…", 0.15)
        with trace(
        "Requirement Extraction",
        run_type="chain"):
            requirements = extract_requirements(raw_text)
        db.save_requirements(rfp_id, requirements)
        db.log_action(rfp_id, "Parsed", "System",
                      f"{len(requirements)} requirements extracted")

        # ---- F2 + F3: run both agents in PARALLEL ------------------------------
        step("Running Agent 1 (RAG) and Agent 2 (Pricing) in parallel…", 0.45)
        with trace(
        "Parallel Agent Execution",
        run_type="chain"):
            rag_agent = RAGAgent()

            with ThreadPoolExecutor(max_workers=2) as ex:
                # Agent 2 (pricing/web) runs in its own thread
                pricing_future = ex.submit(fetch_pricing, raw_text)
                # Agent 1 is initialized above; retrieval happens during synthesis.
                pricing_lines, web_insight = pricing_future.result()

        if not use_web_search:
            web_insight = None

        db.save_pricing(rfp_id, pricing_lines)
        db.log_action(rfp_id, "Agents run", "System",
                      f"RAG over {len(rag_agent.docs)} KB docs; "
                      f"{len(pricing_lines)} pricing lines fetched")

        # ---- F4: synthesize the draft -----------------------------------------
        step("Synthesizing draft (F4)…", 0.8)
        with trace(
        "Draft Generation",
        run_type="chain"):
            sections = generate_draft(requirements, rag_agent, pricing_lines, web_insight)
        db.save_draft_sections(rfp_id, sections)

        # ---------------- Evaluation ----------------
        runtime = time.perf_counter() - start_time
        evaluation = evaluate_pipeline(
            requirements=requirements,
            sections=sections,
            pricing_lines=pricing_lines,
            runtime_seconds=runtime,
            rag_agent=rag_agent,
        )

        db.save_evaluation_metrics(
            rfp_id,
            evaluation,
        )

        num_flags = evaluation["hallucination_flags"]

        db.update_rfp_metrics(rfp_id, len(requirements), num_flags, "In Review")
        db.log_action(rfp_id, "Draft generated", "System",
                      f"{len(sections)} sections, {num_flags} flags")

        step("Done.", 1.0)
        elapsed = time.perf_counter() - start_time

        PIPELINE_RUNTIME.observe(elapsed)

        REQUIREMENTS_EXTRACTED.observe(len(requirements))

        SECTIONS_GENERATED.observe(len(sections))

        HALLUCINATION_FLAGS.set(num_flags)
        return {
        "requirements": len(requirements),
        "sections": len(sections),
        "flags": num_flags,
        "pricing_lines": len(pricing_lines),
        "web_insight": bool(web_insight),
        "evaluation": evaluation
        }
    except Exception:
        PIPELINE_FAILURES.inc()
        raise