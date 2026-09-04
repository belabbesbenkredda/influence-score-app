"""Stage 4 — Sample recent content per outlet.

Per active outlet, pull 5-8 items from the last 14 days with full text
(>= 300 words). Paths, in order:

  1. rss_fulltext      RSS entries that carry the full article body
  2. page_fetch        RSS entry link fetched with a browser UA, text via trafilatura
  3. transcript_page   links harvested from the outlet's transcript/episode index page
  4. youtube_transcript YouTube auto-captions via youtube-transcript-api (skipped for
                       the rest of the run once YouTube blocks the IP)
  5. gdelt             GDELT DOC 2.0 article discovery for the outlet's domain, then page_fetch

Every miss is logged in fetch_log with a reason. Resume-safe: outlets that
already have >= MAX_PER_OUTLET items are skipped.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import feedparser
import requests
import trafilatura

from psi import db

WINDOW_DAYS = 14
MIN_WORDS = 300
# Outlets that block article fetching are sampled from their public RSS summaries instead of
# being dropped. A headline plus blurb runs 30-40 words, which is enough to place an item's
# topics but far too little to judge its argument: those items are marked
# content_basis='summary_only', and their D is not comparable with a full-text score.
# BB's call (decision D22): keep them in the ranking, flag the limitation everywhere.
SUMMARY_MIN_WORDS = 28
MIN_PER_OUTLET = 5
MAX_PER_OUTLET = 8
MAX_CANDIDATES = 24
WORKERS = 6
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"

NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(days=WINDOW_DAYS)

_STATE = {"yt_blocked": False, "gdelt_disabled": False}
_SKIP_PATH = re.compile(r"/(tag|tags|category|categories|author|authors|people|person|about|privacy|terms|contact|subscribe|newsletter|newsletters|search|photos|gallery|live|topics?|sitemap|login|account|page/\d+|feed|rss|wp-json|wp-content|store|careers|jobs|events|donate|shop)(/|$)", re.I)
_ASSET = re.compile(r"\.(css|js|png|jpe?g|gif|svg|ico|webp|webmanifest|json|xml|pdf|mp3|mp4|m4a)$", re.I)
# Sections that are not public-affairs content. Applied to every candidate URL.
_NONPOL = re.compile(r"(^|\.)(cooking|athletic|sports?|games|crosswords|wirecutter|recipes?|travel|realestate|style|fashion|food|dining|arts?|movies?|music|television|theater|books?|entertainment|lifestyle|weather|obituaries|horoscopes?|puzzles?|shopping|deals|coupons)\.|/(cooking|athletic|sports?|games|crosswords|wirecutter|recipes?|travel|real-?estate|style|fashion|food|dining|arts?|movies?|music|television|theater|books?|entertainment|lifestyle|weather|obituaries|horoscopes?|puzzles?|shopping|deals|coupons|celebrity|celebrities|gossip|royals?|autos?|cars)(/|$)", re.I)
_SUBINDEX = re.compile(r"/(date|shows?|episodes?|archive|transcripts?)/[^/]+/?$|/shows?/20\d\d/\d{1,2}/\d{1,2}/?$", re.I)
_ARTICLEY = re.compile(r"transcript|episode|full-show|segment|/show/|/watch/|/audio/|/story/|/news/|/politics/|/opinion/|/podcast/|/video/|/20\d\d/|/\d{4}/\d{1,2}/", re.I)


def nonpolitical(url: str) -> bool:
    p = urlparse(url)
    return bool(_NONPOL.search(p.netloc) or _NONPOL.search(p.path))


def item_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def clean_text(t: str) -> str:
    t = re.sub(r"\[\d{1,2}:\d{2}(:\d{2})?\]", " ", t)          # transcript timestamps
    t = re.sub(r"\r", "", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def words(t: str | None) -> int:
    return len(t.split()) if t else 0


def looks_like_listing(text: str) -> bool:
    """Index/series pages extract as many short lines (titles, dates, teasers)."""
    lines = [l for l in text.split("\n") if l.strip()]
    if len(lines) < 12:
        return False
    short = sum(1 for l in lines if len(l.split()) < 12)
    return short / len(lines) > 0.6


def title_from_url(url: str) -> str:
    p = urlparse(url)
    parts = [x for x in p.path.split("/") if x and x.lower() not in {"show", "shows", "date", "segment", "transcript", "transcripts", "video", "watch"}]
    return " / ".join(parts[-3:]) if parts else url


def strip_html(s: str) -> str:
    return trafilatura.extract(f"<html><body><article>{s}</article></body></html>", include_comments=False) or re.sub(r"<[^>]+>", " ", s)


def parse_date(entry) -> str | None:
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc).isoformat()
            except (TypeError, ValueError):
                pass
    return None


def within_window(iso: str | None) -> bool | None:
    """True/False when known, None when the date is unknown."""
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d >= CUTOFF
    except ValueError:
        return None


PLAIN_UA = {"User-Agent": "psi-influence-engine/0.2 (+https://publicspheres.org)"}


def fetch_html(url: str, timeout: int = 20) -> tuple[str | None, str]:
    try:
        r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
        if r.status_code in (403, 406):
            # some hosts (npr.org) reject browser UAs and accept a plain one
            r = requests.get(url, headers=PLAIN_UA, timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        return None, f"error:{type(exc).__name__}"
    if r.status_code != 200:
        return None, f"http_{r.status_code}"
    if "text/html" not in r.headers.get("content-type", "text/html"):
        return None, "not_html"
    return r.text, "ok"


def extract_article(html: str, url: str) -> dict:
    meta = trafilatura.bare_extraction(html, url=url, include_comments=False, with_metadata=True)
    if meta and hasattr(meta, "as_dict"):
        meta = meta.as_dict()
    meta = meta or {}
    text = meta.get("text") or ""
    if words(text) < MIN_WORDS:
        # transcripts often sit in containers the precision-first pass drops (e.g. democracynow.org)
        recall = trafilatura.extract(html, url=url, include_comments=False, favor_recall=True) or ""
        if words(recall) > words(text):
            text = recall
    date = meta.get("date")
    if date and len(date) == 10:
        date = f"{date}T00:00:00+00:00"
    return {"text": clean_text(text), "title": meta.get("title"), "date": date}


# ---------------------------------------------------------------- candidate sources

def rss_candidates(outlet: dict) -> list[dict]:
    if not outlet.get("rss_url"):
        return []
    try:
        feed = feedparser.parse(outlet["rss_url"], request_headers=UA)
        if not feed.entries and getattr(feed, "status", 200) in (403, 406):
            feed = feedparser.parse(outlet["rss_url"], request_headers=PLAIN_UA)
        if not feed.entries:
            return [{"error": f"rss_empty_status_{getattr(feed, 'status', 'na')}"}]
    except Exception as exc:  # feedparser is very forgiving; this is belt and braces
        return [{"error": f"rss_error:{type(exc).__name__}"}]
    out = []
    for e in feed.entries[:60]:
        link = e.get("link")
        if not link:
            continue
        published = parse_date(e)
        body = ""
        for c in e.get("content", []) or []:
            if c.get("value") and words(c["value"]) > words(body):
                body = c["value"]
        summary = e.get("summary") or ""
        if not body and words(summary) >= MIN_WORDS:
            body = summary
        out.append({"url": link, "title": e.get("title"), "published": published,
                    "fulltext": strip_html(body) if body else None,
                    "summary": strip_html(summary) if summary else None, "source": "rss"})
    return out


def harvest_links(index_url: str, html: str) -> tuple[list[str], list[str]]:
    """Return (article-like links, sub-index links) found on an index page, best first."""
    base_host = urlparse(index_url).netloc.split(":")[0].removeprefix("www.")
    scored, subindex, seen = [], [], set()
    for m in re.finditer(r'href=["\']([^"\'#?]+)', html):
        href = urljoin(index_url, m.group(1)).rstrip("/")
        if href in seen or href == index_url.rstrip("/"):
            continue
        seen.add(href)
        p = urlparse(href)
        host = p.netloc.split(":")[0].removeprefix("www.")
        if not host.endswith(base_host) or _ASSET.search(p.path):
            continue
        if _SUBINDEX.search(p.path):
            subindex.append(href)
            continue
        if _SKIP_PATH.search(p.path) or nonpolitical(href) or len(p.path) < 12 or re.search(r"/(podcast-series|series|program|programs|collections?)/", p.path):
            continue
        slug = p.path.rstrip("/").rsplit("/", 1)[-1]
        score = 0
        if _ARTICLEY.search(p.path):
            score += 2
        if len(slug) >= 20 or "-" in slug or "_" in slug:
            score += 1
        if p.path.count("/") >= 2:
            score += 1
        if score >= 2:
            scored.append((score, href))
    scored.sort(key=lambda x: -x[0])
    subindex.sort(key=lambda h: re.sub(r"\D", "", h)[-8:], reverse=True)   # newest date-like path first
    return [h for _, h in scored], subindex


def transcript_candidates(outlet: dict) -> list[dict]:
    idx = outlet.get("transcript_url")
    if not idx:
        return []
    html, status = fetch_html(idx)
    if not html:
        return [{"error": f"transcript_index_{status}"}]
    links, subindex = harvest_links(idx, html)
    if len(links) < 5 and subindex:
        # e.g. transcripts.cnn.com/date/YYYY-MM-DD or democracynow.org/shows/YYYY/M/D
        for sub in subindex[:3]:
            sub_html, _ = fetch_html(sub)
            if sub_html:
                more, _ = harvest_links(sub, sub_html)
                links.extend(l for l in more if l not in links)
            time.sleep(0.3)
    return [{"url": l, "title": None, "published": None, "fulltext": None, "source": "transcript_page"} for l in links[:MAX_CANDIDATES]]


def homepage_candidates(outlet: dict) -> list[dict]:
    """Outlets without a working feed: harvest current article links from the site's front page."""
    home = outlet.get("url")
    if not home:
        return []
    html, status = fetch_html(home)
    if not html:
        return [{"error": f"homepage_{status}"}]
    links, _ = harvest_links(home, html)
    return [{"url": l, "title": None, "published": None, "fulltext": None, "source": "homepage"} for l in links[:MAX_CANDIDATES]]


