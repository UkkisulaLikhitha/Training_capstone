from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    REGISTRY,
)

def _metric(factory, name, description):
    """
    Create metric if it doesn't exist.
    Otherwise return the already-registered metric.
    """
    try:
        return factory(name, description)
    except ValueError:
        return REGISTRY._names_to_collectors[name]


# -------------------------------------------------------
# Pipeline Metrics
# -------------------------------------------------------

PIPELINE_RUNS = _metric(
    Counter,
    "smartrfp_pipeline_runs_total",
    "Total pipeline executions"
)

PIPELINE_FAILURES = _metric(
    Counter,
    "smartrfp_pipeline_failures_total",
    "Failed pipeline executions"
)

PIPELINE_RUNTIME = _metric(
    Histogram,
    "smartrfp_pipeline_runtime_seconds",
    "Pipeline execution time"
)

# -------------------------------------------------------
# LLM Metrics
# -------------------------------------------------------

LLM_REQUESTS = _metric(
    Counter,
    "smartrfp_llm_requests_total",
    "Total LLM requests"
)

LLM_ERRORS = _metric(
    Counter,
    "smartrfp_llm_errors_total",
    "Total LLM failures"
)

LLM_LATENCY = _metric(
    Histogram,
    "smartrfp_llm_latency_seconds",
    "LLM response time"
)

LLM_DEMO_MODE = _metric(
    Counter,
    "smartrfp_demo_mode_total",
    "Fallback demo responses"
)

# -------------------------------------------------------
# RAG Metrics
# -------------------------------------------------------

RAG_QUERIES = _metric(
    Counter,
    "smartrfp_rag_queries_total",
    "Total retrieval requests"
)

RAG_RESULTS = _metric(
    Histogram,
    "smartrfp_rag_results",
    "Documents returned by retrieval"
)

RAG_EMPTY = _metric(
    Counter,
    "smartrfp_rag_empty_total",
    "Queries returning no KB documents"
)

# -------------------------------------------------------
# Pricing Metrics
# -------------------------------------------------------

PRICING_REQUESTS = _metric(
    Counter,
    "smartrfp_pricing_requests_total",
    "Pricing agent requests"
)

PRICING_ITEMS = _metric(
    Histogram,
    "smartrfp_pricing_items",
    "Pricing items returned"
)

# -------------------------------------------------------
# Proposal Metrics
# -------------------------------------------------------

REQUIREMENTS_EXTRACTED = _metric(
    Histogram,
    "smartrfp_requirements_extracted",
    "Requirements extracted from RFP"
)

SECTIONS_GENERATED = _metric(
    Histogram,
    "smartrfp_sections_generated",
    "Proposal sections generated"
)

HALLUCINATION_FLAGS = _metric(
    Gauge,
    "smartrfp_hallucination_flags",
    "Number of hallucination flags"
)