"""Stage 2 — Reach (R).

Reads data/reach_seed.csv (one row per outlet, sourced figures with URLs and
verbatim quotes) and data/type_weights.csv (Pew platform shares), applies
the verification verdicts, and normalises:

  reach_norm_type = reach_raw / max(reach_raw) within the same (type, unit)
  reach_norm      = reach_norm_type * weight[type]
  weight[type]    = platform_share[type] / max(platform_share)

Rows whose figure was refuted by the fact-check pass are nulled and flagged
`unsourced`. Rows the checker could not fetch keep the figure with flag
`unverified`. Nothing is ever filled in by hand here.
"""
from __future__ import annotations

import csv
from collections import defaultdict

from psi import db

REACH_SEED = db.DATA / "reach_seed.csv"
WEIGHTS_SEED = db.DATA / "type_weights.csv"
TABLE_MD = db.DATA / "reach_table.md"

# When Pew has no platform share for a type, borrow the nearest platform's.
WEIGHT_PROXY = {"cable": "tv", "newsletter": "print_digital"}


def _num(v):
    if v is None:
        return None
    v = str(v).strip()
    if v == "" or v.lower() in {"null", "none", "nan"}:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load_csv(path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Missing {path}")
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()} for r in csv.DictReader(f)]


def run() -> None:
    reach_rows = load_csv(REACH_SEED)
    weight_rows = load_csv(WEIGHTS_SEED)

    with db.db() as con:
        outlets = {r["outlet_id"]: r for r in db.rows(con, "SELECT * FROM outlets WHERE country=?", (db.COUNTRY,))}

        # --- type weights ---
        shares = {}
        for w in weight_rows:
            share = _num(w.get("platform_share"))
            shares[w["type"]] = {"platform_share": share, "source": w.get("source") or None,
                                 "source_url": w.get("source_url") or None, "survey_date": w.get("survey_date") or None,
                                 "flag": w.get("flag") or ("ok" if share is not None else "unsourced")}
        max_share = max([v["platform_share"] for v in shares.values() if v["platform_share"] is not None] or [None])
        weights = {}
        for t in ["tv", "cable", "print_digital", "radio", "podcast", "newsletter"]:
            info = shares.get(t, {"platform_share": None, "source": None, "source_url": None, "survey_date": None, "flag": "unsourced"})
            share = info["platform_share"]
            flag = info["flag"]
            if share is None and t in WEIGHT_PROXY and shares.get(WEIGHT_PROXY[t], {}).get("platform_share") is not None:
                proxy = shares[WEIGHT_PROXY[t]]
                share = proxy["platform_share"]
                info = {**proxy}
                flag = "proxy"
            weight = (share / max_share) if (share is not None and max_share) else None
            weights[t] = weight
            db.upsert(con, "type_weights", {"type": t, "country": db.COUNTRY, "platform_share": share, "weight": weight,
                                            "source": info.get("source"), "source_url": info.get("source_url"),
                                            "survey_date": info.get("survey_date"), "flag": flag}, "type")

        # --- apply verdicts, group by (type, unit) ---
        prepared = []
        for r in reach_rows:
            oid = r["outlet_id"]
            if oid not in outlets:
                print(f"  reach row for unknown outlet {oid!r} skipped")
                continue
            raw = _num(r.get("reach_raw"))
            flag = (r.get("flag") or "unsourced").strip()
            verdict = (r.get("verify_verdict") or "").strip()
            notes = r.get("notes") or ""
            if raw is not None and verdict == "refuted":
                notes = f"REFUTED by fact-check ({r.get('verify_evidence','')[:200]}); candidate figure {raw} {r.get('reach_unit')} from {r.get('reach_source_url')}. " + notes
                raw, flag = None, "unsourced"
            elif raw is not None and verdict == "unverifiable":
                flag = "unverified" if flag == "ok" else f"{flag}_unverified"
            if raw is None:
                flag = "unsourced"
            prepared.append({"outlet_id": oid, "type": outlets[oid]["type"], "raw": raw, "unit": (r.get("reach_unit") or None) if raw is not None else None,
                             "source": r.get("reach_source") or None, "url": r.get("reach_source_url") or None,
                             "quote": r.get("reach_source_quote") or None, "date": r.get("reach_date") or None,
                             "tier": int(_num(r.get("source_tier")) or 0) or None, "flag": flag, "notes": notes})

        groups = defaultdict(list)
        for p in prepared:
            if p["raw"] is not None:
                groups[(p["type"], p["unit"])].append(p["raw"])
        group_max = {k: max(v) for k, v in groups.items()}

        n_sourced = 0
        for p in prepared:
            norm_type = norm = None
            if p["raw"] is not None:
                gmax = group_max[(p["type"], p["unit"])]
                norm_type = p["raw"] / gmax if gmax else None
                if len(groups[(p["type"], p["unit"])]) < 3:
                    p["notes"] = f"small unit group ({len(groups[(p['type'], p['unit'])])} outlets share unit {p['unit']}); " + p["notes"]
                w = weights.get(p["type"])
                norm = norm_type * w if (norm_type is not None and w is not None) else None
                n_sourced += 1
            db.upsert(con, "reach", {"outlet_id": p["outlet_id"], "country": db.COUNTRY, "reach_raw": p["raw"], "reach_unit": p["unit"],
                                     "reach_source": p["source"], "reach_source_url": p["url"], "reach_source_quote": p["quote"],
                                     "reach_date": p["date"], "reach_norm_type": norm_type, "reach_norm": norm,
                                     "flag": p["flag"], "source_tier": p["tier"], "notes": p["notes"]}, "outlet_id")

        # outlets with no reach row at all -> explicit unsourced row
        for oid in outlets:
            if not con.execute("SELECT 1 FROM reach WHERE outlet_id=?", (oid,)).fetchone():
                db.upsert(con, "reach", {"outlet_id": oid, "country": db.COUNTRY, "reach_raw": None, "flag": "unsourced",
                                         "notes": "no reach row in seed"}, "outlet_id")

        table = db.rows(con, """SELECT o.name, o.type, r.reach_raw, r.reach_unit, r.reach_source, r.reach_source_url, r.reach_date,
                                       r.reach_norm_type, r.reach_norm, r.flag, r.source_tier
                                FROM reach r JOIN outlets o USING(outlet_id) WHERE o.country=? ORDER BY o.type, r.reach_norm DESC NULLS LAST""", (db.COUNTRY,))
        flags = db.rows(con, "SELECT flag, COUNT(*) n FROM reach WHERE country=? GROUP BY flag ORDER BY n DESC", (db.COUNTRY,))

    with open(TABLE_MD, "w", encoding="utf-8") as f:
        f.write("# Reach table (auto-generated by `python run.py reach`)\n\n")
        f.write("Type weights (Pew platform share / max):\n\n")
        for t, w in weights.items():
            f.write(f"- {t}: {w:.3f}\n" if w is not None else f"- {t}: null\n")
        f.write("\n| Outlet | Type | Raw | Unit | Source | Date | Norm (type) | Norm | Flag |\n|---|---|---|---|---|---|---|---|---|\n")
        for r in table:
            raw = f"{r['reach_raw']:,.0f}" if r["reach_raw"] is not None else "null"
            src = f"[{r['reach_source']}]({r['reach_source_url']})" if r["reach_source_url"] else (r["reach_source"] or "")
            nt = f"{r['reach_norm_type']:.3f}" if r["reach_norm_type"] is not None else ""
            nn = f"{r['reach_norm']:.3f}" if r["reach_norm"] is not None else ""
            f.write(f"| {r['name']} | {r['type']} | {raw} | {r['reach_unit'] or ''} | {src} | {r['reach_date'] or ''} | {nt} | {nn} | {r['flag']} |\n")

    print(f"  {len(prepared)} reach rows; {n_sourced} with a sourced figure")
    for fl in flags:
        print(f"    {fl['flag']:24s} {fl['n']}")
    print("  type weights:", {t: (round(w, 3) if w is not None else None) for t, w in weights.items()})


if __name__ == "__main__":
    run()
