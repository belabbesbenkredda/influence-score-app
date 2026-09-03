# RUNLOG — PSI Influence Engine v0.2 (US)

Read newest at the bottom. Short lines for phone reading.

## 2026-09-03 — Session start

**What I found**
- Repo had no Canada pipeline. Only an early Streamlit demo
  (`streamlit_app.py`) with a hand-entered R/S/D form.
- Building the US pipeline fresh. Schema carries a `country`
  column so Canada can be added later without a rewrite.
- `PSI_API_KEY` is set and works with `claude-sonnet-5`.

**Environment probes (what works from the cloud runner)**
- Anthropic API: OK.
- RSS feeds: OK (NYT, NPR, Politico, Axios, The Hill, WSJ, WaPo...).
- Gallup MIP page: OK, fetched, cached in `data/raw/`.
- YouTube channel feeds: OK. YouTube transcripts: BLOCKED
  (IP blocked / "sign in to confirm you're not a bot").
  Tried youtube-transcript-api, yt-dlp, Piped, Invidious. All fail.
- GDELT DOC API: 429 rate-limited on first call. Fallback only.
- Direct article fetch: blocked at Politico (403), WSJ (401),
  Reuters (401), Bloomberg (403), WaPo (timeout).
  Politico and Axios RSS carry full text, so RSS full text is the
  first path.
- Transcript pages work: Fox News, CNN, MSNBC, PBS NewsHour,
  NPR, Crooked (Pod Save America), NYT The Daily.

**Decisions**
- Scoring model: `claude-sonnet-5` as briefed. It rejects
  `temperature`, so the call omits it (the API returns 400
  otherwise). Structured JSON output enforces the schema.
- TV / cable / radio / podcast sampling uses the outlet's own
  published transcripts and articles instead of YouTube
  auto-captions. `fetch_method` records which. Logged as a gap.
- Cross-type reach normalisation: within-type max scaling, then a
  platform weight from Pew's news-platform fact sheet. See
  `data/reach_sources.md` once written.

**Spend so far**: ~$0.00 (one 10-token API test).

**Next**: scaffold committed; run the outlet + reach research
workflow (Stages 1-2).
