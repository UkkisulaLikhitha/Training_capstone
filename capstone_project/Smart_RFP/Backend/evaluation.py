from statistics import mean
import llm
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CONFIDENCE_MAP = {
    "high": 1.0,
    "medium": 0.7,
    "low": 0.4,
}

EXPECTED_SECTIONS = {
    "Executive Summary",
    "Company Overview",
    "Understanding of Requirements",
    "Proposed Technical Solution",
    "Implementation Plan",
    "Security",
    "Deliverables",
    "Timeline",
    "Pricing",
    "Conclusion",
}


def evaluate_pipeline(
    requirements,
    sections,
    pricing_lines,
    runtime_seconds,
    rag_agent=None,
):
    """
    Compute deterministic evaluation metrics.
    """

    # ---------------- Completeness ----------------
    generated = {s["section_title"] for s in sections}

    proposal_completeness = round(
        len(generated & EXPECTED_SECTIONS) /
        len(EXPECTED_SECTIONS),
        2,
    )

    # ---------------- Confidence ----------------
    confidence_scores = [
        CONFIDENCE_MAP.get(
            s.get("confidence", "").lower(),
            0.4,
        )
        for s in sections
    ]

    average_confidence = round(
        mean(confidence_scores),
        2,
    ) if confidence_scores else 0

    # ---------------- Flags ----------------
    hallucination_flags = sum(
        1
        for s in sections
        if s.get("flag_type")
    )

    # ---------------- Context Coverage ----------------
    grounded = sum(
        1
        for s in sections
        if s.get("source")
        and s["source"] != "Synthesised"
    )

    context_coverage = round(
        grounded / len(sections),
        2,
    ) if sections else 0

    # ---------------- Pricing ----------------
    if pricing_lines:
        fresh = sum(
            1
            for p in pricing_lines
            if not p["stale"]
        )

        pricing_freshness = round(
            fresh / len(pricing_lines),
            2,
        )
    else:
        pricing_freshness = 0

    # ---------------- Additional Metrics ----------------
    kb_documents = len(rag_agent.docs) if rag_agent else 0

    pricing_items = len(pricing_lines)

    llm_demo_mode = llm.used_demo()

    llm_calls = 5          # Executive, Overview, Technical, Security, Conclusion

    def similarity(a, b):
        if not a or not b:
            return 0

        vect = TfidfVectorizer(stop_words="english")

        X = vect.fit_transform([a, b])

        return float(cosine_similarity(X[0], X[1])[0][0])

    faithfulness_scores = []

    for sec in sections:

        docs = sec.get("retrieved_docs", [])

        if not docs:
            continue

        context = " ".join(d["content"] for d in docs)

        faithfulness_scores.append(

            similarity(
                sec["content"],
                context,
            )

        )

    faithfulness = round(
        mean(faithfulness_scores),
        2,
    ) if faithfulness_scores else 0

    answer_scores = []

    for sec in sections:

        req = sec.get("requirement")

        if not req:
            continue

        answer_scores.append(

            similarity(
                req,
                sec["content"],
            )

        )

    answer_relevancy = round(
        mean(answer_scores),
        2,
    ) if answer_scores else 0

    precision_scores = []

    for sec in sections:

        docs = sec.get("retrieved_docs", [])

        if not docs:
            continue

        useful = 0

        for d in docs:

            if similarity(
                sec["content"],
                d["content"],
            ) > 0.30:

                useful += 1

        precision_scores.append(
            useful / len(docs)
        )

    context_precision = round(
        mean(precision_scores),
        2,
    ) if precision_scores else 0

    recall_scores = []

    for sec in sections:

        req = sec.get("requirement")

        docs = sec.get("retrieved_docs", [])

        if not docs:
            continue

        covered = 0

        for d in docs:

            if similarity(
                req,
                d["content"],
            ) > 0.30:

                covered += 1

        recall_scores.append(
            covered / len(docs)
        )

    context_recall = round(
        mean(recall_scores),
        2,
    ) if recall_scores else 0

    hits = []

    for sec in sections:

        docs = sec.get("retrieved_docs", [])

        hits.append(

            int(
                any(d["score"] > 0.30 for d in docs)
            )

        )

    hit_rate = round(
        mean(hits),
        2,
    )

    mrr_scores = []

    for sec in sections:

        docs = sec.get("retrieved_docs", [])

        rr = 0

        for rank, doc in enumerate(docs, 1):

            if doc["score"] > 0.30:

                rr = 1 / rank

                break

        mrr_scores.append(rr)

    mrr = round(
        mean(mrr_scores),
        2,
    )

    overlap = []

    for sec in sections:

        docs = sec.get("retrieved_docs", [])

        for i in range(len(docs)):

            for j in range(i + 1, len(docs)):

                overlap.append(

                    similarity(
                        docs[i]["content"],
                        docs[j]["content"],
                    )

                )

    chunk_overlap = round(
        mean(overlap),
        2,
    ) if overlap else 0

    return {
        "requirements": len(requirements),
        "sections_generated": len(sections),
        "proposal_completeness": proposal_completeness,
        "average_confidence": average_confidence,
        "context_coverage": context_coverage,
        "hallucination_flags": hallucination_flags,
        "pricing_freshness": pricing_freshness,
        "runtime_seconds": round(runtime_seconds, 2),
        "knowledge_documents": kb_documents,
        "pricing_items": pricing_items,
        "llm_calls": llm_calls,
        "demo_mode": llm_demo_mode,
        "faithfulness": faithfulness,
        "answer_relevancy": answer_relevancy,
        "context_precision": context_precision,
        "context_recall": context_recall,
        "mrr": mrr,
        "hit_rate": hit_rate,
        "chunk_overlap": chunk_overlap,
    }
