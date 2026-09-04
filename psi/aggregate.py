"""Stage 6 — Aggregate, item-first.

v0.3 makes the individual item the primary object, as the framework defines it:
influence is a property of content, not of a masthead.

  R_item = estimated US adults reaching this item / US adult population
           (psi/audience.py; a modelled level, not a measurement)
  S_item = sum over the item's topics of share x MIP share
  D_item = (logos + ethos + pathos) / 30
  I_item = R x S x D

Outlets are then a rollup: the mean influence of a representative item, plus
the count of items sampled. A period total is deliberately not reported —
sampling is capped per outlet, so summing would rank outlets by how many of
their items we happened to fetch.

Scores come from the newest prompt version present for an item, so a partial
rescore degrades gracefully. v1 scores are kept and exported alongside so the
effect of a rubric change is visible rather than silent.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from psi import audience, db

PRIMARY_VERSION = "score_v2"
FALLBACK_VERSION = "score_v1"


def confidence(n_scored: int, reach_ok: bool) -> str:
    if n_scored >= 6 and reach_ok:
        return "high"
    if 3 <= n_scored <= 5 or (n_scored >= 6 and not reach_ok):
        return "medium"
    return "low"


def fmt(v):
    if isinstance(v, float):
        return f"{v:.8f}" if abs(v) < 0.01 else f"{v:.6f}"
    return "" if v is None else v


def run() -> None:
    now = datetime.now(timezone.utc).isoformat()
    with db.db() as con:
        mip = {r["topic"]: r["mip_share"] for r in db.rows(con, "SELECT topic, mip_share FROM mip WHERE country=?", (db.COUNTRY,))}
        outlets = {r["outlet_id"]: r for r in db.rows(con, """
            SELECT o.*, r.reach_raw, r.reach_unit, r.reach_source, r.reach_source_url, r.reach_date,
                   r.flag AS reach_flag, r.notes AS reach_notes
            FROM outlets o LEFT JOIN reach r USING(outlet_id) WHERE o.country=?""", (db.COUNTRY,))}

        # per-outlet audience model, computed once
        model = {}
        for oid, o in outlets.items():
            people, basis = audience.people_per_item(o["type"], o["reach_unit"], o["reach_raw"], o["reach_notes"])
            model[oid] = {"people": people, "basis": basis, "r": audience.penetration(people)}

        # newest available score per item
        scores = {}
        for ver in (FALLBACK_VERSION, PRIMARY_VERSION):
            for r in db.rows(con, "SELECT * FROM scores2 WHERE prompt_version=?", (ver,)):
                scores[r["item_id"]] = r
        for r in db.rows(con, "SELECT * FROM scores"):          # v1 rows written before the v2 tables existed
            scores.setdefault(r["item_id"], dict(r))

        topics_by_item = {}
        for r in db.rows(con, "SELECT item_id, prompt_version, topic, share FROM item_topics"):
            cur = topics_by_item.setdefault(r["item_id"], {})
            if cur.get("_v") in (None, FALLBACK_VERSION) or r["prompt_version"] == PRIMARY_VERSION:
                if cur.get("_v") != r["prompt_version"]:
                    cur.clear()
                    cur["_v"] = r["prompt_version"]
                cur[r["topic"]] = r["share"]
        for item_id, sc in scores.items():                       # v1 single-label fallback
            if item_id not in topics_by_item and sc.get("topic"):
                topics_by_item[item_id] = {"_v": FALLBACK_VERSION, sc["topic"]: 1.0}

        items = db.rows(con, "SELECT * FROM items WHERE country=?", (db.COUNTRY,))

        rows = []
        for it in items:
            sc = scores.get(it["item_id"])
            o = outlets.get(it["outlet_id"], {})
            m = model.get(it["outlet_id"], {})
            shares = {k: v for k, v in (topics_by_item.get(it["item_id"], {}) or {}).items() if k != "_v"}
            s = sum(share * mip.get(t, 0.0) for t, share in shares.items()) if shares else None
            d = (sc["d"] / 30.0) if sc and sc.get("d") is not None else None
            r = m.get("r")
            i = r * s * d if (r is not None and s is not None and d is not None) else None
            rows.append({
                "item_id": it["item_id"], "outlet_id": it["outlet_id"], "outlet": o.get("name"), "type": o.get("type"),
                "title": it["title"], "url": it["url"], "published_at": it["published_at"], "word_count": it["word_count"],
                "fetch_method": it["fetch_method"],
                "R": r, "S": s, "D": d, "I": i,
                "r_people": m.get("people"), "r_basis": m.get("basis"),
                "logos": sc.get("logos") if sc else None, "ethos": sc.get("ethos") if sc else None,
                "pathos": sc.get("pathos") if sc else None, "d_raw": sc.get("d") if sc else None,
                "prompt_version": sc.get("prompt_version") if sc else None,
                "justification": sc.get("justification") if sc else None,
                "topics": "; ".join(f"{t}:{share:.2f}" for t, share in sorted(shares.items(), key=lambda kv: -kv[1])),
                "reach_flag": o.get("reach_flag") or "unsourced",
            })

        ranked = sorted(rows, key=lambda x: (x["I"] is None, -(x["I"] or 0)))
        rank = 0
        for row in ranked:
            if row["I"] is not None:
                rank += 1
                row["rank"] = rank
            else:
                row["rank"] = None
            db.upsert(con, "item_scores", {"item_id": row["item_id"], "country": db.COUNTRY, "r": row["R"], "s": row["S"],
                                           "d": row["D"], "i": row["I"], "rank": row["rank"], "r_people": row["r_people"],
                                           "r_basis": row["r_basis"], "computed_at": now}, "item_id")

        # ---- outlet rollup: the mean influence of a representative item ----
        by_outlet = {}
        for row in rows:
            by_outlet.setdefault(row["outlet_id"], []).append(row)
        orows = []
        for oid, o in outlets.items():
            mine = [x for x in by_outlet.get(oid, []) if x["I"] is not None]
            n_items = len(by_outlet.get(oid, []))
            n = len(mine)
            mean = (lambda k: sum(x[k] for x in mine) / n if n else None)
            i_mean = mean("I")
            orows.append({
                "outlet_id": oid, "name": o["name"], "type": o["type"], "url": o["url"],
                "R": model[oid]["r"], "r_people": model[oid]["people"], "r_basis": model[oid]["basis"],
                "S": mean("S"), "D": mean("D"), "I_mean_item": i_mean,
                "best_item_I": max((x["I"] for x in mine), default=None),
                "n_items": n_items, "n_scored": n,
                "confidence": confidence(n, model[oid]["r"] is not None),
                "reach_raw": o["reach_raw"], "reach_unit": o["reach_unit"], "reach_flag": o["reach_flag"] or "unsourced",
                "reach_source": o["reach_source"], "reach_source_url": o["reach_source_url"], "reach_date": o["reach_date"],
            })
        oranked = sorted(orows, key=lambda x: (x["I_mean_item"] is None, -(x["I_mean_item"] or 0)))
        orank = 0
        for row in oranked:
            if row["I_mean_item"] is not None:
                orank += 1
                row["rank"] = orank
            else:
                row["rank"] = None
            db.upsert(con, "outlet_scores", {"outlet_id": row["outlet_id"], "country": db.COUNTRY, "r": row["R"],
                                             "s": row["S"], "d": row["D"], "i": row["I_mean_item"], "rank": row["rank"],
                                             "n_items": row["n_items"], "n_scored": row["n_scored"],
                                             "confidence": row["confidence"], "flags": row["reach_flag"],
                                             "computed_at": now}, "outlet_id")
        db.set_meta(con, "aggregate_run", {"at": now, "primary_version": PRIMARY_VERSION,
                                           "us_adults": audience.US_ADULTS,
                                           "assumptions": {k: v[0] for k, v in audience.ASSUMPTIONS.items()}})

    db.OUT.mkdir(parents=True, exist_ok=True)
    icols = ["rank", "item_id", "outlet", "type", "title", "url", "published_at", "R", "S", "D", "I",
             "r_people", "logos", "ethos", "pathos", "d_raw", "topics", "prompt_version", "reach_flag",
             "word_count", "fetch_method", "r_basis", "justification"]
    with open(db.OUT / "ranked_items.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=icols)
        w.writeheader()
        for row in ranked:
            w.writerow({c: fmt(row.get(c)) for c in icols})
    with open(db.OUT / "ranked_items.json", "w", encoding="utf-8") as f:
        json.dump({"country": db.COUNTRY, "computed_at": now,
                   "formula": "I = R x S x D, per item. R = modelled US adults reaching the item / %d US adults." % audience.US_ADULTS,
                   "assumptions": {k: {"value": v[0], "meaning": v[1]} for k, v in audience.ASSUMPTIONS.items()},
                   "items": [{c: row.get(c) for c in icols} for row in ranked]}, f, indent=1)

    ocols = ["rank", "outlet_id", "name", "type", "R", "S", "D", "I_mean_item", "best_item_I", "confidence",
             "n_items", "n_scored", "r_people", "reach_raw", "reach_unit", "reach_flag", "reach_source",
             "reach_source_url", "reach_date", "r_basis", "url"]
    with open(db.OUT / "ranked_outlets.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ocols)
        w.writeheader()
        for row in oranked:
            w.writerow({c: fmt(row.get(c)) for c in ocols})
    with open(db.OUT / "ranked_outlets.json", "w", encoding="utf-8") as f:
        json.dump({"country": db.COUNTRY, "computed_at": now,
                   "note": "Outlet score is the mean influence of one sampled item, not a period total.",
                   "outlets": [{c: row.get(c) for c in ocols} for row in oranked]}, f, indent=1)

    n_ranked = sum(1 for r in ranked if r["I"] is not None)
    print(f"  {len(rows)} items, {n_ranked} with R, S and D; {sum(1 for r in oranked if r['rank'])} outlets rolled up")
    print("  top items:")
    for row in ranked[:10]:
        if row["I"] is not None:
            print(f"    {row['rank']:2d}. I={row['I']:.7f} R={row['R']:.5f} S={row['S']:.3f} D={row['D']:.2f} "
                  f"{row['outlet'][:22]:22s} {(row['title'] or '')[:46]}")


if __name__ == "__main__":
    run()
