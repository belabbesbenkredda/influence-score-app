"""Collect public audience counts that need no press source:

  podcast    -> YouTube channel subscriber count (public, tier 5)
  newsletter -> subscriber count printed on the publication's own page (self_reported, tier 6)

Writes data/raw/public_counts.json with the URL fetched, the verbatim
snippet, and the fetch date. `merge_reach.py` folds these into
data/reach_seed.csv. Nothing is guessed: a channel or page that does not
expose a number yields null.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from psi import db  # noqa: E402

OUT = db.DATA / "raw" / "public_counts.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}


def parse_count(s: str) -> float | None:
    s = s.strip().replace(",", "")
    m = re.match(r"^([\d.]+)\s*([KMB]?)\+?$", s, re.I)
    if not m:
        return None
    n = float(m.group(1))
    return n * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2).upper()]


def youtube_subscribers(channel_id: str) -> dict:
    url = f"https://www.youtube.com/channel/{channel_id}/about"
    try:
        r = requests.get(url, headers=UA, timeout=25)
    except requests.RequestException as exc:
        return {"url": url, "raw": None, "quote": None, "error": type(exc).__name__}
    if r.status_code != 200:
        return {"url": url, "raw": None, "quote": None, "error": f"http_{r.status_code}"}
    m = re.search(r'"subscriberCountText":\s*(?:\{"simpleText":\s*"([^"]+)"|"([^"]+)")', r.text)
    text = (m.group(1) or m.group(2)) if m else None
    if not text:
        return {"url": url, "raw": None, "quote": None, "error": "no_subscriber_count_in_page"}
    raw = parse_count(text.replace("subscribers", "").strip())
    title = re.search(r'<meta property="og:title" content="([^"]+)"', r.text) or re.search(r'"channelMetadataRenderer":\{"title":"([^"]+)"', r.text)
    return {"url": url, "raw": raw, "quote": f"{htmllib.unescape(title.group(1)) if title else channel_id}: {text}", "error": None}


def newsletter_subscribers(site: str) -> dict:
    try:
        r = requests.get(site, headers=UA, timeout=25, allow_redirects=True)
    except requests.RequestException as exc:
        return {"url": site, "raw": None, "quote": None, "error": type(exc).__name__}
    if r.status_code != 200:
        return {"url": site, "raw": None, "quote": None, "error": f"http_{r.status_code}"}
    page = htmllib.unescape(r.text)
    cands = re.findall(r"((?:Over|More than|Nearly)?\s*[\d][\d,.]*\+?\s*[KkMm]?\s+(?:paid\s+)?subscribers)", page)
    cands = [c.strip() for c in cands]
    if not cands:
        return {"url": r.url, "raw": None, "quote": None, "error": "no_subscriber_text_on_page"}
    best = max(cands, key=lambda c: parse_count(re.sub(r"^(Over|More than|Nearly)\s*", "", c).replace("subscribers", "").replace("paid", "").strip()) or 0)
    num = re.sub(r"^(Over|More than|Nearly)\s*", "", best).replace("subscribers", "").replace("paid", "").strip()
    return {"url": r.url, "raw": parse_count(num), "quote": best, "paid_only": "paid" in best, "error": None}


def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with db.db() as con:
        outlets = db.rows(con, "SELECT outlet_id, name, type, url, youtube_channel_id FROM outlets WHERE country=? AND status!='defunct'", (db.COUNTRY,))
    results = {}
    for o in outlets:
        if o["type"] == "podcast" and o["youtube_channel_id"]:
            res = youtube_subscribers(o["youtube_channel_id"])
            res.update({"unit": "youtube_subscribers", "source": "YouTube channel page (public count)", "tier": 5, "flag": "ok" if res["raw"] else "unsourced"})
        elif o["type"] == "newsletter":
            res = newsletter_subscribers(o["url"])
            unit = "subscribers_self_reported" + ("_paid_only" if res.get("paid_only") else "")
            res.update({"unit": unit, "source": "Publication page (self-reported)", "tier": 6, "flag": "self_reported" if res["raw"] else "unsourced"})
        else:
            continue
        res["date"] = today
        results[o["outlet_id"]] = res
        print(f"  {o['outlet_id']:26s} {o['type']:10s} {res['raw'] if res['raw'] is not None else 'null':>12} {res.get('quote') or res.get('error')}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({sum(1 for r in results.values() if r['raw'])} sourced of {len(results)})")


if __name__ == "__main__":
    main()
