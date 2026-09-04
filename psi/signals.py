"""Per-item reach signals — the distribution half of R.

The audience model in `psi/audience.py` sets the LEVEL: how many people a
typical item from an outlet reaches. It cannot say which of that outlet's items
actually travelled. That needs a per-item signal, and

    R_item = level_for_outlet x (item's signal / mean signal for that outlet)

so an episode that did three times its channel's usual numbers carries three
times the reach, and the outlet's own aggregate still anchors the scale.

Without signals every item from an outlet inherits the same R, which is exactly
the flat ranking v0.3 produced. This module is the seam where that is fixed.

WHY IT IS EMPTY BY DEFAULT
Every free source of per-item numbers refuses this runner: the YouTube watch
page returns 429, Reddit's public JSON 403, GDELT 429, Pushshift 403. Rather
than scrape around blocks or invent a proxy, the providers below take proper
credentials and stay switched off until they are configured. Nothing here
fabricates a signal, and `run.py signals` reports honestly how many items it
could and could not measure.

CONFIGURE ONE OF THESE
  PSI_YOUTUBE_API_KEY   YouTube Data API v3. Free tier, 10,000 units/day;
                        videos.list?part=statistics costs 1 unit per call and
                        takes 50 ids at once, so a month of episodes is trivial.
                        Covers every podcast, TV and radio outlet with a channel.
  PSI_ANALYTICS_URL     A per-URL pageview endpoint (Chartbeat, Parse.ly, or a
  PSI_ANALYTICS_KEY     publisher's own API). Covers articles, which is the
                        half YouTube cannot reach.
  PSI_SOCIAL_URL        A social-listening endpoint returning engagement counts
  PSI_SOCIAL_KEY        for a URL. A weaker signal than pageviews: it measures
                        circulation among posters, not readers.

Adding a provider means implementing `collect()` and registering it; the rest
of the pipeline needs no change.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from psi import db

TIMEOUT = 30
YOUTUBE_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"


class Provider:
    """A source of per-item audience numbers."""

    name = "provider"
    unit = "unknown"

    def configured(self) -> bool:
        raise NotImplementedError

    def handles(self, item: dict) -> bool:
        raise NotImplementedError

    def collect(self, items: list[dict]) -> dict[str, float]:
        """item_id -> signal value. Omit anything the provider could not measure."""
        raise NotImplementedError


class YouTubeDataAPI(Provider):
    """Real view counts per video, from the official API.

    The watch page is rate-limited to death from a data centre; the API is not,
    and it is free at the volumes this index needs.
    """

    name = "youtube_data_api"
    unit = "video_views"

    def configured(self) -> bool:
        return bool(os.environ.get("PSI_YOUTUBE_API_KEY"))

    @staticmethod
    def video_id(url: str) -> str | None:
        if not url:
            return None
        m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url) or re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
        return m.group(1) if m else None

    def handles(self, item: dict) -> bool:
        return self.video_id(item.get("url")) is not None

    def collect(self, items: list[dict]) -> dict[str, float]:
        key = os.environ["PSI_YOUTUBE_API_KEY"]
        by_vid = {}
        for it in items:
            vid = self.video_id(it["url"])
            if vid:
                by_vid.setdefault(vid, []).append(it["item_id"])
        out: dict[str, float] = {}
        vids = list(by_vid)
        for i in range(0, len(vids), 50):                      # the API takes 50 ids per call
            batch = vids[i:i + 50]
            try:
                r = requests.get(YOUTUBE_ENDPOINT, timeout=TIMEOUT,
                                 params={"part": "statistics", "id": ",".join(batch), "key": key})
            except requests.RequestException as exc:
                print(f"    youtube: request failed ({type(exc).__name__}); {len(batch)} ids unmeasured")
                continue
            if r.status_code != 200:
                print(f"    youtube: HTTP {r.status_code} — {r.text[:160]}")
                continue
            for entry in r.json().get("items", []):
                views = entry.get("statistics", {}).get("viewCount")
                if views is None:
                    continue
                for item_id in by_vid.get(entry["id"], []):
                    out[item_id] = float(views)
            time.sleep(0.2)
        return out


class UrlMetricProvider(Provider):
    """A generic per-URL metric endpoint: analytics or social listening.

    Expects a JSON response containing a number under one of the usual keys.
    Point PSI_ANALYTICS_URL at an endpoint taking `?url=`; the key, if any, is
    sent as a bearer token.
    """

    VALUE_KEYS = ("pageviews", "views", "visits", "engagements", "total", "count", "score")

    def __init__(self, name: str, unit: str, url_env: str, key_env: str):
        self.name, self.unit, self.url_env, self.key_env = name, unit, url_env, key_env

    def configured(self) -> bool:
        return bool(os.environ.get(self.url_env))

    def handles(self, item: dict) -> bool:
        scheme = urlparse(item.get("url") or "").scheme
        return scheme in {"http", "https"} and YouTubeDataAPI.video_id(item.get("url")) is None

    @classmethod
    def _extract(cls, payload) -> float | None:
        if isinstance(payload, (int, float)):
            return float(payload)
        if isinstance(payload, dict):
            for k in cls.VALUE_KEYS:
                if k in payload:
                    got = cls._extract(payload[k])
                    if got is not None:
                        return got
            for v in payload.values():
                got = cls._extract(v)
                if got is not None:
                    return got
        if isinstance(payload, list):
            for v in payload:
                got = cls._extract(v)
                if got is not None:
                    return got
        return None

    def collect(self, items: list[dict]) -> dict[str, float]:
        endpoint = os.environ[self.url_env]
        key = os.environ.get(self.key_env)
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        out: dict[str, float] = {}
        for it in items:
            try:
                r = requests.get(endpoint, params={"url": it["url"]}, headers=headers, timeout=TIMEOUT)
            except requests.RequestException:
                continue
            if r.status_code != 200:
                continue
            try:
                value = self._extract(r.json())
            except ValueError:
                continue
            if value is not None:
                out[it["item_id"]] = value
            time.sleep(0.1)
        return out


def providers() -> list[Provider]:
    return [
        YouTubeDataAPI(),
        UrlMetricProvider("analytics", "pageviews", "PSI_ANALYTICS_URL", "PSI_ANALYTICS_KEY"),
        UrlMetricProvider("social", "engagements", "PSI_SOCIAL_URL", "PSI_SOCIAL_KEY"),
    ]


def run() -> None:
    """Stage: collect whatever per-item signals the configured providers can supply."""
    now = datetime.now(timezone.utc).isoformat()
    active = [p for p in providers() if p.configured()]
    with db.db() as con:
        items = db.rows(con, "SELECT item_id, outlet_id, url FROM items WHERE country=?", (db.COUNTRY,))
    if not active:
        print("  no signal provider configured — every item keeps its outlet's average reach.")
        print("  set PSI_YOUTUBE_API_KEY (free, covers every channel-based outlet), and/or")
        print("  PSI_ANALYTICS_URL + PSI_ANALYTICS_KEY for per-article pageviews.")
        print(f"  {len(items)} items are currently unmeasured at item level.")
        with db.db() as con:
            db.set_meta(con, "signals_run", {"at": now, "providers": [], "measured": 0, "items": len(items)})
        return

    total = 0
    for p in active:
        mine = [it for it in items if p.handles(it)]
        if not mine:
            continue
        print(f"  {p.name}: {len(mine)} candidate items")
        got = p.collect(mine)
        with db.db() as con:
            for item_id, value in got.items():
                db.upsert(con, "item_signals", {"item_id": item_id, "provider": p.name, "unit": p.unit,
                                                "value": value, "collected_at": now},
                          ["item_id", "provider"])
        total += len(got)
        print(f"    measured {len(got)} of {len(mine)}")
    with db.db() as con:
        db.set_meta(con, "signals_run", {"at": now, "providers": [p.name for p in active],
                                         "measured": total, "items": len(items)})
    print(f"  {total} of {len(items)} items now carry a per-item signal")


def distribution(con, outlet_ids: list[str]) -> dict[str, float]:
    """item_id -> multiplier on its outlet's average reach.

    An item with the outlet's typical signal gets 1.0. Outlets with no measured
    items are absent from the result and stay flat. Multipliers are clamped to
    [0.1, 10] so one viral outlier cannot swamp the index.
    """
    rows = db.rows(con, """SELECT s.item_id, i.outlet_id, s.value
                           FROM item_signals s JOIN items i USING(item_id)
                           WHERE s.value > 0""")
    by_outlet: dict[str, list] = {}
    for r in rows:
        by_outlet.setdefault(r["outlet_id"], []).append(r)
    out = {}
    for oid, rs in by_outlet.items():
        mean = sum(r["value"] for r in rs) / len(rs)
        if mean <= 0:
            continue
        for r in rs:
            out[r["item_id"]] = max(0.1, min(10.0, r["value"] / mean))
    return out


if __name__ == "__main__":
    run()
