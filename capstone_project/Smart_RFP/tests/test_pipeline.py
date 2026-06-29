"""
test_pipeline.py
----------------
Proves the whole backend works WITHOUT the Streamlit UI and WITHOUT a Groq key
(it runs in demo mode). Run:  python test_pipeline.py
"""

import os
from database import init_db, create_rfp, get_rfp, get_requirements, get_draft_sections, get_pricing
from seed_data import seed
from pipeline import run_pipeline
from utils.exporter import export_txt, export_docx, export_pdf

SAMPLE_RFP = """
Acme Cloud Migration — Request for Proposal RFP-2026-118

1. Solution Overview
1.1 The vendor must describe a phased approach to migrate our on-premise workloads
to a managed cloud platform with minimal downtime.
1.2 Vendor shall provide a 24/7 support model and describe the uptime SLA offered.

2. Security & Compliance
2.1 Vendor must comply with data residency requirements; customer data shall remain
in North America.
2.2 Describe your security certifications and audit process.

3. Data Platform
3.1 The vendor should provide a data platform that consolidates legacy databases.

4. Commercials
4.1 Provide a detailed pricing breakdown including migration labor and licenses.
"""


def main():
    init_db()
    seed()

    rfp_id = create_rfp(
        deal_name="Acme Cloud Migration — RFP-2026-118",
        client_name="Acme Corp",
        region="North America",
        deadline="10 Jul 2026",
        contact_email="bids@acme.com",
        notes="Test run",
        file_name="acme.txt",
        raw_text=SAMPLE_RFP,
        assigned_role="Senior Reviewer",
        assigned_to="Priya S.",
        use_web_search=True,
    )
    print(f"Created RFP id={rfp_id}")

    def prog(label, frac):
        print(f"  [{int(frac*100):3d}%] {label}")

    summary = run_pipeline(rfp_id, SAMPLE_RFP, use_web_search=True, progress=prog)
    print("\nPipeline summary:", summary)

    print("\n--- Requirements ---")
    for r in get_requirements(rfp_id)[:5]:
        print(f"  [{r['section']}] {r['text'][:70]}")

    print("\n--- Draft sections ---")
    for s in get_draft_sections(rfp_id):
        flag = f"  <FLAG: {s['flag_type']}>" if s['flag_type'] else ""
        print(f"  • {s['section_title'][:60]}{flag}")
        print(f"      {s['content'][:90]}...")
        print(f"      source: {s['source']}")

    print("\n--- Pricing ---")
    for p in get_pricing(rfp_id):
        stale = " STALE" if p['stale'] else ""
        print(f"  {p['item']:<32} ${p['total']:>12,.2f}  ({p['fetched_at']}){stale}")

    print("\n--- Exporting ---")
    os.makedirs("exports", exist_ok=True)
    for ext, fn in (("txt", export_txt), ("docx", export_docx), ("pdf", export_pdf)):
        data = fn(rfp_id)
        path = f"exports/acme_test.{ext}"
        with open(path, "wb") as f:
            f.write(data)
        print(f"  wrote {path}  ({len(data):,} bytes)")

    print("\nALL GOOD ✓")


if __name__ == "__main__":
    main()
