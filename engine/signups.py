#!/usr/bin/env python3
"""
Signup dashboard — how's the launch doing?

Reads the live Supabase `signups` table with the service key from .env and
prints the count, a breakdown by discipline + source, and the latest entries.
This is the number that decides everything: 25+ from one good post = flip the
engine live.

    python3 signups.py
"""
import os, json, ssl, urllib.request
from collections import Counter
from pathlib import Path

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL = ssl._create_unverified_context()

GATE = 25  # the validation threshold


def _env():
    env = {}
    p = Path(__file__).with_name(".env")
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: os.environ[k] for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY") if k in os.environ})
    return env


def fetch():
    e = _env()
    url = e["SUPABASE_URL"].rstrip("/") + "/rest/v1/signups?select=email,discipline,source,created_at&order=created_at.desc"
    req = urllib.request.Request(url, headers={
        "apikey": e["SUPABASE_SERVICE_KEY"],
        "Authorization": "Bearer " + e["SUPABASE_SERVICE_KEY"],
    })
    with urllib.request.urlopen(req, context=_SSL, timeout=30) as r:
        return json.loads(r.read())


def main():
    rows = fetch()
    n = len(rows)
    bar = "█" * min(n, GATE) + "·" * max(0, GATE - n)
    print(f"\n  ReelGrants signups: {n}")
    print(f"  [{bar}] {n}/{GATE} to validation gate")
    if n >= GATE:
        print("  ✅ GATE CLEARED — time to flip the engine live.")
    elif n:
        print(f"  {GATE - n} more to go.")
    if rows:
        print("\n  by discipline:")
        for k, v in Counter(r.get("discipline") or "(none)" for r in rows).most_common():
            print(f"    {v:>3}  {k}")
        print("  by source:")
        for k, v in Counter(r.get("source") or "(none)" for r in rows).most_common():
            print(f"    {v:>3}  {k}")
        print("\n  latest:")
        for r in rows[:8]:
            print(f"    {r['created_at'][:16]}  {r['email']}  ({r.get('discipline') or '—'})")
    print()


if __name__ == "__main__":
    main()
