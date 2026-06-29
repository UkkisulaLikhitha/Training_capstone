"""
demo_seed.py
------------
Populates a few sample RFPs the first time the app runs so the Dashboard,
Resource Cost, Human Review and Export pages look populated (like the design
mockups) instead of empty. Runs only when there are zero RFPs. You can delete
these any time from Settings → Manage RFPs.
"""

from datetime import datetime, timedelta
import database as db

# (deal, client, region, status, role, num_req, num_flags, days_ago)
_DEMO = [
    ("Healthcare RFP", "ABC Healthcare", "US", "In Review", "Supervisor", 7, 3, 0),
    ("Core Banking RFP", "Global Bank", "EU", "Drafting", "Senior Reviewer", 9, 2, 1),
    ("Cloud Migration RFP", "Tech Solutions", "North America", "Approved", "SME (Subject Matter Expert)", 8, 1, 2),
    ("Data Analytics RFP", "DataCorp", "US", "Drafting", "Junior Reviewer", 6, 2, 3),
    ("Security Services RFP", "Secure Ltd.", "UK", "In Review", "Senior Reviewer", 10, 4, 4),
    ("ERP Modernization RFP", "Initech", "US", "Approved", "Supervisor", 8, 1, 6),
    ("Network Upgrade RFP", "Umbrella Inc.", "EU", "Rejected", "Junior Reviewer", 5, 3, 8),
]

_SECTIONS = [
    ("Executive Summary",
     "Thank you for the opportunity to submit this proposal. We propose a secure, "
     "scalable and compliant solution that directly addresses the stated requirements "
     "while minimising business disruption and improving availability and long-term "
     "scalability.", "Synthesised", None, "medium"),
    ("Company Overview",
     "Our team specialises in enterprise solution delivery across healthcare, finance "
     "and government sectors, with a proven track record of secure, on-time delivery.",
     "Synthesised", None, "medium"),
    ("Understanding of Requirements",
     "Based on the RFP, we understand the project requires a phased delivery with strong "
     "security and compliance, integration with existing systems, and an itemised "
     "commercial proposal.", "RFP (parsed)", None, "high"),
    ("Proposed Technical Solution",
     "We propose a managed, cloud-native platform tailored to the requirements:\n\n"
     "- Scalable application and compute tier\n"
     "- Managed database with automated backup\n"
     "- Monitoring and centralised logging\n"
     "- Identity and access management\n"
     "- Disaster recovery and high availability",
     "Solution Doc - Managed Platform", None, "high"),
    ("Implementation Plan",
     "Our delivery follows a structured, phased approach:\n\n"
     "- **Phase 1 — Assessment & Discovery**\n"
     "- **Phase 2 — Solution & Migration Planning**\n"
     "- **Phase 3 — Environment / Infrastructure Setup**\n"
     "- **Phase 4 — Build & Migration**\n"
     "- **Phase 5 — Integration & Configuration**\n"
     "- **Phase 6 — Testing & QA**\n"
     "- **Phase 7 — Go Live & Handover**",
     "Standard delivery methodology", None, "high"),
    ("Security",
     "The proposed solution follows industry best practice:\n\n"
     "- ISO 27001 aligned controls\n"
     "- Encryption at rest and in transit\n"
     "- Role-based access control (RBAC)\n"
     "- Multi-factor authentication (MFA)\n"
     "- Continuous monitoring and audit logging",
     "Compliance Clause - Security Certifications", "compliance", "medium"),
    ("Deliverables",
     "The engagement will produce the following deliverables:\n\n"
     "- Solution Design & Architecture\n"
     "- Implementation / Migration Scripts\n"
     "- Test Plan & Test Report\n"
     "- Training Documentation\n"
     "- Deployment & Support Guide\n"
     "- Final Proposal & Audit Trail",
     "Standard deliverables", None, "high"),
    ("Timeline",
     "The estimated delivery duration is approximately **16 weeks**:\n\n"
     "- Week 1–2: Discovery & Assessment\n"
     "- Week 3–5: Infrastructure / Setup\n"
     "- Week 6–10: Build & Migration\n"
     "- Week 11–14: Testing & QA\n"
     "- Week 15–16: Go Live & Handover",
     "Estimated schedule", None, "high"),
    ("Pricing",
     "Our itemised commercial proposal is summarised in the pricing table.\n\n"
     "**Total Estimated Cost** is shown on the Resource Cost page and is valid for 90 days.",
     "Agent 2 · Live Pricing", None, "high"),
    ("Conclusion",
     "We appreciate the opportunity to partner with you. Our solution provides a secure, "
     "scalable and future-ready platform aligned with your business objectives.",
     "Synthesised", None, "medium"),
]

