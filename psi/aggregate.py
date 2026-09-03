"""Stage 6 — Aggregate to outlet level.

  R = reach_norm                         (0-1, cross-type normalised)
  S = mean(mip_share of item topics)     (0-1)
  D = mean(logos+ethos+pathos) / 30      (0-1)
  I = R * S * D

confidence: high  = >= 6 scored items and sourced reach
            medium = 3-5 scored items (any reach)
            low    = otherwise
Outlets without a sourced reach figure get I = null (never a guessed R).
Exports out/ranked_outlets.csv, out/ranked_outlets.json, out/items_scored.csv.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from psi import db


def confidence(n_scored: int, reach_sourced: bool) -> str:
    if n_scored >= 6 and reach_sourced:
        return "high"
    if 3 <= n_scored <= 5 or (n_scored >= 6 and not reach_sourced):
        return "medium"
    return "low"


def run() -> None:
    with db.db() as con:
        mip = {r["topic"]: r["mip_share"] for r in db.rows(con, "SELECT topic, mip_share FROM mip WHERE country=?", (db.COUNTRY,))}
        outlets = db.rows(con, """SELECT o.*, r.reach_raw, r.reach_unit, r.reach_norm, r.reach_norm_type, r.flag AS reach_flag,
                                         r.reach_source, r.reach_source_url, r.reach_date
                                  FROM outlets o LEFT JOIN reach r USING(outlet_id) WHERE o.country=?""", (db.COUNTRY,))
        items = db.rows(con, """SELECT i.item_id, i.outlet_id, i.title, i.url, i.published_at, i.word_count, i.fetch_method,
                                       s.topic, s.logos, s.ethos, s.pathos, s.d, s.justification, s.model, s.prompt_version, s.cost_usd, s.text_truncated
                                FROM items i LEFT JOIN scores s USING(item_id) WHERE i.country=?""", (db.COUNTRY,))
        n_items_by_outlet = {}
        scored_by_outlet = {}
        for it in items:
            n_items_by_outlet[it["outlet_id"]] = n_items_by_outlet.get(it["outlet_id"], 0) + 1
            if it["d"] is not None:
                scored_by_outlet.setdefault(it["outlet_id"], []).append(it)

        results = []
        for o in outlets:
            sc = scored_by_outlet.get(o["outlet_id"], [])
            n_scored = len(sc)
            r = o["reach_norm"]
            reach_sourced = o["reach_raw"] is not None and r is not None
            s = sum(mip.get(x["topic"], 0.0) for x in sc) / n_scored if n_scored else None
            d = (sum(x["d"] for x in sc) / n_scored) / 30.0 if n_scored else None
            i = r * s * d if (r is not None and s is not None and d is not None) else None
            flags = []
            if o["reach_flag"] and o["reach_flag"] != "ok":
                flags.append(f"reach:{o['reach_flag']}")
            if o["status"] != "active":
                flags.append(f"status:{o['status']}")
            if n_scored == 0:
                flags.append("no_scored_items")
            results.append({
                "outlet_id": o["outlet_id"], "name": o["name"], "type": o["type"], "url": o["url"],
                "R": r, "S": s, "D": d, "I": i,
                "reach_raw": o["reach_raw"], "reach_unit": o["reach_unit"], "reach_source": o["reach_source"],
                "reach_source_url": o["reach_source_url"], "reach_date": o["reach_date"], "reach_flag": o["reach_flag"] or "unsourced",
                "n_items": n_items_by_outlet.get(o["outlet_id"], 0), "n_scored": n_scored,
                "mean_logos": (sum(x["logos"] for x in sc) / n_scored) if n_scored else None,
                "mean_ethos": (sum(x["ethos"] for x in sc) / n_scored) if n_scored else None,
                "mean_pathos": (sum(x["pathos"] for x in sc) / n_scored) if n_scored else None,
                "confidence": confidence(n_scored, reach_sourced), "flags": ";".join(flags),
            })

        ranked = sorted(results, key=lambda x: (x["I"] is None, -(x["I"] or 0), -(x["D"] or 0)))
        rank = 0
        for row in ranked:
            if row["I"] is not None:
                rank += 1
                row["rank"] = rank
            else:
                row["rank"] = None

        now = datetime.now(timezone.utc).isoformat()
        for row in ranked:
            db.upsert(con, "outlet_scores", {"outlet_id": row["outlet_id"], "country": db.COUNTRY, "r": row["R"], "s": row["S"],
                                             "d": row["D"], "i": row["I"], "rank": row["rank"], "n_items": row["n_items"],
                                             "n_scored": row["n_scored"], "confidence": row["confidence"], "flags": row["flags"],
                                             "computed_at": now}, "outlet_id")

    db.OUT.mkdir(parents=True, exist_ok=True)
    cols = ["rank", "outlet_id", "name", "type", "R", "S", "D", "I", "confidence", "n_items", "n_scored", "mean_logos", "mean_ethos",
            "mean_pathos", "reach_raw", "reach_unit", "reach_source", "reach_source_url", "reach_date", "reach_flag", "flags", "url"]

    def fmt(v):
        if isinstance(v, float):
            return f"{v:.6f}"
        return "" if v is None else v

    with open(db.OUT / "ranked_outlets.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in ranked:
            w.writerow({c: fmt(row.get(c)) for c in cols})
    with open(db.OUT / "ranked_outlets.json", "w", encoding="utf-8") as f:
        json.dump({"country": db.COUNTRY, "computed_at": now, "formula": "I = R * S * D; R=reach_norm, S=mean mip_share of item topics, D=mean(L+E+P)/30",
                   "outlets": [{c: row.get(c) for c in cols} for row in ranked]}, f, indent=1)

    icols = ["item_id", "outlet_id", "title", "url", "published_at", "word_count", "fetch_method", "topic", "mip_share", "logos", "ethos",
             "pathos", "d", "justification", "model", "prompt_version", "cost_usd", "text_truncated"]
    with open(db.OUT / "items_scored.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=icols)
        w.writeheader()
        for it in sorted(items, key=lambda x: (x["outlet_id"], x["published_at"] or "")):
            it = dict(it)
            it["mip_share"] = mip.get(it["topic"]) if it["topic"] else None
            w.writerow({c: fmt(it.get(c)) for c in icols})

    n_ranked = sum(1 for r in ranked if r["I"] is not None)
    print(f"  {len(ranked)} outlets aggregated; {n_ranked} ranked (have R, S and D)")
    for row in ranked[:10]:
        if row["I"] is not None:
            print(f"    {row['rank']:2d}. {row['name']:32s} I={row['I']:.4f} R={row['R']:.3f} S={row['S']:.3f} D={row['D']:.3f} n={row['n_scored']} {row['confidence']}")


if __name__ == "__main__":
    run()