def youtube_candidates(outlet: dict) -> list[dict]:
    cid = outlet.get("youtube_channel_id")
    if not cid or _STATE["yt_blocked"]:
        return []
    feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}", request_headers=UA)
    out = []
    for e in feed.entries[:15]:
        vid = e.get("yt_videoid")
        if not vid:
            continue
        out.append({"url": f"https://www.youtube.com/watch?v={vid}", "title": e.get("title"), "published": parse_date(e),
                    "fulltext": None, "source": "youtube", "video_id": vid})
    return out


def fetch_youtube_transcript(video_id: str) -> tuple[str | None, str]:
    if _STATE["yt_blocked"]:
        return None, "youtube_ip_blocked"
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import IpBlocked, RequestBlocked
    except ImportError:
        return None, "youtube_transcript_api_missing"
    try:
        tr = YouTubeTranscriptApi().fetch(video_id, languages=["en", "en-US"])
        return clean_text(" ".join(s.text for s in tr)), "ok"
    except (IpBlocked, RequestBlocked):
        _STATE["yt_blocked"] = True
        return None, "youtube_ip_blocked"
    except Exception as exc:
        return None, f"youtube_{type(exc).__name__}"


def gdelt_candidates(outlet: dict) -> list[dict]:
    if _STATE["gdelt_disabled"] or not outlet.get("url"):
        return []
    domain = urlparse(outlet["url"]).netloc.removeprefix("www.")
    params = {"query": f"domain:{domain} sourcelang:english", "mode": "artlist", "format": "json",
              "maxrecords": 20, "timespan": f"{WINDOW_DAYS}d", "sort": "datedesc"}
    for attempt in range(2):
        try:
            r = requests.get(GDELT, params=params, headers=UA, timeout=30)
        except requests.RequestException as exc:
            return [{"error": f"gdelt_error:{type(exc).__name__}"}]
        if r.status_code == 429:
            if attempt == 0:
                time.sleep(30)
                continue
            _STATE["gdelt_disabled"] = True
            return [{"error": "gdelt_429"}]
        if r.status_code != 200:
            return [{"error": f"gdelt_http_{r.status_code}"}]
        try:
            arts = r.json().get("articles", [])
        except ValueError:
            return [{"error": "gdelt_bad_json"}]
        out = []
        for a in arts:
            seen = a.get("seendate")  # 20260901T120000Z
            published = None
            if seen and len(seen) >= 15:
                published = f"{seen[0:4]}-{seen[4:6]}-{seen[6:8]}T{seen[9:11]}:{seen[11:13]}:00+00:00"
            out.append({"url": a.get("url"), "title": a.get("title"), "published": published, "fulltext": None, "source": "gdelt"})
        return out
    return []


