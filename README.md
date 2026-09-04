# PSI Influence Engine v0.4 — United States

A ranked map of the opinion-forming core of the American public sphere,
built for the Public Sphere Index (PSI, [publicspheres.org](https://publicspheres.org)).

Every outlet gets an influence score

    I = R × S × D

- **R — Reach.** How many people the outlet reaches, from third-party
  audience data (Nielsen, Press Gazette/Similarweb, Comscore, Talkers,
  public YouTube and Substack counts). Normalised to 0–1.
- **S — Salience.** How much the topics it covers matter to the public,
  from Gallup's "Most Important Problem" survey. Objective, not judged by
  an AI.
- **D — Discursiveness.** How much the outlet argues rather than asserts:
  Logos (evidence and reasoning) + Ethos (credibility and fairness) +
  Pathos (emotional intensity), each 0–10, scored by Claude from the text
  of recent items. Normalised to 0–1.

This is v0.4. **Individual items are the primary object** — influence is
a property of content, not of a masthead — and outlets appear as a rollup
of a representative item. Scores are published as PSI points (I × 1,000),
the expected influence per thousand American adults. The
seven-determinant health matrix is not built yet; `docs/next.md` says how
it would attach.

## What is in the box

| Path | What it is |
|---|---|
| `out/report.html` | The report. One self-contained page; open it in any browser, works offline. Also at `docs/index.html` for GitHub Pages. |
| `out/ranked_items.csv` / `.json` | The primary ranking: every item with R, S, D, I and provenance. |
| `out/ranked_outlets.csv` / `.json` | The outlet rollup — the influence of one representative item, not a period total. |
| `out/items_scored.csv` | Every sampled item with topic, L/E/P scores and the model's justification. |
| `out/handcheck_sample.md` | 20 random scored items to check by hand from a phone. |
| `out/psi.sqlite` | The database behind all of the above. |
| `data/outlets_seed.csv` | The outlet universe. Edit this to add or remove outlets. |
| `data/reach_seed.csv` | One audience figure per outlet with source URL, quote, date and fact-check verdict. |
| `data/reach_sources.md` | How reach is sourced and normalised. `data/reach_table.md` is the auto-generated per-outlet table. |
| `data/type_weights.csv` | Pew platform shares used to compare across outlet types. |
| `data/mip_table.csv` / `data/mip_raw_gallup.csv` | Gallup MIP salience, collapsed and raw. |
| `psi/prompts/score_v2.md` | The scoring rubric given to the model. Versioned; `score_v1` is kept for comparison. |
| `psi/audience.py` | Converts each medium's currency into people per item. Every constant here is a stated assumption. |
| `psi/signals.py` | Per-item reach signals. Off until a provider is configured. |
| `RUNLOG.md` | What was done, decided and left uncertain, stage by stage. |

## How to rerun everything

You need Python 3.10+ and an Anthropic API key.

```bash
pip install -r requirements.txt
export PSI_API_KEY=sk-ant-...        # only needed for the scoring stage
python run.py all
```

`run.py all` runs the seven stages in order:

1. `outlets` — loads `data/outlets_seed.csv` into the database.
2. `reach` — loads `data/reach_seed.csv` and `data/type_weights.csv`, applies fact-check verdicts, normalises.
3. `salience` — fetches the latest Gallup MIP table (falls back to the cached copy in `data/raw/`).
4. `sample` — pulls up to 8 recent items (last 14 days, 300+ words) per outlet. Outlets that block fetching are sampled from their public RSS summaries and marked `summary_only`.
5. `signals` — collects per-item audience signals from whichever provider is configured (see below). Without one, every item inherits its outlet's average reach.
6. `score` — one Claude call per item. Skips items already scored, so reruns only pay for new items.
7. `aggregate` — computes R, S, D and I per item, ranks them, rolls up to outlets; writes the CSV/JSON exports.
8. `report` — writes `out/report.html`, `docs/index.html` and `out/handcheck_sample.md`.

Run a single stage with `python run.py <stage>`; `python run.py status`
prints row counts. Useful knobs (environment variables):

| Variable | Meaning |
|---|---|
| `PSI_API_KEY` | Anthropic API key for scoring. |
| `PSI_SCORE_MODEL` | Scoring model, default `claude-sonnet-5`. |
| `PSI_SCORE_EFFORT` | Model effort, default `medium`. |
| `PSI_SCORE_LIMIT` | Score at most N items this run (smoke tests). |
| `PSI_MAX_SPEND` | Stop scoring past this many dollars (default 20). |
| `PSI_DB_PATH` | Use another SQLite file. |
| `PSI_COUNTRY` | Country code stored on every row, default `US`. |
| `PSI_PROMPT_VERSION` | Scoring rubric, default `score_v2`. |
| `PSI_YOUTUBE_API_KEY` | YouTube Data API v3 key. Turns on per-item reach for every channel-based outlet. Free tier is ample. |
| `PSI_ANALYTICS_URL` / `PSI_ANALYTICS_KEY` | A per-URL pageview endpoint (Chartbeat, Parse.ly, a publisher API) for per-article reach. |
| `PSI_SOCIAL_URL` / `PSI_SOCIAL_KEY` | A social-listening endpoint returning engagement per URL. |

Scoring cost is roughly one cent per item; a full run of ~500 items is a
few dollars.

## How to add an outlet

1. Add a row to `data/outlets_seed.csv`: a short `outlet_id`
   (lowercase, underscores), `name`, `type` (`tv`, `cable`,
   `print_digital`, `radio`, `podcast`, `newsletter`), `url`, and where
   possible `rss_url`, `youtube_channel_id`, and a `transcript_url` (a page
   listing recent transcripts or episodes).
2. Add a row to `data/reach_seed.csv` with a sourced audience figure, the
   URL you got it from, a verbatim quote containing the number, the date
   it describes, and `flag` (`ok`, `self_reported`) — or leave the figure
   blank and set `flag` to `unsourced`. Never type a number from memory.
3. `python run.py all`. Only the new outlet's items are fetched and scored.

## Where the data came from

- **Outlets** were assembled from the brief's list plus comparable
  national outlets, with feeds and transcript pages verified by fetching.
- **Reach** figures come from the sources listed per outlet in
  `data/reach_table.md`, each with a link and a verbatim quote, then
  re-checked by a pass that fetches every URL again and looks for the
  quote. By type: Semrush monthly visits for websites, Nielsen figures
  reported in the trade press for TV and cable, public YouTube
  subscriber counts for podcasts, publications' own subscriber counts
  for newsletters, and Talkers estimates for radio. See
  `data/reach_sources.md` for why each was used and how they are
  normalised.
- **Salience** is Gallup's Most Important Problem table
  (news.gallup.com/poll/1675), latest monthly column.
- **Content** was fetched from each outlet's RSS feed, website or
  transcript pages, within the last 14 days.
- **Scores** were produced by `claude-sonnet-5` with the rubric in
  `psi/prompts/score_v1.md`, one call per item, strict JSON output.

## Known limitations

- **No fabricated figures, so there are gaps.** 16 of 124 outlets have no
  sourced reach figure; they appear in the tables with R = null and no
  rank. Flags (`unsourced`, `self_reported`, `secondary`, `stale`,
  `unverified`) are shown everywhere.
- **Radio reach is the weakest column.** No public per-host audience
  table exists for American talk radio, so those rows use Talkers'
  self-described non-scientific estimates, flagged `secondary`.
- **Cross-type reach is a convention.** Viewers, visits, listeners and
  subscribers are not the same thing. Each type is scaled to its leader
  and then by Pew's platform share; treat cross-type comparisons as
  indicative.
- **Reach and scores cover different sets of outlets.** 108 of 124 outlets
  have a sourced reach figure and 84 have sampled items, but only 74 have
  both, so only 74 are ranked. The rest appear in the tables unranked.
- **Some big sites block automated fetching** (New York Times, Wall
  Street Journal, Washington Post, Bloomberg, Reuters, USA Today, The
  Hill). They have reach figures but no scored items in this run. Running
  the `sample` stage from a normal home connection fills most of these.
- **YouTube captions were blocked from the cloud runner**, so TV, cable,
  radio and podcast outlets were sampled from their own published
  transcripts and articles instead of broadcast captions. 20 of the 30
  podcasts publish only show notes and so have no scored items.
- **Discursiveness is model-judged.** The rubric is public and versioned,
  the model's justification is stored per item, and
  `out/handcheck_sample.md` exists so a human can audit it.
- **Salience uses the topic's MIP share**, so an outlet that covers many
  low-salience topics scores low on S by design, not by accident.
- The legacy `streamlit_app.py` at the repo root is an earlier manual
  scoring demo and is not part of this pipeline.
