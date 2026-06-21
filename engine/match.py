#!/usr/bin/env python3
"""
ReelGrants — matching engine core (offline, no accounts needed).

This is the heart of the PAID product: given a filmmaker's profile, it reads the
tracked grants, figures out which ones they actually qualify for, sorts by urgency,
and produces the exact "alert" text a member would receive.

It runs entirely offline against grants.json. The later production engine wraps this
with (a) a daily source-poller that refreshes grants.json and (b) an email/SMS
dispatcher. Both of those need accounts; THIS does not, and it's the part worth
proving first because it's what people pay for.

Usage:
    python3 match.py                 # demo: runs 3 sample filmmaker profiles
    python3 match.py --test          # run the built-in assertions
"""
import json, sys, datetime, re
from pathlib import Path

GRANTS_PATH = Path(__file__).resolve().parent.parent / "grants.json"
TODAY = datetime.date(2026, 6, 21)  # pinned for reproducible demo/tests

# --- discipline synonyms so a user's self-described format maps to grant categories ---
DISCIPLINE_MAP = {
    "documentary": "Documentary",
    "doc": "Documentary",
    "narrative": "Narrative",
    "fiction": "Narrative",
    "screenwriting": "Screenwriting",
    "screenplay": "Screenwriting",
    "writer": "Screenwriting",
    "short": "Short Film",
    "short film": "Short Film",
    "animation": "Animation",
    "animated": "Animation",
    "emerging": "Emerging/Identity-based",
    "first feature": "Emerging/Identity-based",
}
# Categories that fit nearly everyone (cross-cutting funds, post, production, dev, fellowships)
BROAD_CATEGORIES = {"General/Creator", "Production", "Post", "Development", "Fellowship/Lab"}


def load_grants():
    data = json.loads(GRANTS_PATH.read_text())
    return data["grants"]


def parse_deadline(deadline: str):
    """Return (date_or_None, is_hard_date). Accepts '2026-07-06', '2026-07-06 (final)' etc."""
    if not deadline:
        return None, False
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", deadline)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return datetime.date(y, mo, d), True
        except ValueError:
            return None, False
    return None, False


def days_left(grant):
    dt, hard = parse_deadline(grant.get("deadline", ""))
    if dt and hard:
        return (dt - TODAY).days
    return None


def region_ok(eligibility: str, user_region: str | None):
    """Conservative region filter: if a grant is clearly region-locked and the user is
    elsewhere, exclude it. We only act on regions we can detect; otherwise include."""
    if not user_region:
        return True
    elig = (eligibility or "").lower()
    ur = user_region.strip().lower()
    LOCKS = {
        "texas": ["texas", "tx-resident", "texas-resident", " tx "],
        "tx": ["texas"],
        "new york": ["ny state", "new york", "nyc"],
        "ny": ["ny state", "new york", "nyc"],
        "minnesota": ["mn or nyc", " mn "],
    }
    # find any region lock the grant imposes
    for region_name, needles in LOCKS.items():
        if any(n in elig for n in needles):
            # grant is locked to region_name; include only if user matches
            if region_name in ur or ur in region_name:
                return True
            # special case: MN-or-NYC grants
            if "mn or nyc" in elig and ("new york" in ur or "ny" == ur or "nyc" in ur or "minnesota" in ur or "mn" == ur):
                return True
            return False
    return True