# ---------------------------------------------------------------- per-outlet driver

def sample_outlet(outlet: dict, have: int) -> dict:
    oid = outlet["outlet_id"]
    paywalled = (outlet.get("content_access") or "open") == "paywalled"
    items, log = [], []
    seen_urls = set()
    need = MAX_PER_OUTLET - have

    def log_miss(url, reason):
        log.append({"outlet_id": oid, "url": url, "status": "miss", "reason": reason})

    def accept(cand, text, method, title=None, published=None, basis="full_text"):
        text = clean_text(text)
        floor = SUMMARY_MIN_WORDS if basis == "summary_only" else MIN_WORDS
        if words(text) < floor:
            log_miss(cand["url"], f"short_{words(text)}w")
            return False
        if method in ("transcript_page", "homepage_fetch") and looks_like_listing(text):
            log_miss(cand["url"], "listing_page")
            return False
        if not title or len(title.split()) < 3 or title.strip().lower() in {"transcripts", "transcript", "(untitled)"}:
            title = title_from_url(cand["url"]) if not title or len(title.split()) < 3 else title
        items.append({"item_id": item_id(cand["url"]), "outlet_id": oid, "country": db.COUNTRY,
                      "title": title or cand.get("title") or "(untitled)", "url": cand["url"], "published_at": published,
                      "text": text, "word_count": words(text), "fetch_method": method,
                      "content_basis": basis, "fetched_at": NOW.isoformat()})
        log.append({"outlet_id": oid, "url": cand["url"], "status": "ok", "reason": method})
        return True

    def consume(cands, label):
        nonlocal need
        for c in cands:
            if need <= 0:
                return
            if "error" in c:
                log_miss(outlet.get("transcript_url") or outlet.get("rss_url") or outlet.get("url"), c["error"])
                continue
            url = c.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            if nonpolitical(url):
                log_miss(url, "nonpolitical_section")
                continue
            inwin = within_window(c.get("published"))
            if inwin is False:
                log_miss(url, "stale")
                continue
            if c["source"] == "youtube":
                text, status = fetch_youtube_transcript(c["video_id"])
                if text and accept(c, text, "youtube_transcript", published=c.get("published")):
                    need -= 1
                elif status != "ok":
                    log_miss(url, status)
                    if _STATE["yt_blocked"]:
                        return
                continue
            if c.get("fulltext") and words(c["fulltext"]) >= MIN_WORDS:
                if accept(c, c["fulltext"], "rss_fulltext", published=c.get("published")):
                    need -= 1
                continue
            html, status = fetch_html(url)
            if not html:
                # A paywalled outlet's article pages refuse us; its own RSS summary is what is public.
                if paywalled and c["source"] == "rss" and c.get("summary"):
                    title = c.get("title") or ""
                    body = (title + ". " + c["summary"]) if title else c["summary"]
                    if accept(c, body, "rss_summary", title=title, published=c.get("published"), basis="summary_only"):
                        need -= 1
                        continue
                log_miss(url, status)
                continue
            art = extract_article(html, url)
            published = c.get("published") or art.get("date")
            if within_window(published) is False:
                log_miss(url, "stale")
                continue
            method = "transcript_page" if c["source"] == "transcript_page" else ("homepage_fetch" if c["source"] == "homepage" else "page_fetch")
            title = c.get("title") if c["source"] == "rss" else (art.get("title") or c.get("title"))
            if accept(c, art.get("text") or "", method, title=title, published=published):
                need -= 1
            time.sleep(0.4)

    broadcast = outlet["type"] in {"tv", "cable", "radio", "podcast"}
    if broadcast:
        consume(transcript_candidates(outlet), "transcript")
    if need > 0:
        consume(rss_candidates(outlet), "rss")
    if need > 0 and broadcast:
        consume(youtube_candidates(outlet), "youtube")
    if need > 0 and (have + len(items)) < MIN_PER_OUTLET:
        consume(homepage_candidates(outlet), "homepage")
    if need > 0 and (have + len(items)) < MIN_PER_OUTLET:
        consume(gdelt_candidates(outlet), "gdelt")
    return {"outlet_id": oid, "items": items, "log": log}


