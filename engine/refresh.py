#!/usr/bin/env python3
"""
ReelGrants — Sourcer/Verifier agent (the first Flock worker).

Job: keep the tracked grants honest WITHOUT a human babysitting it.

For each fund in sources.json it fetches the funder's own page, reads the text for
open/closed signals and deadline dates, compares that to what we currently show, and
produces a PROPOSAL with a confidence score:

  - keep      : page agrees with us (nothing to do)
  - auto-close: page clearly says applications are closed but we show it OPEN
                -> high confidence, safe to auto-apply (prevents showing a stale "open")
  - flag      : something changed or is ambiguous -> goes to the review queue for a
                30-second human/AI check. We NEVER auto-publish a new *deadline*; a wrong
                date emailed to a subscriber is the one unforgivable error, so dates are
                always reviewed, never trusted blind.

Design notes:
  * stdlib only (urllib/re/json/datetime) — runs anywhere, no API key, no pip install.
  * fetch is injectable (fetch_fn) so the whole thing is testable offline with fixtures.
  * the live default only hits the time-sensitive ("daily"/"weekly") sources, to be a
    polite crawler and keep runs fast.

Usage:
    python3 refresh.py --test          # offline assertions against fixtures
    python3 refresh.py                  # live check of due sources -> review_queue.json
    python3 refresh.py --all            # live check of every source
"""
import json, sys, re, datetime, ssl, urllib.request, urllib.error
from pathlib import Path

# Public read-only crawl: prefer verified TLS, but fall back to an unverified context
# when the host Python lacks a CA bundle (common on macOS). Safe here — we only read
# public grant pages for keywords/dates; no credentials or secrets ever cross this.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl._create_unverified_context()

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "sources.json"
QUEUE_PATH = ROOT / "engine" / "review_queue.json"
TODAY = datetime.date(2026, 6, 21)
UA = "ReelGrantsBot/0.1 (+https://nicholastavares55.github.io/reelgrants/; polite grant tracker)"

CLOSED_SIGNALS = [
    "applications are now closed", "applications are closed", "submissions are closed",
    "application is closed", "now closed", "deadline has passed", "no longer accepting",
    "closed for the season", "applications closed", "currently closed", "check back",
]
OPEN_SIGNALS = [
    "now accepting", "applications are open", "apply now", "submissions are open",
    "now open", "open call", "accepting applications", "applications open",
]
MONTHS = {m.lower(): i for i, m in enumerate(
    ["", "January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"])}


