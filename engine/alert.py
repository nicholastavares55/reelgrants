#!/usr/bin/env python3
"""
ReelGrants — Alerter agent (the Flock worker subscribers actually pay for).

Turns "grants you qualify for" into the two emails that make the product worth money:

  1. OPENED  — "A grant you qualify for just opened: <name>" (sent once, when it first
               shows as open/rolling for that subscriber)
  2. NUDGE   — deadline countdowns at 14, 3, and 1 days before close

The whole value is *not annoying people*: every alert is de-duped via a persistent
sent-log, so a subscriber never gets the same opened/nudge twice. Sending is injectable
(send_fn) — DRY-RUN by default (composes, never sends). Going live just means passing a
real send_fn (Resend/SMTP) once Nick approves email credentials.

Usage:
    python3 alert.py --test         # offline assertions
    python3 alert.py                # dry-run demo against engine/subscribers.sample.json
"""
import json, sys, datetime
from pathlib import Path
import match  # reuse the proven matching core

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"
SENT_LOG_PATH = ENGINE / "sent_log.json"
SUBS_SAMPLE = ENGINE / "subscribers.sample.json"
NUDGE_DAYS = [14, 3, 1]
TODAY = match.TODAY


def load_sent_log(path=SENT_LOG_PATH):
    if Path(path).exists():
        return set(json.loads(Path(path).read_text()))
    return set()


def save_sent_log(keys, path=SENT_LOG_PATH):
    Path(path).write_text(json.dumps(sorted(keys), indent=2))


def due_alerts(sub, grants, sent, today=TODAY):
    """Return the alert events newly due for one subscriber (respecting the sent-log)."""
    matched = match.match_for(sub, grants)
    events = []
    for g in matched:
        gid = g["name"]
        dl = g.get("_days_left")
        # 1) opened — fire once when first matched as actionable
        if g.get("status") in ("open", "rolling"):
            key = f'{sub["email"]}|{gid}|opened'
            if key not in sent:
                events.append({"key": key, "type": "opened", "grant": g})
        # 2) deadline nudges at each threshold the deadline has reached
        if dl is not None and dl >= 0:
            for t in sorted(NUDGE_DAYS):  # ascending -> the tightest threshold crossed wins
                if dl <= t:
                    key = f'{sub["email"]}|{gid}|nudge{t}'
                    if key not in sent:
                        events.append({"key": key, "type": f"nudge{t}",
                                       "grant": g, "days_left": dl})
                    break  # stop at the tightest crossed threshold, sent or not —
                           # never fall through to a looser nudge
    return events


def compose(sub, events):
    """Build the actual email a subscriber receives. Returns {to, subject, body}."""
    name = sub.get("name") or sub["email"].split("@")[0]
    opened = [e for e in events if e["type"] == "opened"]
    nudges = [e for e in events if e["type"].startswith("nudge")]
    if opened and not nudges:
        subject = (f"🎬 A grant you qualify for just opened: {opened[0]['grant']['name']}"
                   if len(opened) == 1 else f"🎬 {len(opened)} new grants you qualify for")
    elif nudges:
        tightest = min(e["days_left"] for e in nudges)
        subject = f"⏰ {tightest} day{'s' if tightest != 1 else ''} left: a grant you qualify for is closing"
    else:
        subject = "ReelGrants update"

    lines = [f"Hi {name},", ""]
    if opened:
        lines.append("Just opened — and it fits what you make:")
        for e in opened:
            g = e["grant"]
            lines.append(f"  • {g['name']} ({g['funder']}) — {g['award_amount']}")
            lines.append(f"    {'; '.join(g['_reasons'])}")
            lines.append(f"    Apply: {g['url']}")
        lines.append("")
    if nudges:
        lines.append("Closing soon — don't miss these:")
        for e in sorted(nudges, key=lambda x: x["days_left"]):
            g = e["grant"]
            lines.append(f"  • {g['name']} ({g['funder']}) — closes in {e['days_left']} day(s)")
            lines.append(f"    Apply: {g['url']}")
        lines.append("")
    lines.append("— ReelGrants · we watch so you don't miss it")
    lines.append("Manage alerts or unsubscribe: https://nicholastavares55.github.io/reelgrants/")
    return {"to": sub["email"], "subject": subject, "body": "\n".join(lines)}