def run() -> None:
    with db.db() as con:
        outlets = db.rows(con, "SELECT * FROM outlets WHERE country=? AND status!='defunct' ORDER BY type, outlet_id", (db.COUNTRY,))
        counts = {r["outlet_id"]: r["n"] for r in db.rows(con, "SELECT outlet_id, COUNT(*) n FROM items GROUP BY outlet_id")}
    todo = [o for o in outlets if counts.get(o["outlet_id"], 0) < MAX_PER_OUTLET]
    print(f"  {len(outlets)} active outlets; {len(todo)} need sampling (window {WINDOW_DAYS}d, min {MIN_WORDS} words)")

    total_new, total_miss = 0, 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(sample_outlet, o, counts.get(o["outlet_id"], 0)): o for o in todo}
        for fut in as_completed(futs):
            o = futs[fut]
            try:
                res = fut.result()
            except Exception as exc:  # never let one outlet kill the run
                res = {"outlet_id": o["outlet_id"], "items": [], "log": [{"outlet_id": o["outlet_id"], "url": o.get("url"), "status": "miss", "reason": f"crash:{type(exc).__name__}:{exc}"[:200]}]}
            with db.db() as con:
                for it in res["items"]:
                    db.upsert(con, "items", it, "item_id")
                for lg in res["log"]:
                    con.execute("INSERT INTO fetch_log(outlet_id,url,status,reason,ts) VALUES(?,?,?,?,?)",
                                (lg["outlet_id"], lg["url"], lg["status"], lg["reason"], NOW.isoformat()))
            n_ok = len(res["items"])
            n_miss = sum(1 for l in res["log"] if l["status"] == "miss")
            total_new += n_ok
            total_miss += n_miss
            methods = sorted({i["fetch_method"] for i in res["items"]})
            print(f"    {o['outlet_id']:28s} +{n_ok} items  {n_miss} misses  {','.join(methods)}")

    with db.db() as con:
        n_items = con.execute("SELECT COUNT(*) FROM items WHERE country=?", (db.COUNTRY,)).fetchone()[0]
        n_out = con.execute("SELECT COUNT(DISTINCT outlet_id) FROM items WHERE country=?", (db.COUNTRY,)).fetchone()[0]
        by_method = db.rows(con, "SELECT fetch_method, COUNT(*) n FROM items WHERE country=? GROUP BY fetch_method ORDER BY n DESC", (db.COUNTRY,))
        by_basis = db.rows(con, "SELECT content_basis, COUNT(*) n FROM items WHERE country=? GROUP BY content_basis", (db.COUNTRY,))
        reasons = db.rows(con, "SELECT reason, COUNT(*) n FROM fetch_log WHERE status='miss' GROUP BY reason ORDER BY n DESC LIMIT 12")
        db.set_meta(con, "sample_run", {"at": NOW.isoformat(), "new_items": total_new, "misses": total_miss,
                                        "yt_blocked": _STATE["yt_blocked"], "gdelt_disabled": _STATE["gdelt_disabled"]})
    print(f"  items in DB: {n_items} across {n_out} outlets; this run +{total_new}, misses {total_miss}")
    print("  by method:", {r["fetch_method"]: r["n"] for r in by_method})
    print("  by content basis:", {r["content_basis"]: r["n"] for r in by_basis})
    print("  top miss reasons:", {r["reason"]: r["n"] for r in reasons})
    if _STATE["yt_blocked"]:
        print("  NOTE: YouTube blocked transcript requests from this IP; TV/podcast items came from transcript pages/articles instead.")


if __name__ == "__main__":
    run()
