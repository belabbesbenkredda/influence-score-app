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

**Gallup note (2026-09-03, later)**
- Gallup posted the August 2026 MIP column during this session.
  Its CDN served the July page and the August page on alternate
  fetches. Fix: every parseable copy is cached under its survey
  month (`data/raw/gallup_mip_1675_2026-07.html`, `..._2026-08.html`)
  and the newest month wins. This run uses **August 2026**:
  government/leadership 25%, economy 23%, inflation/cost of
  living 19%, foreign policy/wars 12%, immigration 10%.
- Header formats differ between versions ("Jul 2026" vs
  "26-Aug"); the parser accepts both.

**Sampler additions after the outlet research came back**
- NPR feeds reject browser user agents: added a plain-UA retry.
- AP, Reuters, Newsweek, USA Today have no working RSS: added a
  front-page link harvest fallback (works for AP; USA Today's
  pages are JavaScript-only, so it stays thin).
- 60 Minutes dropped from the universe: it is a show, CBS News
  already covers it.

## 2026-09-03 — Stages 1-4 done, scoring started

**Checkpoint A**
- Outlets in DB: **124** (target ~110).
- Outlets with a sourced reach figure: **108** (target 60).
- Items fetched with usable text: **576** across 84 outlets
  (target 300). Misses logged: 2,886 rows in `fetch_log`.

**Outlet universe (Stage 1)**
- Built by seven parallel research agents (one per outlet type),
  then a completeness critic, then a gap filler. Every RSS feed
  and transcript index was verified by fetching it.
- The critic found 139 rows and said the list needed trimming,
  not additions. Dropped 20: brand duplicates (60 Minutes,
  Bulwark newsletter, Meidas+, Honestly), non-US (Economist, FT,
  Rest Is Politics US), aggregators (MSN, Yahoo News, 1440),
  entertainment (Shawn Ryan, Theo Von, PBD, Pivot), C-SPAN
  (raw feed, not Nielsen-rated), and six small outlets.
  Reasons are in `psi/tools/ingest_research.py`.
- Result: 124 outlets — 7 tv, 8 cable, 52 print/digital,
  12 radio, 30 podcast, 15 newsletter.

**Reach (Stage 2) — where each figure comes from**
- print_digital 43/52: Semrush monthly visits per domain,
  July 2026 (June for smaller sites; the month is recorded per
  row). 8 outlets have no Semrush page at all (Semafor, Puck,
  National Review, New Republic, Intercept, Dispatch, Bulwark,
  American Conservative) and stay unsourced.
- cable 7/8: Nielsen via MediaPost (July 2026 total day) and the
  Fox Business Q2 press release. OAN is not Nielsen-rated.
- tv 6/7: Nielsen via Deadline (Q2 2026 evening newscasts) and
  The Desk (Univision/Telemundo, week to 12 July). PBS NewsHour's
  only public Nielsen average is 2022 (Pew) — kept, flagged
  `stale`.
- podcast 29/30: YouTube subscriber counts read off the channel
  pages. Bannon's War Room has no channel (banned 2021).
- newsletter 14/15: subscriber counts printed on the publication's
  own page, flagged `self_reported`. Punchbowl blocks fetching.
- radio 9/12: no public per-host Nielsen table exists (Nielsen
  does not compile nationwide by host; Talkers' own audience page
  is now 404). Used Talkers estimates reproduced in Wikipedia's
  most-listened-to table, flagged `secondary` and undated.
  Democracy Now!, 1A and Erick Erickson are not in it.
- Cross-type weights: Pew News Platform Fact Sheet, Aug 2025.
  TV 64, digital 65, radio 44, podcast 32, newsletter 30 percent
  of US adults. Cable borrows television (flagged `proxy`).

**Verification**: every figure is re-fetched by
`psi/tools/verify_reach.py`, which looks for the recorded quote
(or its number plus a distinctive word) in the live page.
`refuted` rows get their figure nulled by `run.py reach`.
No model is involved; it is a plain text search.

**Sampling (Stage 4) — what the runner could not get**
- Blocked entirely: YouTube captions (bot wall), so TV, cable,
  radio and podcast items come from transcript pages and
  articles. WaPo timed out on every attempt; NYT article pages
  403 on every attempt.
- 639 of the misses are HTTP 403, 902 are items older than the
  14-day window.
- Working paths: RSS full text 301 items, page fetch 155,
  transcript pages 81, homepage harvest 35, YouTube 4.

**Spend so far**: ~$0.22 (smoke tests). Scoring 576 items now,
estimated $8-12.

## 2026-09-03 — Checkpoint B: first full run complete

`python run.py all` ran all seven stages end to end and reproduced
everything. Scoring is resume-safe: the rerun added 48 new items,
scored only those 5 that met the word floor, and left the other 576
alone.

**Top 10 by I = R × S × D**

| # | Outlet | I |
|---|---|---|
| 1 | ABC News (tv) | 0.0743 |
| 2 | Fox News Channel (cable) | 0.0642 |
| 3 | NBC News (tv) | 0.0393 |
| 4 | Marketplace (radio) | 0.0336 |
| 5 | The Mark Levin Show (radio) | 0.0299 |
| 6 | MS NOW (cable) | 0.0297 |
| 7 | Letters from an American (newsletter) | 0.0285 |
| 8 | Clay Travis & Buck Sexton (radio) | 0.0268 |
| 9 | CNN (cable) | 0.0263 |
| 10 | CBS News (tv) | 0.0252 |

