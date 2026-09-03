"""SQLite schema and helpers for the PSI Influence Engine.

Every table carries a `country` column so a second country (e.g. Canada)
can live in the same database without touching the pipeline code.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "out"
DB_PATH = OUT / "psi.sqlite"

COUNTRY = os.environ.get("PSI_COUNTRY", "US")

SCHEMA = """
CREATE TABLE IF NOT EXISTS outlets (
    outlet_id      TEXT PRIMARY KEY,
    country        TEXT NOT NULL DEFAULT 'US',
    name           TEXT NOT NULL,
    type           TEXT NOT NULL,   -- tv|cable|print_digital|radio|podcast|newsletter
    url            TEXT,
    rss_url        TEXT,
    youtube_channel TEXT,
    transcript_url TEXT,            -- index page of published transcripts/segments (TV/radio/podcast)
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS reach (
    outlet_id        TEXT PRIMARY KEY REFERENCES outlets(outlet_id),
    country          TEXT NOT NULL DEFAULT 'US',
    reach_raw        REAL,           -- NULL when unsourced
    reach_unit       TEXT,           -- e.g. avg_total_viewers, monthly_unique_visitors_us, weekly_listeners
    reach_source     TEXT,           -- short label, e.g. "Nielsen via Adweek"
    reach_source_url TEXT,
    reach_source_quote TEXT,         -- verbatim snippet that carries the figure
    reach_date       TEXT,           -- period the figure describes (YYYY-MM or YYYY-MM-DD)
    reach_norm_type  REAL,           -- 0-1 within type
    reach_norm       REAL,           -- 0-1 across types (see data/reach_sources.md)
    flag             TEXT,           -- ok | self_reported | unverified | unsourced
    source_tier      INTEGER,        -- 1 Pew .. 6 publisher-stated (brief §Stage 2)
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS type_weights (
    type        TEXT PRIMARY KEY,
    country     TEXT NOT NULL DEFAULT 'US',
    platform_share REAL,             -- % of adults who get news from this platform (sourced)
    weight      REAL,                -- platform_share / max(platform_share)
    source      TEXT,
    source_url  TEXT,
    survey_date TEXT,
    flag        TEXT
);

CREATE TABLE IF NOT EXISTS mip (
    topic       TEXT PRIMARY KEY,
    country     TEXT NOT NULL DEFAULT 'US',
    mip_share   REAL NOT NULL,       -- 0-1 share of respondents naming this topic
    gallup_categories TEXT,          -- raw categories collapsed into this topic
    source_url  TEXT,
    survey_date TEXT
);

CREATE TABLE IF NOT EXISTS mip_raw (
    category    TEXT PRIMARY KEY,
    country     TEXT NOT NULL DEFAULT 'US',
    share       REAL,                -- NULL when Gallup prints '*' (<0.5%) or '--'
    share_label TEXT,                -- the printed value ('11', '*', '--')
    topic       TEXT,                -- collapsed topic
    source_url  TEXT,
    survey_date TEXT
);

CREATE TABLE IF NOT EXISTS items (
    item_id      TEXT PRIMARY KEY,
    outlet_id    TEXT NOT NULL REFERENCES outlets(outlet_id),
    country      TEXT NOT NULL DEFAULT 'US',
    title        TEXT,
    url          TEXT,
    published_at TEXT,
    text         TEXT,
    word_count   INTEGER,
    fetch_method TEXT,               -- rss_fulltext | page_fetch | transcript_page | gdelt | youtube_transcript
    fetched_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_outlet ON items(outlet_id);

CREATE TABLE IF NOT EXISTS fetch_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    outlet_id TEXT,
    url       TEXT,
    status    TEXT,                  -- ok | miss
    reason    TEXT,
    ts        TEXT
);

CREATE TABLE IF NOT EXISTS scores (
    item_id        TEXT PRIMARY KEY REFERENCES items(item_id),
    topic          TEXT,
    logos          INTEGER,
    ethos          INTEGER,
    pathos         INTEGER,
    d              INTEGER,          -- logos + ethos + pathos (0-30)
    justification  TEXT,
    raw_json       TEXT,
    model          TEXT,
    prompt_version TEXT,
    input_tokens   INTEGER,
    output_tokens  INTEGER,
    cache_read_tokens INTEGER,
    cache_write_tokens INTEGER,
    cost_usd       REAL,
    text_truncated INTEGER DEFAULT 0,
    scored_at      TEXT
);

CREATE TABLE IF NOT EXISTS outlet_scores (
    outlet_id   TEXT PRIMARY KEY REFERENCES outlets(outlet_id),
    country     TEXT NOT NULL DEFAULT 'US',
    r           REAL,
    s           REAL,
    d           REAL,
    i           REAL,
    rank        INTEGER,
    n_items     INTEGER,
    n_scored    INTEGER,
    confidence  TEXT,                -- high | medium | low
    flags       TEXT,
    computed_at TEXT
);

CREATE TABLE IF NOT EXISTS run_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=60)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    return con


@contextmanager
def db(path: Path | str = DB_PATH):
    con = connect(path)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def set_meta(con: sqlite3.Connection, key: str, value) -> None:
    con.execute(
        "INSERT INTO run_meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value) if not isinstance(value, str) else value),
    )


def get_meta(con: sqlite3.Connection, key: str, default=None):
    row = con.execute("SELECT value FROM run_meta WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except (TypeError, ValueError):
        return row["value"]


def rows(con: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in con.execute(sql, params).fetchall()]


def upsert(con: sqlite3.Connection, table: str, record: dict, key: str) -> None:
    cols = list(record.keys())
    placeholders = ",".join("?" for _ in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != key)
    con.execute(
        f"INSERT INTO {table}({','.join(cols)}) VALUES({placeholders}) "
        f"ON CONFLICT({key}) DO UPDATE SET {updates}",
        [record[c] for c in cols],
    )