def http_fetch(url, timeout=12):
    """Default live fetcher. Returns lowercased page text, or '' on any failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
            raw = r.read(400_000).decode("utf-8", "ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, Exception):
        return ""
    # crude tag strip — enough for keyword/date signals
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def find_dates(text, today=TODAY, horizon_days=400):
    """Return sorted list of plausible upcoming deadline dates found in the text."""
    found = set()
    # 1) "July 7, 2026" / "July 7 2026"
    for m in re.finditer(r"([a-z]+)\s+(\d{1,2}),?\s+(20\d{2})", text):
        mo = MONTHS.get(m.group(1), 0)
        if mo:
            try:
                found.add(datetime.date(int(m.group(3)), mo, int(m.group(2))))
            except ValueError:
                pass
    # 2) ISO 2026-07-07
    for m in re.finditer(r"(20\d{2})-(\d{2})-(\d{2})", text):
        try:
            found.add(datetime.date(*map(int, m.groups())))
        except ValueError:
            pass
    upcoming = sorted(d for d in found if today <= d <= today + datetime.timedelta(days=horizon_days))
    return upcoming


def assess(source, text, today=TODAY):
    """Compare a fetched page against what we currently show. Returns a proposal dict."""
    cur_status = str(source.get("current", {}).get("status", "")).lower()
    name = source["name"]
    base = {"name": name, "url": source["url"], "current": source.get("current", {})}

    if not text:
        return {**base, "action": "flag", "confidence": 0.3,
                "evidence": "could not fetch page (down, blocked, or moved)",
                "reason": "unreachable"}

    closed = next((s for s in CLOSED_SIGNALS if s in text), None)
    opened = next((s for s in OPEN_SIGNALS if s in text), None)
    dates = find_dates(text, today)
    we_show_open = ("open" in cur_status and "soon" not in cur_status) or cur_status == "rolling"

    # Strongest, safest signal: we say OPEN but the page says CLOSED -> auto-correct.
    if closed and we_show_open and not opened:
        return {**base, "action": "auto-close", "confidence": 0.9,
                "evidence": f'page says "{closed}"', "reason": "we show open but funder says closed",
                "proposed": {"status": "closed-recurring"}}

    # We say closed/recurring but the page is clearly open now -> flag to promote (don't
    # auto-publish: opening a fund on the site should be a deliberate, verified action).
    if opened and not we_show_open and not closed:
        ev = f'page says "{opened}"'
        if dates:
            ev += f"; nearest date found {dates[0].isoformat()}"
        return {**base, "action": "flag", "confidence": 0.7,
                "evidence": ev, "reason": "funder appears OPEN but we don't show it",
                "candidate_deadline": dates[0].isoformat() if dates else None}

    # We show a hard deadline; see if the page's nearest date drifted from ours.
    cur_dl = str(source.get("current", {}).get("deadline", ""))
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", cur_dl)
    if m and dates:
        our_dl = datetime.date(*map(int, m.groups()))
        if abs((dates[0] - our_dl).days) > 3 and dates[0] not in (our_dl,):
            return {**base, "action": "flag", "confidence": 0.5,
                    "evidence": f"page's nearest date {dates[0].isoformat()} vs our {our_dl.isoformat()}",
                    "reason": "possible deadline drift — verify before changing"}

    return {**base, "action": "keep", "confidence": 0.6,
            "evidence": "page consistent with what we show", "reason": "ok"}


def run(sources, fetch_fn=http_fetch, today=TODAY, only_due=True):
    report = {"checked": 0, "keep": 0, "auto_close": 0, "flag": 0,
              "applied": [], "queue": [], "ran_at": str(today)}
    for s in sources:
        if only_due and s.get("check") == "monthly":
            continue
        report["checked"] += 1
        p = assess(s, fetch_fn(s["url"]), today)
        act = p["action"]
        if act == "keep":
            report["keep"] += 1
        elif act == "auto-close":
            report["auto_close"] += 1
            report["applied"].append(p)   # caller persists status change to grants.json
        else:
            report["flag"] += 1
            report["queue"].append(p)
    return report


# ----------------------------- tests -----------------------------
def run_tests():
    fixtures = {
        "https://open-but-we-say-closed.test":
            "great news — applications are now open! apply now. deadline august 3, 2026.",
        "https://closed-but-we-say-open.test":
            "the 2026 cycle is complete. applications are now closed. check back next year.",
        "https://consistent-open.test":
            "submissions are open. final deadline july 7, 2026. apply now.",
        "https://drifted.test":
            "the new deadline is august 15, 2026. now accepting submissions.",
        "https://down.test": "",
    }
    fetch = lambda u: fixtures.get(u, "")

    srcs = [
        {"name": "OpenClaim", "url": "https://closed-but-we-say-open.test",
         "check": "daily", "current": {"status": "open", "deadline": "2026-07-01"}},
        {"name": "ShouldPromote", "url": "https://open-but-we-say-closed.test",
         "check": "weekly", "current": {"status": "closed-recurring", "deadline": "annual"}},
        {"name": "Steady", "url": "https://consistent-open.test",
         "check": "daily", "current": {"status": "open", "deadline": "2026-07-07"}},
        {"name": "Drifter", "url": "https://drifted.test",
         "check": "daily", "current": {"status": "open", "deadline": "2026-07-07"}},
        {"name": "Offline", "url": "https://down.test",
         "check": "daily", "current": {"status": "open", "deadline": "2026-07-07"}},
        {"name": "Skipped", "url": "https://consistent-open.test",
         "check": "monthly", "current": {"status": "closed-recurring", "deadline": "annual"}},
    ]
    rep = run(srcs, fetch_fn=fetch)

    assert rep["checked"] == 5, f"monthly source should be skipped, got {rep['checked']}"
    a = {p["name"]: p for p in rep["applied"]}
    assert "OpenClaim" in a and a["OpenClaim"]["action"] == "auto-close", "stale-open should auto-close"
    assert a["OpenClaim"]["confidence"] >= 0.9
    q = {p["name"]: p for p in rep["queue"]}
    assert q["ShouldPromote"]["reason"].startswith("funder appears OPEN"), "open fund should flag to promote"
    assert q["ShouldPromote"]["candidate_deadline"] == "2026-08-03", "should extract candidate date"
    assert q["Drifter"]["reason"].startswith("possible deadline drift"), "drift should be flagged not auto-applied"
    assert q["Offline"]["reason"] == "unreachable", "unfetchable page should flag, never silently change"
    # the safety invariant: a deadline change is NEVER auto-applied
    assert all("deadline" not in p.get("proposed", {}) for p in rep["applied"]), \
        "deadlines must never auto-apply — review only"
    # date parsing
    assert find_dates("deadline july 7, 2026 and 2026-08-03")[0] == datetime.date(2026, 7, 7)
    print("All Sourcer/Verifier tests passed ✓")


def run_live(only_due=True):
    sources = json.loads(SOURCES_PATH.read_text())["sources"]
    rep = run(sources, only_due=only_due)
    QUEUE_PATH.write_text(json.dumps(rep, indent=2))
    print(f"Checked {rep['checked']} sources · keep {rep['keep']} · "
          f"auto-close {rep['auto_close']} · flagged {rep['flag']}")
    print(f"Review queue written to {QUEUE_PATH.relative_to(ROOT)}")
    for p in rep["queue"][:10]:
        print(f"  ⚑ {p['name']}: {p['reason']} ({p['evidence']})")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_tests()
    else:
        run_live(only_due="--all" not in sys.argv)
