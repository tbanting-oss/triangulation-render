#!/usr/bin/env python3
"""
Converts workflow_dispatch input env vars (set by render-card.yml) into the
JSON payload render_card.py's --json flag expects.

Empty-string inputs are converted to None, not left as "" — this matters
because render_card.py's CardInput treats None as "pending, render an em
dash" (per the 24 Aug 2026 leg-status fix), while an empty string would be
treated as a truthy-but-blank value and likely render incorrectly.
"""
import json
import os


def get(name):
    v = os.environ.get(name, "")
    return v if v != "" else None


def get_float(name):
    v = get(name)
    return float(v) if v is not None else None


payload = {
    "vendor": os.environ["VENDOR"],
    "movement": get_float("MOVEMENT"),
    "visibility": get_float("VISIBILITY"),
    "proof": get_float("PROOF"),
    "tier": os.environ["TIER"],
    "pillar": get("PILLAR"),
    "confidence": get("CONFIDENCE"),
    "confidence_reason": get("CONFIDENCE_REASON"),
    "signal_url": get("SIGNAL_URL"),
    "signal_title": get("SIGNAL_TITLE"),
    "pr_summary_short": get("PR_SUMMARY_SHORT"),
}

with open("card_input.json", "w") as f:
    json.dump(payload, f, indent=2)

print(json.dumps(payload, indent=2))
