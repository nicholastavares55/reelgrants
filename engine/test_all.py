#!/usr/bin/env python3
"""
ReelGrants engine — full regression suite.

Runs every Flock worker's offline assertions in one shot, plus a couple of
cross-cutting integration + data-integrity checks. No network, no accounts.
This is the durable, reusable safety net: green here means the paid core,
the verifier, the alerter, and the orchestrator all still behave.

    python3 test_all.py
"""
import sys, json, datetime
from pathlib import Path
import match, refresh, alert, run

ROOT = Path(__file__).resolve().parent.parent


def section(label, fn):
    try:
        fn()
        print(f"  ✓ {label}")
        return True
    except AssertionError as e:
        print(f"  ✗ {label}: {e}")
        return False
    except Exception as e:
        print(f"  ✗ {label}: {type(e).__name__}: {e}")
        return False


def data_integrity():
    """grants.json must stay well-formed: required fields, valid dates, real urls."""
    grants = json.loads((ROOT / "grants.json").read_text())["grants"]
    assert len(grants) >= 49, f"expected >=49 funds, got {len(grants)}"
    seen = set()
    for g in grants:
        for f in ("name", "funder", "category", "deadline", "status", "url"):
            assert g.get(f), f"{g.get('name','?')} missing {f}"
        assert g["url"].startswith("http"), f"{g['name']} has a bad url"
        assert g["name"] not in seen, f"duplicate fund: {g['name']}"
        seen.add(g["name"])
        d, hard = match.parse_deadline(g["deadline"])
        if hard:  # any hard date must be a real calendar date
            assert isinstance(d, datetime.date)


def sources_cover_grants():
    """Every fund must have a watch entry in sources.json (so nothing goes unmonitored)."""
    grants = {g["name"] for g in json.loads((ROOT / "grants.json").read_text())["grants"]}
    sources = {s["name"] for s in json.loads((ROOT / "sources.json").read_text())["sources"]}
    missing = grants - sources
    assert not missing, f"funds with no source watch: {missing}"


def integration_no_double_alert():
    """End-to-end: running the alerter twice never double-sends."""
    grants = match.load_grants()
    subs = run.load_subscribers(live=False)
    box1, sent1 = alert.run(subs, grants, sent=set())
    box2, _ = alert.run(subs, grants, sent=sent1)
    assert box1, "first cycle should produce alerts"
    assert box2 == [], "second cycle must be silent (no duplicate alerts)"


def main():
    print("ReelGrants engine — full regression suite\n")
    results = []
    print("Unit:")
    results.append(section("matcher (match.py)", match.run_tests))
    results.append(section("sourcer/verifier (refresh.py)", refresh.run_tests))
    results.append(section("alerter (alert.py)", alert.run_tests))
    results.append(section("orchestrator (run.py)", run.run_tests))
    print("Integration & data:")
    results.append(section("data integrity (grants.json)", data_integrity))
    results.append(section("source coverage", sources_cover_grants))
    results.append(section("no double-alerts (end-to-end)", integration_no_double_alert))

    passed = sum(results)
    print(f"\n{passed}/{len(results)} suites passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
