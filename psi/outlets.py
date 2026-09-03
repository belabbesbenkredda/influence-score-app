"""Stage 1 — Outlet universe.

Loads data/outlets_seed.csv into the `outlets` table. The seed file is the
editable source of truth: add a row there to add an outlet, then rerun
`python run.py outlets`.
"""
from __future__ import annotations

import csv

from psi import db

SEED = db.DATA / "outlets_seed.csv"
FIELDS = ["outlet_id", "name", "type", "url", "rss_url", "youtube_channel", "youtube_channel_id",
          "transcript_url", "status", "notes"]
TYPES = {"tv", "cable", "print_digital", "radio", "podcast", "newsletter"}


def load_seed() -> list[dict]:
    if not SEED.exists():
        raise SystemExit(f"Missing {SEED}. Stage 1 needs the outlet seed file.")
    with open(SEED, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in FIELDS if c not in reader.fieldnames]
        if missing:
            raise SystemExit(f"{SEED} is missing columns: {missing}")
        out = []
        for row in reader:
            row = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            if not row["outlet_id"]:
                continue
            if row["type"] not in TYPES:
                raise SystemExit(f"{row['outlet_id']}: bad type {row['type']!r}")
            out.append(row)
    ids = [r["outlet_id"] for r in out]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SystemExit(f"duplicate outlet_id in seed: {sorted(dupes)}")
    return out


def run() -> None:
    seed = load_seed()
    with db.db() as con:
        for row in seed:
            rec = {c: (row.get(c) or None) for c in FIELDS}
            rec["status"] = rec["status"] or "active"
            rec["country"] = db.COUNTRY
            db.upsert(con, "outlets", rec, "outlet_id")
        n = con.execute("SELECT COUNT(*) FROM outlets WHERE country=?", (db.COUNTRY,)).fetchone()[0]
        by_type = db.rows(con, "SELECT type, COUNT(*) AS n, SUM(status='active') AS active FROM outlets WHERE country=? GROUP BY type ORDER BY type", (db.COUNTRY,))
    print(f"  {n} outlets loaded for {db.COUNTRY}")
    for r in by_type:
        print(f"    {r['type']:14s} {r['n']:3d} (active {r['active']})")


if __name__ == "__main__":
    run()