def run(subscribers, grants, sent=None, today=TODAY, send_fn=None, persist=False):
    """Compose (and optionally send) all due alerts. Returns the list of emails.

    send_fn=None  -> DRY RUN (nothing leaves the building)
    send_fn set   -> live; only keys that send successfully are marked sent
    """
    sent = set(sent) if sent is not None else set()
    outbox = []
    for sub in subscribers:
        events = due_alerts(sub, grants, sent, today)
        if not events:
            continue
        email = compose(sub, events)
        delivered = True
        if send_fn is not None:
            try:
                send_fn(email)
            except Exception as e:
                delivered = False
                email["error"] = str(e)
        if delivered:
            for e in events:
                sent.add(e["key"])
        email["_event_keys"] = [e["key"] for e in events]
        outbox.append(email)
    if persist and send_fn is not None:
        save_sent_log(sent)
    return outbox, sent


# ----------------------------- tests -----------------------------
def run_tests():
    grants = match.load_grants()
    subs = [{"name": "Maya", "email": "maya@test.com", "disciplines": ["documentary"], "region": "California"}]

    # fresh run -> some alerts, including at least one "opened"
    outbox, sent = run(subs, grants, sent=set())
    assert outbox, "a doc filmmaker should get at least one alert on first run"
    assert any(k.endswith("opened") for k in sent), "should fire an 'opened' alert"

    # idempotency: same inputs + accumulated sent-log -> no duplicate emails
    outbox2, sent2 = run(subs, grants, sent=sent)
    assert outbox2 == [], "no subscriber should be alerted twice for the same events"
    assert sent2 == sent, "sent-log should be stable when nothing new is due"

    # a hard-deadline nudge fires when inside the window and only once
    fake = [{"name": "Closing Soon Fund", "funder": "X", "category": "Documentary",
             "award_amount": "$10k", "deadline": "2026-06-23", "eligibility": "",
             "status": "open", "url": "http://x.test"}]
    ob, sl = run([subs[0]], fake, sent=set())
    keys = sl
    assert any("nudge3" in k for k in keys), "a fund closing in 2 days should trigger the 3-day nudge"
    assert sum(1 for k in keys if "nudge" in k) == 1, "exactly one nudge threshold per run"
    ob2, _ = run([subs[0]], fake, sent=sl)
    assert ob2 == [], "same nudge must not resend"

    # compose produces a real, addressed email
    ev = due_alerts(subs[0], fake, set())
    msg = compose(subs[0], ev)
    assert msg["to"] == "maya@test.com" and msg["subject"] and "Apply:" in msg["body"]

    # live-send failure must NOT mark the key sent (so it retries next run)
    def boom(_): raise RuntimeError("smtp down")
    ob3, sl3 = run([subs[0]], fake, sent=set(), send_fn=boom)
    assert sl3 == set(), "failed sends must not be recorded as sent"
    assert ob3 and "error" in ob3[0]
    print("All Alerter tests passed ✓")


def run_demo():
    grants = match.load_grants()
    if SUBS_SAMPLE.exists():
        subs = json.loads(SUBS_SAMPLE.read_text())
    else:
        subs = [{"name": "Maya", "email": "maya@example.com", "disciplines": ["documentary"], "region": "California"},
                {"name": "Devon", "email": "devon@example.com", "disciplines": ["screenwriting"], "region": "Texas"}]
    outbox, _ = run(subs, grants, sent=set())  # demo always starts clean
    print(f"DRY RUN — {len(outbox)} email(s) would be sent:\n")
    for m in outbox:
        print("=" * 70)
        print(f"To: {m['to']}\nSubject: {m['subject']}\n\n{m['body']}\n")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_tests()
    else:
        run_demo()
