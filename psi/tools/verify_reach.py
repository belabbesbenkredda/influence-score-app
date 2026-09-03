"""Deterministic fact-check of data/reach_seed.csv.

For every row with a figure, re-fetch reach_source_url and check that the
number appears in the page text in any common formatting (1,490,000 /
1.49 million / 1.49M / 1,490K ...). Writes verify_verdict and
verify_evidence back into the seed:

  verified      page fetched and the figure found
  refuted       page fetched but the figure is absent  -> reach.py nulls the figure
  unverifiable  page could not be fetched (blocked/timeout) -> flag unverified

No model is involved; this is a plain text search.
"""
from __future__ import annotations

import csv
import html as htmllib
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from psi import db  # noqa: E402
from psi.tools.ingest_research import REACH_COLS, write_csv  # noqa: E402

SEED = db.DATA / "reach_seed.csv"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
PLAIN = {"User-Agent": "psi-influence-engine/0.2 (+https://publicspheres.org)"}


def variants(n: float) -> list[str]:
    n = float(n)
    out = {f"{n:,.0f}", f"{n:.0f}"}
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= div:
            v = n / div
            for fmt in ("{:.2f}", "{:.1f}", "{:.0f}"):
                s = fmt.format(v).rstrip("0").rstrip(".") if "." in fmt.format(v) else fmt.format(v)
                out.update({f"{s}{suf}", f"{s} {suf}", f"{s}{suf.lower()}", f"{s} {'billion' if suf == 'B' else 'million' if suf == 'M' else 'thousand'}"})
    return sorted(out, key=len, reverse=True)


def quote_tokens(quote: str) -> tuple[str | None, str | None]:
    """The longest number and the longest word in the recorded quote."""
    nums = re.findall(r"\d[\d,.]*", quote or "")
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]{5,}", quote or "")]
    return (max(nums, key=len) if nums else None, max(words, key=len) if words else None)


def check(url: str, raw: float, quote: str = "") -> tuple[str, str]:
    page = status = None
    for headers in (UA, PLAIN):
        try:
            r = requests.get(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            return "unverifiable", f"fetch error {type(exc).__name__}"
        status = r.status_code
        if r.status_code == 200 and len(r.text) > 500:
            page = r.text
            break
    if page is None:
        return "unverifiable", f"http {status}"
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", page))
    text = re.sub(r"\s+", " ", text)

    # 1. the recorded quote itself, or its distinctive number plus a distinctive word
    if quote:
        q = re.sub(r"\s+", " ", htmllib.unescape(quote)).strip()
        i = text.find(q)
        if i >= 0:
            return "verified", f"exact quote found: {q[:200]}"
        num, word = quote_tokens(q)
        if num and word and num in text and word in text:
            j = text.find(num)
            return "verified", f"figure {num} and '{word}' both present: {text[max(0, j - 100):j + 150].strip()}"
    # 2. the figure in any common formatting
    for v in variants(raw):
        i = text.find(v)
        if i >= 0:
            return "verified", text[max(0, i - 120):i + len(v) + 120].strip()
    return "refuted", f"quote absent and none of {variants(raw)[:5]} found in fetched page ({len(text)} chars)"


def main() -> None:
    with open(SEED, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    counts = {"verified": 0, "refuted": 0, "unverifiable": 0, "skipped": 0}
    for r in rows:
        if r["reach_raw"] == "" or not r["reach_source_url"]:
            r["verify_verdict"], r["verify_evidence"] = "", ""
            continue
        if r.get("verify_verdict") == "verified" and r.get("verify_evidence"):
            counts["skipped"] += 1
            continue
        verdict, evidence = check(r["reach_source_url"], float(r["reach_raw"]), r.get("reach_source_quote", ""))
        r["verify_verdict"], r["verify_evidence"] = verdict, evidence.replace("\n", " ")[:400]
        counts[verdict] += 1
        print(f"  {r['outlet_id']:24s} {verdict:12s} {evidence[:110]}")
        time.sleep(0.5)
    write_csv(SEED, rows, REACH_COLS)
    print("verification:", counts)


if __name__ == "__main__":
    main()
