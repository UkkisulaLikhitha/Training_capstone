#!/usr/bin/env python3
"""Deterministic incident-timeline analyzer. Computes TTD/TTA/TTM/TTR exactly."""
import argparse, json, sys
from datetime import datetime, timezone

PHASES = ["incident_start", "detected", "acknowledged", "mitigated", "resolved"]
SEV_HINT = [(240, "SEV1"), (60, "SEV2"), (15, "SEV3")]  # minutes of customer impact

def parse_ts(raw):
    dt = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)

def human(sec):
    if sec is None: return None
    sec = int(round(sec)); h, rem = divmod(abs(sec), 3600); m, s = divmod(rem, 60)
    p = [f"{h}h"] if h else []
    if m: p.append(f"{m}m")
    if s and not h: p.append(f"{s}s")
    return ("-" if sec < 0 else "") + (" ".join(p) if p else "0m")

def diff(ph, a, b):
    return (ph[b] - ph[a]).total_seconds() if a in ph and b in ph else None

def compute(data):
    ph = {}
    for e in data["timeline"]:
        t = e.get("type")
        if t not in PHASES: continue
        if t in ph: raise ValueError(f"duplicate '{t}' event")
        ph[t] = parse_ts(e["ts"])
    warnings, present = [], [e for e in PHASES if e in ph]
    for a, b in zip(present, present[1:]):
        if ph[a] > ph[b]: warnings.append(f"'{b}' occurs before '{a}'")
    for req in ("detected", "mitigated"):
        if req not in ph: warnings.append(f"missing '{req}' event")
    start, end = ph.get("incident_start", ph.get("detected")), ph.get("mitigated")
    impact = (end - start).total_seconds() if start and end else None
    metrics = {
        "ttd": diff(ph, "incident_start", "detected"),
        "tta": diff(ph, "detected", "acknowledged"),
        "ttm": diff(ph, "detected", "mitigated"),
        "ttr": diff(ph, "detected", "resolved"),
        "customer_impact": impact,
    }
    sev = "SEV4"
    if impact is not None:
        for thr, s in SEV_HINT:
            if impact / 60 >= thr: sev = s; break
    return {
        "incident_id": data.get("incident_id"), "title": data.get("title"),
        "metrics_human": {k: human(v) for k, v in metrics.items()},
        "severity_hint": sev, "warnings": warnings,
    }

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("incident_file"); ap.add_argument("--pretty", action="store_true")
    a = ap.parse_args(argv)
    try:
        with open(a.incident_file) as fh: data = json.load(fh)
        out = compute(data)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr); return 1
    print(json.dumps(out, indent=2 if a.pretty else None)); return 0

if __name__ == "__main__":
    raise SystemExit(main())