**Counts**
- 124 outlets, 108 with sourced reach, 581 items, 581 scored,
  75 ranked (60 high confidence, 7 medium, 8 low).
- Reach flags: ok 63, scope_global 20, unsourced 16,
  self_reported 15, secondary 9, stale 1.
- Fact-check: all 108 figures re-fetched and matched. 0 refuted.

**Estimated total spend: $3.90** (581 items, claude-sonnet-5,
about $0.0067 each). Guardrail was $25.

**What looked wrong, and what I did**

1. *Semrush was giving worldwide traffic.* First pass ranked BBC
   News above every US outlet but the NYT on 404m visits. Semrush
   publishes a US-only split, so the collector now reads that
   (BBC US = 100m). 20 smaller sites have no US split published;
   they keep the worldwide figure and are flagged `scope_global`.
   Putting them in their own group would have normalised Newsweek
   to 1.0, level with the NYT.
2. *Radio is the weakest column.* No public per-host audience table
   exists any more. The 9 radio figures are Talkers estimates
   reproduced by Wikipedia, undated, flagged `secondary`. Marketplace
   at #4 and Levin at #5 rest on those numbers; treat that part of
   the ranking as indicative.
3. *Only 75 of 124 outlets are ranked.* 16 have no reach figure and
   34 have reach but no scored items, because their content could not
   be fetched: 20 podcasts publish only show notes (YouTube captions
   are blocked from this IP) and 10 large publishers (NYT, WSJ, WaPo,
   Bloomberg, Reuters, USA Today, The Hill) block automated fetching.
   Those outlets appear unranked rather than being scored on thin data.
4. *ABC News tops the list* on the strength of World News Tonight's
   8.2m viewers, the largest audience in any type here. That is the
   formula working as specified; it does mean R dominates I when one
   type's leader is far ahead.
5. *Gallup served two versions of its page* during the session (July
   and August columns on alternate fetches). Every parseable copy is
   now cached by survey month and the newest wins. This run uses
   August 2026.

**Scoring sanity**: mean Logos 5.0, Ethos 5.2, Pathos 5.1, D 15.3/30.
Highest D over 6+ items: The New Yorker and ProPublica (0.696).
Lowest: Noticias Telemundo (0.283) and Louder with Crowder (0.333).
Nine items were truncated at 6,000 words and are flagged in the DB.
`out/handcheck_sample.md` has 20 items for BB to check by hand.

**Report**: `out/report.html` (752 KB) verified to open with the
network fully blocked — no requests attempted, no console errors,
fonts embedded as data URIs, sorting and filtering work. Copied to
`docs/index.html`.

**Definition of done**
- [x] >= 110 outlets (124), >= 60 sourced reach (108), 0 fabricated
- [x] MIP table with Gallup provenance and survey date (2026-08)
- [x] >= 300 scored items (581); ranked CSV/JSON; offline report
- [x] handcheck sample, RUNLOG, README for a non-developer
- [x] `python run.py all` reproduces everything

## 2026-09-04 — v0.3: rubric v2, item-first, absolute reach

BB reviewed all 22 methodological decisions in the review console.
10 approve, 11 change, 1 reject (D14, the sampling window),
1 left open (D06, where he asked which normalisation I preferred).

**Rubric v2 (`psi/prompts/score_v2.md`)**
- Ethos rewritten. It now measures the speaker's standing with
  their own audience, and the rubric explicitly forbids lowering
  it for partisanship, one-sidedness or absent counterarguments.
  BB's paper: the framework must catch both Goebbels and Socrates.
- Topics are now proportional shares, not one label per item.

**Effect of the rescore (581 items, both rubrics, $4.26 total)**

| | v1 | v2 | change |
|---|---|---|---|
| logos | 5.02 | 5.12 | +0.10 |
| ethos | 5.17 | 5.39 | +0.22 |
| pathos | 5.10 | 4.54 | -0.56 |

Ethos moved exactly where the error predicted:
podcast +2.42, radio +1.47, newsletter +0.48,
cable -0.07, print_digital -0.25, tv -0.35.
Mark Levin went 2 -> 8. The old rubric was scoring
institutional manner as credibility and penalising
audience authority.

Economy coverage rose 7.7% -> 9.1% of topic mass.
Smaller than the labelling test suggested, because
government/leadership genuinely dominates these days
and economy is a minority share inside those items.

**Reach is now absolute (`psi/audience.py`)**
- Leader-normalisation and the Pew platform weights are gone.
  R = estimated US adults reaching one item / 262m US adults.
- Each medium's currency is converted by a named constant:
  radio weekly cume / 5 episodes; podcast subscribers x 10%
  episode rate x audio multiple; newsletter subscribers x 40%
  open rate; digital monthly visits / 800 items a month.
- Every constant is an assumption, gathered in one module and
  printed in the report. The digital divisor is the weakest.

**Item-first aggregation**
- 581 items, 423 with R, S and D. Outlets are now a rollup:
  the mean influence of one representative item, never a period
  total, because sampling is capped per outlet.

**KNOWN LIMITATION, visible in the output**
Every item from one outlet still carries the same R, so the
item ranking is currently the outlet ranking with S x D as a
tiebreak — the top seven items are all ABC News at R = 0.03130.
The audience model supplies the LEVEL; the per-item SIGNAL that
supplies the DISTRIBUTION is not collected yet. That is the next
build: YouTube per-video views, engagement per URL.

**Still open from the review**: D01 (new entrants), D08 (unsourced
outlets), D15 (items per outlet), D22 (paywalled papers). The
one-month evenly-sampled window and audio transcription are also
still to do.
