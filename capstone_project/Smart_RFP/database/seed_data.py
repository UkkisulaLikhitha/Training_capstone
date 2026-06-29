"""
seed_data.py
------------
Populates the internal knowledge base (the documents Agent 1 / RAG searches).
Run once:  python seed_data.py
It is also called automatically on first app launch if the KB is empty.

In a real deployment these would be your company's past winning proposals,
templates, compliance clauses, solution docs, product catalog, and case studies.
"""

from database import init_db, kb_count, add_kb_doc

SAMPLE_DOCS = [
    {
        "title": "Past Proposal - Contoso Cloud Migration 2025",
        "doc_type": "Past Proposal",
        "content": (
            "We propose a phased migration to a managed cloud platform with a 99.9% "
            "uptime SLA and 24/7 support. The migration is delivered in three phases: "
            "assessment, lift-and-shift of non-critical workloads, and modernization of "
            "core systems. A dedicated migration squad of 6 engineers handles cutover with "
            "zero-downtime strategies. Backups are taken before every cutover window."
        ),
    },
    {
        "title": "Solution Doc - Managed Kubernetes Platform",
        "doc_type": "Solution Doc",
        "content": (
            "Our managed Kubernetes offering provides automated scaling, rolling "
            "deployments, centralized logging, and role-based access control. We support "
            "blue-green and canary releases. Monitoring is provided through an integrated "
            "observability stack with alerting on latency, error rate, and saturation."
        ),
    },
    {
        "title": "Compliance Clause - Data Residency",
        "doc_type": "Compliance Clause",
        "content": (
            "Customer data will remain stored within the customer's specified region in "
            "compliance with local data-protection regulations. Data does not leave the "
            "region without explicit written consent. Encryption at rest (AES-256) and in "
            "transit (TLS 1.2+) is enforced for all customer data."
        ),
    },
    {
        "title": "Compliance Clause - Security Certifications",
        "doc_type": "Compliance Clause",
        "content": (
            "Our platform maintains ISO 27001 and SOC 2 Type II certifications. Annual "
            "third-party penetration testing is conducted. We provide audit logs, "
            "least-privilege access, and a documented incident-response process with a "
            "defined breach-notification timeline."
        ),
    },
    {
        "title": "Template - Support and SLA",
        "doc_type": "Template",
        "content": (
            "Standard support tiers: Bronze (business hours), Silver (extended hours), and "
            "Gold (24/7). Gold tier includes a 15-minute response target for critical "
            "incidents and a named technical account manager. Service credits apply if the "
            "monthly uptime falls below the committed SLA."
        ),
    },
    {
        "title": "Case Study - Initech Data Platform",
        "doc_type": "Case Study",
        "content": (
            "For Initech we delivered a unified data platform that reduced reporting time "
            "by 60% and consolidated 12 legacy databases into a single warehouse. The "
            "project finished two weeks ahead of schedule and within budget, and is cited "
            "as a reference for large data-modernization engagements."
        ),
    },
    {
        "title": "Product Catalog - Professional Services Rates",
        "doc_type": "Catalog",
        "content": (
            "Professional services are billed by role: Solution Architect, Senior Engineer, "
            "Engineer, and Project Manager. Engagements are scoped in sprints. Standard "
            "delivery methodology follows discovery, design, build, test, and hypercare "
            "phases with clear acceptance criteria at each gate."
        ),
    },
    {
        "title": "Template - Implementation Approach",
        "doc_type": "Template",
        "content": (
            "Our implementation approach is iterative and milestone-driven. We begin with a "
            "discovery workshop to confirm requirements, produce a solution design document, "
            "then deliver in two-week sprints with demos at the end of each sprint. A risk "
            "register and RAID log are maintained throughout the engagement."
        ),
    },
]


def seed():
    init_db()
    if kb_count() > 0:
        print(f"Knowledge base already has {kb_count()} documents. Skipping seed.")
        return
    for d in SAMPLE_DOCS:
        add_kb_doc(d["title"], d["doc_type"], d["content"])
    print(f"Seeded {len(SAMPLE_DOCS)} knowledge-base documents.")


if __name__ == "__main__":
    seed()
