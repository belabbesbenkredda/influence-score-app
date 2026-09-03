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

## 2026-09-03 — Stages built, research workflow running

**Done**
- All seven stage modules written and committed.
- Salience (Stage 3) runs: Gallup MIP, July 2026 column,
  49 raw categories -> 18 topics. Top: government/leadership 28%,
  economy 18%, inflation/cost of living 13%, immigration 12%.
- Smoke test of sampling + scoring on 7 outlets in a scratch DB:
  scoring works, ~$0.011 per item with prompt caching.
  Structured JSON output rejects min/max on integers; switched
  to an enum of 0-10.

**Research workflow (Stages 1-2)**
- 7 outlet-type agents -> completeness critic -> reach agents ->
  fact-check agents (re-fetch every source URL) -> Pew weights.
- The runner has 4 CPUs, so the workflow runs only 2 agents at a
  time. Expect it to take a while. Nothing else blocks on it
  except loading the seed CSVs.

**Sampling findings (what the cloud runner can and cannot get)**
- Works: PBS NewsHour full transcripts, CNN transcripts (via
  date pages), Democracy Now transcripts (needs recall-mode
  extraction), Fox/Politico/Axios articles via RSS full text.
- Blocked: NYT article pages (403), WSJ (401), Reuters (401),
  Bloomberg (403), WaPo (timeout), YouTube captions (bot wall).
- Podcast episode pages (Crooked, audioboom) are show notes,
  not transcripts: ~150-250 words, under the 300-word floor.
  Podcasts will be thin until YouTube captions are reachable.
- Decision: broadcast-type outlets try transcript pages first,
  then RSS, then YouTube, then GDELT. Non-political sections
  (sports, cooking, arts...) are filtered out of every path.

**Spend so far**: ~$0.07 (6 smoke-test items).
