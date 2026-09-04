"""YouTube Data API v3 — real per-episode audience for channel-based outlets.

Why this matters more than it first appears. Podcast reach is currently
`subscribers x PODCAST_EPISODE_VIEW_RATE x (1 + PODCAST_AUDIO_MULTIPLE)`, where
the view rate is a guess and subscribers are a stock that never decays. BB's
objection (decision D10) was exact: the correct unit is the audience of an
episode, not the size of a following. This module replaces the guess with
measurement.

For every outlet with a channel id it walks the channel's uploads playlist,
keeps the videos published inside the sampling window, and reads their view
counts. The outlet's per-item audience becomes the median of those — median
rather than mean so one viral episode does not redefine the show — and each
video's own count becomes a per-item signal, so an episode that broke out
carries the reach it actually earned.

Quota: the free tier is 10,000 units a day. Walking a channel costs 1 unit per
50 videos and reading statistics costs 1 unit per 50 ids, so the whole US
universe costs well under 100 units. `search.list` costs 100 units a call and is
deliberately not used.

What this does NOT give us: captions. Downloading a transcript through the API
needs OAuth as the channel owner, so discursiveness for these outlets still
depends on published transcripts or our own transcription. This fixes R, not D.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from statistics import median

import requests

from psi import db

API = "https://www.googleapis.com/youtube/v3"
TIMEOUT = 30
WINDOW_DAYS = int(os.environ.get("PSI_YT_WINDOW_DAYS", "14"))
MAX_VIDEOS_PER_CHANNEL = 60


class QuotaExceeded(RuntimeError):
    pass


def _get(path: str, params: dict, key: str) -> dict:
    params = dict(params, key=key)
    r = requests.get(f"{API}/{path}", params=params, timeout=TIMEOUT)
    if r.status_code == 403 and "quota" in r.text.lower():
        raise QuotaExceeded(r.text[:200])
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def uploads_playlist(channel_id: str, key: str) -> str | None:
    data = _get("channels", {"part": "contentDetails", "id": channel_id}, key)
    items = data.get("items") or []
    if not items:
        return None
    return items[0]["contentDetails"]["relatedPlaylists"].get("uploads")


def recent_videos(playlist_id: str, key: str, since: datetime) -> list[dict]:
    """Videos from the uploads playlist, newest first, stopping once past the window."""
    out, page = [], None
    while len(out) < MAX_VIDEOS_PER_CHANNEL:
        params = {"part": "contentDetails,snippet", "playlistId": playlist_id, "maxResults": 50}
        if page:
            params["pageToken"] = page
        data = _get("playlistItems", params, key)
        stop = False
        for it in data.get("items", []):
            published = it["contentDetails"].get("videoPublishedAt") or it["snippet"].get("publishedAt")
            if not published:
                continue
            when = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if when < since:
                stop = True
                continue
            out.append({"video_id": it["contentDetails"]["videoId"],
                        "title": it["snippet"].get("title", ""),
                        "published": when.isoformat()})
        page = data.get("nextPageToken")
        if stop or not page:
            break
        time.sleep(0.1)
    return out


def statistics(video_ids: list[str], key: str) -> dict[str, dict]:
    stats = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        data = _get("videos", {"part": "statistics,contentDetails", "id": ",".join(batch)}, key)
        for entry in data.get("items", []):
            st = entry.get("statistics", {})
            stats[entry["id"]] = {
                "views": float(st["viewCount"]) if "viewCount" in st else None,
                "likes": float(st["likeCount"]) if "likeCount" in st else None,
                "comments": float(st["commentCount"]) if "commentCount" in st else None,
                "duration": entry.get("contentDetails", {}).get("duration"),
            }
        time.sleep(0.1)
    return stats


def run() -> None:
    key = os.environ.get("PSI_YOUTUBE_API_KEY")
    if not key:
        print("  PSI_YOUTUBE_API_KEY not set — podcast and broadcast reach stays modelled from")
        print("  subscriber counts. Get a key at console.cloud.google.com (enable 'YouTube Data")
        print("  API v3', create an API key, restrict it to that API) and rerun this stage.")
        with db.db() as con:
            n = con.execute("SELECT COUNT(*) FROM outlets WHERE country=? AND youtube_channel_id IS NOT NULL "
                            "AND youtube_channel_id!=''", (db.COUNTRY,)).fetchone()[0]
        print(f"  {n} outlets have a channel id and are waiting on it.")
        return

    since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    with db.db() as con:
        outlets = db.rows(con, """SELECT outlet_id, name, type, youtube_channel_id
                                  FROM outlets WHERE country=? AND status!='defunct'
                                    AND youtube_channel_id IS NOT NULL AND youtube_channel_id!=''
                                  ORDER BY type, outlet_id""", (db.COUNTRY,))
    print(f"  {len(outlets)} outlets with a channel; window {WINDOW_DAYS} days")

    now = datetime.now(timezone.utc).isoformat()
    measured = skipped = 0
    for o in outlets:
        try:
            pl = uploads_playlist(o["youtube_channel_id"], key)
            if not pl:
                print(f"    {o['outlet_id']:24s} channel not found")
                skipped += 1
                continue
            vids = recent_videos(pl, key, since)
            if not vids:
                print(f"    {o['outlet_id']:24s} no uploads in window")
                skipped += 1
                continue
            stats = statistics([v["video_id"] for v in vids], key)
        except QuotaExceeded as exc:
            print(f"  quota exhausted at {o['outlet_id']}: {exc}")
            break
        except (RuntimeError, requests.RequestException) as exc:
            print(f"    {o['outlet_id']:24s} error: {type(exc).__name__} {exc}")
            skipped += 1
            continue

        views = [stats[v["video_id"]]["views"] for v in vids
                 if v["video_id"] in stats and stats[v["video_id"]]["views"] is not None]
        if not views:
            skipped += 1
            continue
        med = median(views)
        with db.db() as con:
            for v in vids:
                st = stats.get(v["video_id"])
                if not st or st["views"] is None:
                    continue
                db.upsert(con, "youtube_videos", {
                    "video_id": v["video_id"], "outlet_id": o["outlet_id"], "title": v["title"][:300],
                    "published_at": v["published"], "views": st["views"], "likes": st["likes"],
                    "comments": st["comments"], "duration": st["duration"], "collected_at": now,
                }, "video_id")
            # the outlet's measured per-episode audience replaces the modelled one
            db.upsert(con, "reach", {
                "outlet_id": o["outlet_id"], "country": db.COUNTRY,
                "reach_raw": med, "reach_unit": "median_episode_views_youtube",
                "reach_source": "YouTube Data API v3 (median views of episodes in window)",
                "reach_source_url": f"https://www.youtube.com/channel/{o['youtube_channel_id']}",
                "reach_source_quote": f"median of {len(views)} episodes published in the last {WINDOW_DAYS} days",
                "reach_date": now[:10], "source_tier": 5, "flag": "ok",
                "notes": (f"measured per-episode audience, replacing the modelled subscriber estimate; "
                          f"range {min(views):,.0f}-{max(views):,.0f} views"),
            }, "outlet_id")
        measured += 1
        print(f"    {o['outlet_id']:24s} {len(views):2d} episodes, median {med:>12,.0f} views")

    with db.db() as con:
        db.set_meta(con, "youtube_run", {"at": now, "measured": measured, "skipped": skipped,
                                         "window_days": WINDOW_DAYS})
        n_vids = con.execute("SELECT COUNT(*) FROM youtube_videos").fetchone()[0]
    print(f"  {measured} outlets now have a measured per-episode audience ({n_vids} videos); {skipped} skipped")
    print("  rerun `python run.py reach aggregate report` to fold it in")


if __name__ == "__main__":
    run()
