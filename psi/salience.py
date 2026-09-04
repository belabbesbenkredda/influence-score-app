"""Stage 3 — Salience (S) from Gallup's "Most Important Problem" table.

Reads the Gallup MIP historical-trends page (live, falling back to the
cached copy in data/raw/), takes the most recent monthly column, keeps the
raw categories in data/mip_raw_gallup.csv and collapses them into ~15 topics
in data/mip_table.csv. S for an item = mip_share of its assigned topic.

Gallup prints '*' for <0.5% and '--' for no mentions; both are stored as
share NULL in mip_raw and contribute 0 to the collapsed topic.
"""
from __future__ import annotations

import csv
import html as htmllib
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

from psi import db

GALLUP_URL = "https://news.gallup.com/poll/1675/most-important-problem.aspx"
RAW_DIR = db.DATA / "raw"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}

# Collapse map: raw Gallup category -> PSI topic id.
# Categories not listed fall into "other". Net rows are skipped.
TOPIC_MAP = {
    "The government/Poor leadership": "government_leadership",
    "Economy in general": "economy",
    "Unemployment/Jobs": "economy",
    "Wage issues": "economy",
    "Gap between rich and poor": "economy",
    "Federal budget deficit/Federal debt": "economy",
    "Taxes": "economy",
    "Foreign Trade/Trade deficit": "economy",
    "Corporate corruption": "economy",
    "Lack of money": "economy",
    "Social Security": "economy",
    "High cost of living/Inflation": "inflation_cost_of_living",
    "Fuel/Oil prices": "inflation_cost_of_living",
    "Energy/Lack of energy sources": "inflation_cost_of_living",
    "Immigration": "immigration",
    "Healthcare": "healthcare",
    "Care for the elderly/Medicare": "healthcare",
    "Cancer/diseases/viruses": "healthcare",
    "Crime/Violence": "crime",
    "Drugs": "crime",
    "Police brutality": "crime",
    "Race relations/Racism": "race_relations",
    "Environment/Pollution/Climate change": "environment",
    "Education": "education",
    "Foreign policy/Foreign aid/Focus overseas": "foreign_policy_wars",
    "Situation with Russia": "foreign_policy_wars",
    "Situation with China": "foreign_policy_wars",
    "Situation in the Middle East": "foreign_policy_wars",
    "War in the Middle East": "foreign_policy_wars",
    "Wars/War (nonspecific)/Fear of war": "foreign_policy_wars",
    "Terrorism": "foreign_policy_wars",
    "National security": "foreign_policy_wars",
    "Lack of military defense": "foreign_policy_wars",
    "International issues, problems": "foreign_policy_wars",
    "Abortion": "abortion",
    "Guns/Gun control": "guns",
    "School shootings": "guns",
    "Unifying the country": "unifying_the_country",
    "Lack of respect for each other": "unifying_the_country",
    "Advancement of computers/technology": "ai_technology",
    "Elections/Election reform/Democracy": "democracy_elections",
    "Judicial system/Courts/Laws": "democracy_elections",
    "Ethics/moral/religious/family decline": "ethics_morality",
    "Poverty/Hunger/Homelessness": "poverty_homelessness",
    "Welfare": "poverty_homelessness",
}

# Rows that are not problems: skipped entirely.
SKIP_ROWS = {"Total", "No opinion"}

TOPIC_LABELS = {
    "government_leadership": "Government / poor leadership",
    "economy": "Economy (jobs, wages, debt, taxes, inequality)",
    "inflation_cost_of_living": "Inflation / cost of living / fuel prices",
    "immigration": "Immigration",
    "healthcare": "Healthcare",
    "crime": "Crime / violence / drugs",
    "race_relations": "Race relations / racism",
    "environment": "Environment / climate",
    "education": "Education",
    "foreign_policy_wars": "Foreign policy / wars / national security",
    "abortion": "Abortion",
    "guns": "Guns / gun control",
    "unifying_the_country": "Unifying the country",
    "ai_technology": "AI / technology",
    "democracy_elections": "Elections / democracy / courts",
    "ethics_morality": "Ethics / moral / family decline",
    "poverty_homelessness": "Poverty / hunger / homelessness",
    "other": "Other",
}

_MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def fetch_page() -> tuple[str, str]:
    """Return (html, provenance) for the newest survey month available.

    Gallup's CDN can serve two versions of the page on the same day (e.g. July
    and August columns). Every parseable copy is cached under its survey month
    and the newest month wins, so reruns are deterministic once a copy is in
    the repo.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    live_note = ""
    try:
        r = requests.get(GALLUP_URL, headers=UA, timeout=30)
        r.raise_for_status()
        latest, _ = parse_mip_table(r.text)
        month = month_label_to_date(latest)
        path = RAW_DIR / f"gallup_mip_1675_{month}.html"
        if not path.exists():
            path.write_text(r.text, encoding="utf-8")
        live_note = f"live fetch {datetime.now(timezone.utc).strftime('%Y-%m-%d')} served the {month} column"
    except (requests.RequestException, ValueError) as exc:
        live_note = f"live fetch unusable ({exc})"
    candidates = []
    for cached in RAW_DIR.glob("gallup_mip_1675_*.html"):
        try:
            latest, _ = parse_mip_table(cached.read_text(encoding="utf-8"))
            candidates.append((month_label_to_date(latest), cached))
        except ValueError:
            continue
    if not candidates:
        raise SystemExit(f"No parseable Gallup page available ({live_note}). Cannot build salience.")
    month, best = max(candidates)
    return best.read_text(encoding="utf-8"), f"{live_note}; using {best.name} ({month}, newest of {len(candidates)} cached copies)"


def parse_mip_table(page: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (latest_column_label, [(category, printed_value), ...]) for the latest month."""
    tables = re.findall(r"<table.*?</table>", page, re.S)
    table = next((t for t in tables if "Most Important Problem Table" in t), None)
    if table is None:
        raise ValueError("Gallup MIP table not found on page; layout changed?")
    rows = re.findall(r"<tr.*?</tr>", table, re.S)
    header_cells = None
    data: list[tuple[str, str]] = []
    for row in rows:
        cells = [htmllib.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]
        cells = [c for c in cells if c != ""]
        if not cells:
            continue
        if header_cells is None and any(_month_label(c) for c in cells):
            header_cells = [c for c in cells if _month_label(c)]
            continue
        if header_cells is None:
            continue
        label = cells[0]
        values = cells[1:]
        if not values or label.startswith("%"):
            continue
        data.append((label, values[0]))
    if header_cells is None or not data:
        raise ValueError("Could not parse Gallup MIP table header/rows.")
    return header_cells[0], data


def _month_label(cell: str) -> tuple[str, int] | None:
    """Gallup prints month headers as 'Jul 2026', and sometimes as 'Jul-26' or '26-Aug'."""
    cell = cell.strip()
    m = re.match(r"^([A-Z][a-z]{2}) (\d{4})$", cell) or re.match(r"^([A-Z][a-z]{2})-(\d{2})$", cell)
    if m and m.group(1) in _MONTHS:
        year = int(m.group(2))
        return m.group(1), (year if year > 100 else 2000 + year)
    m = re.match(r"^(\d{2})-([A-Z][a-z]{2})$", cell)
    if m and m.group(2) in _MONTHS:
        return m.group(2), 2000 + int(m.group(1))
    return None


def month_label_to_date(label: str) -> str:
    mon, year = _month_label(label)
    return f"{year}-{_MONTHS[mon]:02d}"


def parse_share(printed: str) -> float | None:
    printed = printed.strip()
    if printed in {"*", "--", "—", ""}:
        return None
    try:
        return float(printed) / 100.0
    except ValueError:
        return None


def run() -> None:
    page, provenance = fetch_page()
    latest, raw_rows = parse_mip_table(page)
    survey_date = month_label_to_date(latest)
    print(f"  Gallup MIP source: {provenance}; latest column = {latest}")

    raw_out = []
    topic_shares: dict[str, float] = {t: 0.0 for t in TOPIC_LABELS}
    topic_cats: dict[str, list[str]] = {t: [] for t in TOPIC_LABELS}
    for category, printed in raw_rows:
        if "(NET)" in category.upper() or category in SKIP_ROWS:
            continue
        share = parse_share(printed)
        topic = TOPIC_MAP.get(category, "other")
        raw_out.append({"category": category, "share": share, "share_label": printed, "topic": topic,
                        "source_url": GALLUP_URL, "survey_date": survey_date})
        if share is not None:
            topic_shares[topic] += share
        topic_cats[topic].append(category)

    db.DATA.mkdir(parents=True, exist_ok=True)
    with open(db.DATA / "mip_raw_gallup.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["category", "share_label", "share", "topic", "source_url", "survey_date"])
        w.writeheader()
        for r in raw_out:
            w.writerow(r)

    mip_rows = []
    for topic, share in sorted(topic_shares.items(), key=lambda kv: -kv[1]):
        mip_rows.append({"topic": topic, "label": TOPIC_LABELS[topic], "mip_share": round(share, 4),
                         "gallup_categories": "; ".join(topic_cats[topic]) or "(none mapped)",
                         "source_url": GALLUP_URL, "survey_date": survey_date})
    with open(db.DATA / "mip_table.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["topic", "label", "mip_share", "gallup_categories", "source_url", "survey_date"])
        w.writeheader()
        for r in mip_rows:
            w.writerow(r)

    with db.db() as con:
        con.execute("DELETE FROM mip WHERE country=?", (db.COUNTRY,))
        con.execute("DELETE FROM mip_raw WHERE country=?", (db.COUNTRY,))
        for r in raw_out:
            db.upsert(con, "mip_raw", {**r, "country": db.COUNTRY}, "category")
        for r in mip_rows:
            db.upsert(con, "mip", {"topic": r["topic"], "country": db.COUNTRY, "mip_share": r["mip_share"],
                                   "gallup_categories": r["gallup_categories"], "source_url": r["source_url"],
                                   "survey_date": r["survey_date"]}, "topic")
        db.set_meta(con, "mip_survey_date", survey_date)
        db.set_meta(con, "mip_provenance", provenance)

    print(f"  {len(raw_out)} raw categories -> {len(mip_rows)} topics; survey month {survey_date}")
    for r in mip_rows:
        print(f"    {r['mip_share']:.2f}  {r['topic']}")


if __name__ == "__main__":
    run()
