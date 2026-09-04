"""Turn the research-agent outputs into the editable seed CSVs.

The outlet universe and reach figures were produced by parallel research
agents (see RUNLOG.md). Their structured outputs are archived verbatim in
data/raw/research_outputs.json. This script converts that archive into:

  data/outlets_seed.csv     one row per outlet
  data/reach_seed.csv       one row per outlet with figure, source URL, quote, verdict
  data/type_weights.csv     Pew platform shares per outlet type

Usage:
  python -m psi.tools.ingest_research --journal <path/to/journal.jsonl>   # build the archive from the workflow journal
  python -m psi.tools.ingest_research                                       # rebuild CSVs from the archive

Editing the CSVs by hand afterwards is expected; rerunning this script
overwrites them, so do that only when re-ingesting new research.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from psi import db  # noqa: E402

ARCHIVE = db.DATA / "raw" / "research_outputs.json"

# Outlets returned by the research agents but excluded from the universe, with the reason.
EXCLUDE = {
    # brand duplicates (same product already in the list under another type)
    "cbs_60_minutes": "show inside CBS News; network-level outlets only",
    "the_bulwark_newsletter": "same Substack product as `bulwark` (print_digital)",
    "meidas_plus": "same newsroom as `meidastouch` (podcast)",
    "honestly_bari_weiss": "on hiatus since early 2026 (agent: status uncertain); The Free Press is in the list",
    # not US outlets (large US audiences, but the brief is the American public sphere); Guardian US and BBC kept with a note
    "economist": "UK weekly; US web reach small and paywalled",
    "ft": "UK daily; US web reach small and paywalled",
    "rest_is_politics_us": "UK production (Goalhanger)",
    # aggregators with no original opinion output
    "msn": "aggregator",
    "yahoo_news": "aggregator",
    "1440_daily_digest": "aggregator newsletter, explicitly non-opinion",
    # entertainment/interview shows with episodic politics, not political coverage outlets
    "shawn_ryan_show": "interview show, politics episodic",
    "theo_von": "comedy interview show",
    "pbd_podcast": "business/interview show",
    "pivot": "tech/business",
    # not opinion-forming as a channel
    "cspan": "raw feed, not Nielsen-rated (critic)",
    # small audiences relative to the list (critic), trimmed to keep the universe near ~110
    "joe_pags_show": "small audience",
    "michael_berry_show": "regional, no text available",
    "current_affairs": "small audience",
    "raw_story": "small audience",
    "compact": "small audience",
    "the_19th": "small audience",
}
OUTLET_COLS = ["outlet_id", "name", "type", "url", "rss_url", "youtube_channel", "youtube_channel_id", "transcript_url", "status", "notes"]
REACH_COLS = ["outlet_id", "reach_raw", "reach_unit", "reach_source", "reach_source_url", "reach_source_quote", "reach_date",
              "source_tier", "flag", "fetched_source", "verify_verdict", "verify_evidence", "notes"]
WEIGHT_COLS = ["type", "platform_share", "measure", "source", "source_url", "quote", "survey_date", "flag", "notes"]


def read_journal(path: Path) -> dict:
    """Collect every agent result from a workflow journal, classified by shape."""
    out = {"outlets": [], "reach": [], "verify": [], "weights": [], "critic": []}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        res = j.get("result") if isinstance(j, dict) else None
        if not isinstance(res, dict):
            continue
        if "outlets" in res:
            out["outlets"].append(res)
        elif "reach" in res:
            out["reach"].append(res)
        elif "results" in res:
            out["verify"].append(res)
        elif "platforms" in res:
            out["weights"].append(res)
        elif "missing_from_brief" in res:
            out["critic"].append(res)
    return out


def merge(archive: dict) -> tuple[list[dict], list[dict], list[dict]]:
    outlets: dict[str, dict] = {}
    for block in archive["outlets"]:
        for o in block["outlets"]:
            oid = (o.get("outlet_id") or "").strip().lower()
            if not oid or oid in EXCLUDE:
                continue
            if oid in outlets:
                # keep the first, but fill gaps
                for k, v in o.items():
                    if outlets[oid].get(k) in (None, "", False, 0) and v not in (None, "", False, 0):
                        outlets[oid][k] = v
                continue
            outlets[oid] = dict(o)

    reach: dict[str, dict] = {}
    for block in archive["reach"]:
        for r in block["reach"]:
            oid = (r.get("outlet_id") or "").strip().lower()
            if not oid:
                continue
            prev = reach.get(oid)
            if prev is None or (prev.get("reach_raw") is None and r.get("reach_raw") is not None):
                reach[oid] = dict(r)

    verify: dict[str, dict] = {}
    for block in archive["verify"]:
        for v in block["results"]:
            oid = (v.get("outlet_id") or "").strip().lower()
            if oid and (oid not in verify or v.get("verdict") == "refuted"):
                verify[oid] = v

    weights: dict[str, dict] = {}
    for block in archive["weights"]:
        for w in block["platforms"]:
            weights[w["type"]] = w

    outlet_rows = []
    for oid, o in sorted(outlets.items(), key=lambda kv: (kv[1].get("type", ""), kv[0])):
        notes = o.get("notes") or ""
        extras = []
        if o.get("rss_url") and not o.get("rss_verified"):
            extras.append("rss unverified")
        if o.get("rss_has_fulltext"):
            extras.append("rss has full text")
        if o.get("transcript_url") and not o.get("transcript_verified"):
            extras.append("transcript index unverified")
        if extras:
            notes = (notes + " | " if notes else "") + "; ".join(extras)
        outlet_rows.append({
            "outlet_id": oid, "name": o.get("name"), "type": o.get("type"), "url": o.get("url"),
            "rss_url": o.get("rss_url") if o.get("rss_verified") else (o.get("rss_url") or ""),
            "youtube_channel": o.get("youtube_channel") or "", "youtube_channel_id": o.get("youtube_channel_id") or "",
            "transcript_url": o.get("transcript_url") or "", "status": o.get("status") or "active", "notes": notes,
        })

    reach_rows = []
    for oid in outlets:
        r = reach.get(oid, {})
        v = verify.get(oid, {})
        raw = r.get("reach_raw")
        flag = r.get("flag") or "unsourced"
        if raw is None:
            flag = "unsourced"
        elif not r.get("fetched_source") and flag == "ok":
            flag = "unverified"   # the researcher never saw the page; the checker may still confirm it
        reach_rows.append({
            "outlet_id": oid, "reach_raw": "" if raw is None else raw, "reach_unit": r.get("reach_unit") or "",
            "reach_source": r.get("reach_source") or "", "reach_source_url": r.get("reach_source_url") or "",
            "reach_source_quote": (r.get("reach_source_quote") or "").replace("\n", " "), "reach_date": r.get("reach_date") or "",
            "source_tier": r.get("source_tier") or "", "flag": flag, "fetched_source": r.get("fetched_source", ""),
            "verify_verdict": v.get("verdict") or "", "verify_evidence": (v.get("evidence") or "").replace("\n", " "),
            "notes": (r.get("notes") or "").replace("\n", " "),
        })

    weight_rows = [{c: (w.get(c) if w.get(c) is not None else "") for c in WEIGHT_COLS} for w in weights.values()]
    return outlet_rows, reach_rows, weight_rows


def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--journal", type=Path, help="workflow journal.jsonl to archive into data/raw/research_outputs.json")
    ap.add_argument("--dry-run", action="store_true", help="print counts only, write nothing")
    args = ap.parse_args()
    if args.journal:
        archive = read_journal(args.journal)
        if not args.dry_run:
            ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
            ARCHIVE.write_text(json.dumps(archive, indent=1), encoding="utf-8")
    else:
        archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    outlet_rows, reach_rows, weight_rows = merge(archive)
    n_sourced = sum(1 for r in reach_rows if r["reach_raw"] != "")
    verdicts = {}
    for r in reach_rows:
        verdicts[r["verify_verdict"] or "(none)"] = verdicts.get(r["verify_verdict"] or "(none)", 0) + 1
    print(f"outlets: {len(outlet_rows)}  reach rows: {len(reach_rows)} (sourced {n_sourced})  verdicts: {verdicts}  weights: {len(weight_rows)}")
    for c in archive.get("critic", []):
        print("critic missing:", c.get("missing_from_brief"))
        print("critic duplicates:", c.get("duplicates"))
        print("critic suspicious:", c.get("suspicious"))
    if args.dry_run:
        return
    write_csv(db.DATA / "outlets_seed.csv", outlet_rows, OUTLET_COLS)
    write_csv(db.DATA / "reach_seed.csv", reach_rows, REACH_COLS)
    write_csv(db.DATA / "type_weights.csv", weight_rows, WEIGHT_COLS)
    print("wrote data/outlets_seed.csv, data/reach_seed.csv, data/type_weights.csv")


if __name__ == "__main__":
    main()
