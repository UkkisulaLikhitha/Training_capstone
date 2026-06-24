---
name: incident-postmortem
description: Generate blameless, consistently formatted production incident post-mortems (RCAs / incident retrospectives) for SRE/DevOps teams. Use this skill whenever the user wants to write up an incident, outage, or production issue, including phrases like "write a post-mortem", "do an RCA", "incident retrospective", "review this outage", or whenever they share an incident timeline and want it turned into a report. Computes exact timing metrics (TTD, TTA, TTM, TTR, customer-impact duration), classifies severity, and enforces blameless language and trackable action items.
---

# Incident Post-Mortem Generator

Turns an incident timeline into a blameless post-mortem. Hand-written ones are
inconsistent: miscomputed metrics, missing sections, blameful language, untrackable
action items. This skill makes the output uniform and the metrics exact.

## Workflow
1. Get a timeline of events. The phases that drive metrics are: incident_start,
   detected, acknowledged, mitigated, resolved.
2. Normalize to JSON: each entry is
   {"ts": "<ISO-8601 UTC>", "type": "<event type>", "note": "<what happened>"}.
3. Compute metrics with the script, never by hand:
   python scripts/incident_metrics.py <incident.json> --pretty
   Use the returned numbers verbatim; surface any warnings to the user.
4. Classify severity: the script gives a hint, but pick the most severe level any
   factor justifies (blast radius, data, security, revenue path), not just duration.
   SEV1 outage/data loss/security; SEV2 major or revenue-path (checkout/payments);
   SEV3 minor; SEV4 cosmetic.
5. Write the report with these sections: Summary, Impact, Timeline, Key metrics,
   Root cause, What went well, What went poorly, Action items.

## Blameless rules (non-negotiable)
- Describe systems and conditions, not culprits ("the deploy lacked an alarm", not
  "Priya forgot the alarm"). Prefer roles over names.
- No blame/shame/hindsight ("should have known", "careless").
- Root cause is a chain of contributing factors, rarely a single human error.

## Action-item rules
Every action item must be specific, owned, dated, and tracked, tagged with a type
(prevent / detect / mitigate / process).
- Bad: "Be more careful with deploys."
- Good: "Add a connection-pool-exhaustion alarm (prevent, owner: Checkout, due: 2026-06-30, PAGE-1183)."
