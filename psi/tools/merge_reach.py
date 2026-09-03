"""Assemble data/reach_seed.csv from the collected sources, then (optionally) verify.

Sources, all under data/raw/:
  public_counts.json        YouTube subscribers (podcasts), publication subscriber lines (newsletters)
  semrush_visits.json       monthly visits for print/digital outlets
  reach_press_figures.json  Nielsen/press figures for TV, cable and radio, copied verbatim with URLs

One row per outlet in the DB. Outlets with no figure get reach_raw empty and
flag=unsourced. The verify columns are filled by verify_reach.py.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from psi import db  # noqa: E402
from psi.tools.ingest_research import REACH_COLS, write_csv  # noqa: E402

RAW = db.DATA / "raw"
SEED = db.DATA / "reach_seed.csv"


def load(name: str) -> dict:
    p = RAW / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def main() -> None:
    counts = load("public_counts.json")
    semrush = load("semrush_visits.json")
    press = {k: v for k, v in load("reach_press_figures.json").items() if not k.startswith("_")}
    existing = {}
    if SEED.exists():
        with open(SEED, newline="", encoding="utf-8") as f:
            existing = {r["outlet_id"]: r for r in csv.DictReader(f)}
    with db.db() as con:
        outlets = db.rows(con, "SELECT outlet_id, name, type FROM outlets WHERE country=? ORDER BY type, outlet_id", (db.COUNTRY,))

    rows, n_sourced = [], 0
    for o in outlets:
        oid = o["outlet_id"]
        src = None
        if oid in press:
            p = press[oid]
            src = {"raw": p.get("raw"), "unit": p.get("unit"), "source": p.get("source"), "url": p.get("url"), "quote": p.get("quote"),
                   "date": p.get("date"), "tier": p.get("tier"), "flag": p.get("flag", "ok"), "notes": p.get("notes", "")}
        elif oid in semrush and semrush[oid].get("raw"):
            s = semrush[oid]
            src = {"raw": s["raw"], "unit": s["unit"], "source": s["source"], "url": s["url"], "quote": s["quote"],
                   "date": s.get("period") or s["date"], "tier": s["tier"], "flag": s["flag"], "notes": f"domain {s['domain']}; fetched {s['date']}"}
        elif oid in counts and counts[oid].get("raw"):
            c = counts[oid]
            src = {"raw": c["raw"], "unit": c["unit"], "source": c["source"], "url": c["url"], "quote": c["quote"],
                   "date": c["date"], "tier": c["tier"], "flag": c["flag"], "notes": "public count read from the page on the fetch date"}
        if src and src["raw"] is not None:
            n_sourced += 1
            prev = existing.get(oid, {})
            same = prev.get("reach_source_url") == src["url"] and str(prev.get("reach_raw")) == str(src["raw"])
            rows.append({"outlet_id": oid, "reach_raw": src["raw"], "reach_unit": src["unit"], "reach_source": src["source"],
                         "reach_source_url": src["url"], "reach_source_quote": src["quote"], "reach_date": src["date"],
                         "source_tier": src["tier"], "flag": src["flag"], "fetched_source": True,
                         "verify_verdict": prev.get("verify_verdict", "") if same else "", "verify_evidence": prev.get("verify_evidence", "") if same else "",
                         "notes": src.get("notes") or ""})
        else:
            err = (semrush.get(oid) or counts.get(oid) or {}).get("error") or (press.get(oid) or {}).get("notes") or "no figure collected"
            rows.append({"outlet_id": oid, "reach_raw": "", "reach_unit": "", "reach_source": "", "reach_source_url": "", "reach_source_quote": "",
                         "reach_date": "", "source_tier": "", "flag": "unsourced", "fetched_source": False, "verify_verdict": "", "verify_evidence": "",
                         "notes": f"unsourced: {err}"})
    write_csv(SEED, rows, REACH_COLS)
    by_type = {}
    for o, r in zip(outlets, rows):
        by_type.setdefault(o["type"], [0, 0])
        by_type[o["type"]][1] += 1
        if r["reach_raw"] != "":
            by_type[o["type"]][0] += 1
    print(f"wrote {SEED}: {n_sourced} sourced of {len(rows)}; by type: " + ", ".join(f"{t} {a}/{b}" for t, (a, b) in by_type.items()))


if __name__ == "__main__":
    main()