_PRICING = [
    ("Managed Compute (12 VMs)", "12", 1800.0, 21600.0, False),
    ("Managed Kubernetes Cluster", "1", 24000.0, 24000.0, False),
    ("Professional Services (480 hrs)", "480", 180.0, 86400.0, False),
    ("Managed Support (12 mo)", "12", 4200.0, 50400.0, False),
    ("Software Licenses (annual)", "1", 52000.0, 52000.0, True),
]


def _meta_get(conn, key):
    conn.execute("CREATE TABLE IF NOT EXISTS app_meta (k TEXT PRIMARY KEY, v TEXT)")
    row = conn.execute("SELECT v FROM app_meta WHERE k=?", (key,)).fetchone()
    return row[0] if row else None


def _meta_set(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO app_meta (k, v) VALUES (?, ?)", (key, str(value)))
    conn.commit()


def seed_demo_rfps():
    # Seed the sample RFPs exactly once. After that, never re-seed — so when the
    # user deletes every RFP (including the last one) the dashboard stays empty.
    conn = db.get_conn()
    if _meta_get(conn, "demo_seeded"):
        conn.close()
        return False
    if db.list_rfps():            # data from an older build: mark as seeded, don't duplicate
        _meta_set(conn, "demo_seeded", 1)
        conn.close()
        return False
    _meta_set(conn, "demo_seeded", 1)
    conn.close()

    now = datetime.now()
    for (deal, client, region, status, role, nreq, nflag, days) in _DEMO:
        rid = db.create_rfp(deal, client, region,
                            (now + timedelta(days=20)).strftime("%Y-%m-%d"),
                            "", "", deal.replace(" ", "_") + ".pdf",
                            "Sample RFP text for demo purposes.", role, "", True)
        db.update_rfp_metrics(rid, nreq, nflag, status)
        # backdate timestamps so "Last Updated" looks realistic
        ts = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        conn = db.get_conn()
        conn.execute("UPDATE rfps SET created_at=?, updated_at=? WHERE id=?",
                     (ts, ts, rid))
        conn.commit()
        conn.close()
        # sections + pricing so Review/Export/Resource pages are populated
        db.save_draft_sections(rid, [
            {"section_title": t, "content": c, "source": s,
             "flag_type": f, "flag_note": None, "confidence": conf}
            for (t, c, s, f, conf) in _SECTIONS])
        db.save_pricing(rid, [
            {"item": i, "qty": q, "unit_price": u, "total": tot,
             "fetched_at": ts.split(" ")[0], "source": "Demo rate card", "stale": st}
            for (i, q, u, tot, st) in _PRICING])
        db.save_requirements(rid, [{"section": "Functional", "text": f"Requirement {n+1}"}
                                   for n in range(nreq)])
        db.log_action(rid, "Uploaded", role, deal)
        if status in ("In Review", "Approved", "Rejected"):
            db.log_action(rid, "Analysis completed", "SmartRFP")
        if status == "Approved":
            db.log_action(rid, "Approved", role)
            db.log_action(rid, "Exported", role)
    return True


if __name__ == "__main__":
    db.init_db()
    print("Seeded demo RFPs." if seed_demo_rfps() else "RFPs already exist; skipped.")