def match_for(profile, grants):
    """profile = {disciplines:[...], region:str|None, want_open_only:bool}
    Returns matched grants sorted by urgency, each annotated with reasons + days_left."""
    wanted = set()
    for d in profile.get("disciplines", []):
        key = d.strip().lower()
        wanted.add(DISCIPLINE_MAP.get(key, d.strip()))

    results = []
    for g in grants:
        if g.get("status") == "verify":
            continue  # never surface unverified rows
        cat = g.get("category", "")
        reasons = []
        cat_hit = cat in wanted
        broad_hit = cat in BROAD_CATEGORIES
        if not (cat_hit or broad_hit):
            continue
        if not region_ok(g.get("eligibility", ""), profile.get("region")):
            continue
        if cat_hit:
            reasons.append(f"matches your work ({cat})")
        elif broad_hit:
            reasons.append(f"open to all creators ({cat})")

        dl = days_left(g)
        if dl is not None and dl >= 0:
            reasons.append(f"closes in {dl} days")
        elif g.get("status") == "open":
            reasons.append("open now")
        elif g.get("status") == "rolling":
            reasons.append("rolling — apply anytime")
        elif g.get("status") == "soon":
            reasons.append("opening soon")
        else:
            reasons.append(f"typical window: {g.get('deadline','annual')}")

        # urgency score: lower = more urgent (surfaced first)
        if dl is not None and dl >= 0:
            score = dl
        elif g.get("status") == "open":
            score = 5
        elif g.get("status") == "soon":
            score = 40
        elif g.get("status") == "rolling":
            score = 60
        else:
            score = 365  # recurring/closed-window

        if profile.get("want_open_only") and score > 60:
            continue

        results.append({**g, "_score": score, "_days_left": dl, "_reasons": reasons})

    results.sort(key=lambda x: (x["_score"], x["name"]))
    return results


def alert_text(profile_name, matched, limit=5):
    if not matched:
        return f"Hi {profile_name} — no matching grants are open right now. We'll email you the moment one is."
    lines = [f"Hi {profile_name} — {len(matched)} grants match your profile. Top picks:\n"]
    for g in matched[:limit]:
        lines.append(f"• {g['name']} ({g['funder']}) — {g['award_amount']}\n  {'; '.join(g['_reasons'])}\n  {g['url']}")
    return "\n".join(lines)


DEMO_PROFILES = [
    {"name": "Maya (doc filmmaker, CA)", "disciplines": ["documentary"], "region": "California", "want_open_only": False},
    {"name": "Devon (screenwriter, TX)", "disciplines": ["screenwriting"], "region": "Texas", "want_open_only": False},
    {"name": "Sam (animator, NY)", "disciplines": ["animation", "short"], "region": "New York", "want_open_only": True},
]


def run_demo():
    grants = load_grants()
    for p in DEMO_PROFILES:
        matched = match_for(p, grants)
        print("=" * 70)
        print(alert_text(p["name"], matched))
        print()


def run_tests():
    grants = load_grants()
    # 1) deadline parsing
    assert parse_deadline("2026-07-06") == (datetime.date(2026, 7, 6), True)
    assert parse_deadline("annual ~May")[0] is None
    # 2) a doc filmmaker gets documentary + broad funds, not animation-only rows
    maya = match_for({"disciplines": ["documentary"], "region": "California"}, grants)
    names = {g["name"] for g in maya}
    assert any("Documentary Fund" in n for n in names), "doc filmmaker should see Sundance Doc Fund"
    assert "AEF Student Scholarship" not in names, "doc filmmaker should NOT get animation-only grant"
    # 3) region lock works: a non-TX writer should NOT see the TX-only AFS short grant
    nontx = match_for({"disciplines": ["short"], "region": "California"}, grants)
    assert "AFS Grant for Short Films" not in {g["name"] for g in nontx}, "TX-only grant leaked to CA user"
    tx = match_for({"disciplines": ["short"], "region": "Texas"}, grants)
    assert "AFS Grant for Short Films" in {g["name"] for g in tx}, "TX user should see TX grant"
    # 4) urgency ordering: an item closing in N days outranks a recurring one
    assert maya[0]["_score"] <= maya[-1]["_score"]
    # 5) unverified rows never surface
    allnames = {g["name"] for g in match_for({"disciplines": ["documentary","narrative","screenwriting","animation","short"], "region": None}, grants)}
    assert "Diane Weyermann Fellowship" not in allnames, "verify-status row should be hidden"
    print("All tests passed ✓")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_tests()
    else:
        run_demo()
