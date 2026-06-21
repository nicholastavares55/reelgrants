#!/usr/bin/env python3
"""
ReelGrants — Orchestrator (the Flock's heartbeat).

One command runs the whole crew on a schedule and reports up, escalating only
exceptions to a human:

    Sourcer/Verifier  -> re-check funder pages, queue anything uncertain
    Matcher + Alerter -> match every subscriber, compose the alerts now due
    Report            -> a single summary; the review queue is the only thing
                         that ever needs a human glance

Safety posture (why Nick can leave this running):
  * DRY-RUN by default — nothing is emailed and grants.json is never rewritten
    unless explicitly run --live with the required credentials present.
  * The Sourcer never auto-changes a *deadline*; date changes always wait in the
    review queue. The Alerter never sends the same alert twice.

Subscribers come from Supabase in production (the signups table) or a local sample
file for dry runs. Reading Supabase needs a SERVICE key (the public anon key is
insert-only by design), so live mode is gated on Nick providing that + an email key.

Usage:
    python3 run.py --test     # offline assertions
    python3 run.py            # full DRY-RUN cycle against sample subscribers
    python3 run.py --live     # real cycle (refuses unless creds are set)
"""
import json, sys, os, datetime
from pathlib import Path
import match, alert, refresh

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"
SUBS_SAMPLE = ENGINE / "subscribers.sample.json"
TODAY = match.TODAY

DISCIPLINE_NORM = {
    "documentary": "documentary", "narrative": "narrative", "fiction": "narrative",
    "screenwriting": "screenwriting", "short film": "short", "short": "short",
    "animation": "animation", "emerging/identity-based": "emerging",
    "general/creator": "general/creator",
}


def normalize_subscriber(raw):
    """Map a signup row (email + single discipline) to a match-engine profile."""
    disc = (raw.get("discipline") or "").strip()
    key = DISCIPLINE_NORM.get(disc.lower(), disc.lower())
    return {
        "email": raw["email"],
        "name": raw.get("name"),
        "disciplines": [key] if key else [],
        "region": raw.get("region"),
    }


def load_subscribers(live=False):
    """Supabase in live mode (service key required); sample file otherwise."""
    if live:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not (url and key):
            raise RuntimeError(
                "live mode needs SUPABASE_URL + SUPABASE_SERVICE_KEY (anon key is "
                "insert-only). Set them or run a dry cycle.")
        import urllib.request
        req = urllib.request.Request(
            f"{url.rstrip('/')}/rest/v1/signups?select=email,discipline",
            headers={"apikey": key, "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=15) as r:
            rows = json.loads(r.read())
        return [normalize_subscriber(x) for x in rows]
    raw = json.loads(SUBS_SAMPLE.read_text())
    return [normalize_subscriber(x) for x in raw]


def build_send_fn(live):
    """Return a real email sender for --live, or None for dry-run."""
    if not live:
        return None
    key = os.environ.get("RESEND_API_KEY")
    sender = os.environ.get("ALERT_FROM", "alerts@reelgrants.app")
    if not key:
        raise RuntimeError("live mode needs RESEND_API_KEY (+ a verified ALERT_FROM).")
    import urllib.request

    def send(email):
        payload = json.dumps({"from": sender, "to": [email["to"]],
                              "subject": email["subject"], "text": email["body"]}).encode()
        req = urllib.request.Request("https://api.resend.com/emails", data=payload,
                                     headers={"Authorization": f"Bearer {key}",
                                              "Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15).read()
    return send


def flock_run(live=False, do_refresh=True, today=TODAY, fetch_fn=None):
    grants = match.load_grants()
    out = {"ran_at": str(today), "mode": "LIVE" if live else "DRY-RUN", "grants_tracked": len(grants)}

    # --- Sourcer/Verifier ---
    if do_refresh:
        sources = json.loads((ROOT / "sources.json").read_text())["sources"]
        srep = refresh.run(sources, fetch_fn=fetch_fn or refresh.http_fetch, today=today)
        out["sourcer"] = {"checked": srep["checked"], "keep": srep["keep"],
                          "auto_close": srep["auto_close"], "flagged": srep["flag"],
                          "needs_review": [q["name"] for q in srep["queue"]]}

    # --- Matcher + Alerter ---
    subs = load_subscribers(live=live)
    sent = alert.load_sent_log() if live else set()
    outbox, new_sent = alert.run(subs, grants, sent=sent, today=today,
                                 send_fn=build_send_fn(live), persist=live)
    out["alerter"] = {"subscribers": len(subs), "emails": len(outbox),
                      "recipients": [m["to"] for m in outbox]}
    out["_outbox"] = outbox
    return out


def print_report(out):
    print(f"=== ReelGrants Flock · {out['mode']} · {out['ran_at']} ===")
    print(f"Grants tracked: {out['grants_tracked']}")
    if "sourcer" in out:
        s = out["sourcer"]
        print(f"Sourcer: checked {s['checked']} · keep {s['keep']} · "
              f"auto-close {s['auto_close']} · flagged {s['flagged']}")
        if s["needs_review"]:
            print("  needs review: " + ", ".join(s["needs_review"][:8]))
    a = out["alerter"]
    print(f"Alerter: {len(a['recipients'])} email(s) for {a['subscribers']} subscriber(s)")
    for m in out["_outbox"]:
        print(f"  → {m['to']}: {m['subject']}")


# ----------------------------- tests -----------------------------
def run_tests():
    # normalization maps a signup row to a usable profile
    p = normalize_subscriber({"email": "a@b.com", "discipline": "Documentary", "region": "Texas"})
    assert p["disciplines"] == ["documentary"] and p["region"] == "Texas"

    # full dry cycle with an offline Sourcer fetcher (no network) produces a report,
    # composes alerts, and sends NOTHING / rewrites nothing.
    out = flock_run(live=False, fetch_fn=lambda u: "")  # empty pages -> all flag unreachable
    assert out["mode"] == "DRY-RUN"
    assert out["alerter"]["subscribers"] == 5, "should load the 5 sample subscribers"
    assert out["alerter"]["emails"] >= 1, "sample doc/screenwriter should get alerts"
    assert out["sourcer"]["checked"] >= 1
    # dry run must never persist a sent-log
    before = alert.load_sent_log()
    flock_run(live=False, fetch_fn=lambda u: "")
    assert alert.load_sent_log() == before, "dry-run must not persist sent-log"

    # live mode without creds must refuse, loudly, rather than half-run
    try:
        load_subscribers(live=True)
        assert False, "live load should refuse without creds"
    except RuntimeError as e:
        assert "SUPABASE" in str(e)
    print("All Orchestrator tests passed ✓")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_tests()
    else:
        live = "--live" in sys.argv
        print_report(flock_run(live=live))
