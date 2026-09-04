"""Generate the v0.5 report body: an interactive index, not a printed table.

Three things drive the design.

1. The heavy bars are gone. Magnitude is a hairline track with a thin rounded
   mark — recessive, per the mark specs — and hue is reserved for the one place
   it carries identity, the Logos/Ethos/Pathos strip.

2. Interaction has to produce understanding, not just disclose fields. The
   centrepiece is a live assumption panel: every constant inside R is a control,
   and moving one re-ranks the whole index in front of you. That answers the
   question this index most needs to answer about itself — how much of the
   ranking is measurement and how much is my guesswork.

3. Each item is placed in the distribution rather than merely printed: expanding
   a row shows its percentile on reach, salience and discursiveness, so a number
   becomes a position.

The page ships the corpus as compact JSON and recomputes the audience model in
the browser, mirroring psi/audience.py exactly.
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from psi import audience, db  # noqa: E402


def build():
    with db.db() as con:
        outlets = db.rows(con, """
            SELECT o.outlet_id, o.name, o.type, o.language, o.content_access, o.url,
                   r.reach_raw, r.reach_unit, r.reach_source, r.reach_source_url, r.reach_date,
                   r.flag AS reach_flag, r.notes AS reach_notes
            FROM outlets o LEFT JOIN reach r USING(outlet_id) WHERE o.country=? ORDER BY o.outlet_id""",
            (db.COUNTRY,))
        items = db.rows(con, """
            SELECT i.item_id, i.outlet_id, i.title, i.url, i.published_at, i.word_count,
                   i.fetch_method, i.content_basis
            FROM items i WHERE i.country=?""", (db.COUNTRY,))
        sc = {r["item_id"]: r for r in db.rows(con, "SELECT * FROM scores2 WHERE prompt_version='score_v2'")}
        for r in db.rows(con, "SELECT * FROM scores"):
            sc.setdefault(r["item_id"], dict(r))
        tops = {}
        for r in db.rows(con, "SELECT item_id, topic, share FROM item_topics WHERE prompt_version='score_v2'"):
            tops.setdefault(r["item_id"], {})[r["topic"]] = round(r["share"], 3)
        mip = db.rows(con, "SELECT topic, mip_share FROM mip WHERE country=? ORDER BY mip_share DESC", (db.COUNTRY,))
        meta = {k: db.get_meta(con, k) for k in ("mip_survey_date", "signals_run")}
        spend = (con.execute("SELECT COALESCE(SUM(cost_usd),0) FROM scores2").fetchone()[0]
                 + con.execute("SELECT COALESCE(SUM(cost_usd),0) FROM scores").fetchone()[0])
        pub = con.execute("SELECT MIN(published_at),MAX(published_at) FROM items WHERE published_at IS NOT NULL").fetchone()
        sigs = {r["item_id"]: r["value"] for r in db.rows(con, "SELECT item_id, value FROM item_signals WHERE value>0")}

    labels = {}
    with open(db.DATA / "mip_table.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            labels[r["topic"]] = r["label"]

    oidx = {o["outlet_id"]: k for k, o in enumerate(outlets)}
    O = [[o["name"], o["type"], o["language"], o["content_access"],
          o["reach_raw"], o["reach_unit"] or "",
          1 if (o["reach_notes"] and "US visits (" in o["reach_notes"]) else 0,
          o["reach_source"] or "", o["reach_source_url"] or "", o["reach_date"] or "",
          o["reach_flag"] or "unsourced"] for o in outlets]

    I = []
    for it in items:
        s = sc.get(it["item_id"])
        if not s:
            continue
        t = tops.get(it["item_id"])
        if not t and s.get("topic"):
            t = {s["topic"]: 1.0}
        if not t:
            continue
        I.append([oidx[it["outlet_id"]], it["title"] or "(untitled)", it["url"],
                  (it["published_at"] or "")[:10], s.get("logos"), s.get("ethos"), s.get("pathos"),
                  t, 1 if it["content_basis"] == "summary_only" else 0,
                  it["word_count"] or 0, it["fetch_method"] or "",
                  (s.get("justification") or "")[:420],
                  round(sigs.get(it["item_id"], 0)) or 0])

    payload = {
        "outlets": O, "items": I,
        "mip": {m["topic"]: m["mip_share"] for m in mip},
        "labels": labels,
        "usAdults": audience.US_ADULTS,
        "defaults": {k: v[0] for k, v in audience.ASSUMPTIONS.items()},
        "meaning": {k: v[1] for k, v in audience.ASSUMPTIONS.items()},
        "surveyDate": meta.get("mip_survey_date"),
        "window": [(pub[0] or "")[:10], (pub[1] or "")[:10]],
        "spend": round(spend, 2),
        "generated": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "signals": bool((meta.get("signals_run") or {}).get("providers")),
    }
    return payload


if __name__ == "__main__":
    p = build()
    out = json.dumps(p, separators=(",", ":"), ensure_ascii=False)
    open("/tmp/build/payload.json", "w", encoding="utf-8").write(out)
    print("items:", len(p["items"]), "outlets:", len(p["outlets"]), "payload KB:", len(out) // 1024)
