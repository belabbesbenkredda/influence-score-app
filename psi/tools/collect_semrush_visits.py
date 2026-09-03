"""Collect monthly visits for print/digital outlets from Semrush's public website-overview pages.

Semrush prints a sentence such as "In July nytimes.com received 493.01M visits" on
https://www.semrush.com/website/<domain>/overview/. That gives one third-party
traffic estimate in one unit (monthly visits) for every digital outlet, which is
what the within-type normalisation needs. It is an estimate, like Similarweb's;
see data/reach_sources.md. Writes data/raw/semrush_visits.json.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from psi import db  # noqa: E402

OUT = db.DATA / "raw" / "semrush_visits.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
# outlets whose site is a section of a bigger domain, or whose canonical domain differs from the seed url
DOMAIN_OVERRIDES = {
    "npr": "npr.org", "the_daily_show": None,
}
MULT = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}


def domain_for(outlet: dict) -> str | None:
    if outlet["outlet_id"] in DOMAIN_OVERRIDES:
        return DOMAIN_OVERRIDES[outlet["outlet_id"]]
    host = urlparse(outlet["url"]).netloc.lower().removeprefix("www.")
    return host or None


def fetch_visits(domain: str) -> dict:
    url = f"https://www.semrush.com/website/{domain}/overview/"
    try:
        r = requests.get(url, headers=UA, timeout=30)
    except requests.RequestException as exc:
        return {"url": url, "raw": None, "quote": None, "error": type(exc).__name__}
    if r.status_code != 200:
        return {"url": url, "raw": None, "quote": None, "error": f"http_{r.status_code}"}
    text = re.sub(r"<[^>]+>", " ", r.text)
    text = re.sub(r"\s+", " ", text)
    # Layout A (large domains): "In July nytimes.com received 493.01M visits"
    m = re.search(r"In (January|February|March|April|May|June|July|August|September|October|November|December) " + re.escape(domain) + r" received ([\d.,]+)([KMB]?) visits", text)
    if m:
        raw = float(m.group(2).replace(",", "")) * MULT[m.group(3)]
        return {"url": url, "raw": raw, "quote": m.group(0), "month": m.group(1), "error": None}
    # Layout B (smaller domains): "Total Visits last 2 months Jun 3.57M May 3.47M"
    m = re.search(r"Total Visits last 2 months (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) ([\d.,]+)([KMB]?)", text)
    if m:
        raw = float(m.group(2).replace(",", "")) * MULT[m.group(3)]
        month = {"Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April", "May": "May", "Jun": "June",
                 "Jul": "July", "Aug": "August", "Sep": "September", "Oct": "October", "Nov": "November", "Dec": "December"}[m.group(1)]
        return {"url": url, "raw": raw, "quote": m.group(0), "month": month, "error": None}
    return {"url": url, "raw": None, "quote": None, "error": "no_visits_figure_on_page"}


def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with db.db() as con:
        outlets = db.rows(con, "SELECT outlet_id, name, type, url FROM outlets WHERE country=? AND status!='defunct' AND type='print_digital' ORDER BY outlet_id", (db.COUNTRY,))
    results = {}
    for o in outlets:
        dom = domain_for(o)
        if not dom:
            continue
        res = fetch_visits(dom)
        res.update({"domain": dom, "unit": "monthly_visits_semrush", "source": "Semrush website overview (monthly visits estimate)",
                    "tier": 3, "flag": "ok" if res["raw"] else "unsourced", "date": today,
                    "period": f"2026-{['January','February','March','April','May','June','July','August','September','October','November','December'].index(res['month'])+1:02d}" if res.get("month") else None})
        results[o["outlet_id"]] = res
        print(f"  {o['outlet_id']:22s} {dom:28s} {res['raw'] if res['raw'] is not None else 'null':>14} {res.get('quote') or res.get('error')}")
        time.sleep(0.8)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({sum(1 for r in results.values() if r['raw'])} sourced of {len(results)})")


if __name__ == "__main__":
    main()
