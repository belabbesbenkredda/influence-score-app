# PSI Influence Engine v0.2 — United States

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

This is v0.2: outlet-level reach, item-level salience and discursiveness
averaged up to the outlet. The seven-determinant health matrix is not
built yet; `docs/next.md` says how it would attach.

## What is in the box

| Path | What it is |
|---|---|
| `out/report.html` | The report. One self-contained page; open it in any browser, works offline. Also at `docs/index.html` for GitHub Pages. |
| `out/ranked_outlets.csv` / `.json` | The ranking with R, S, D, I, confidence and reach provenance per outlet. |
| `out/items_scored.csv` | Every sampled item with topic, L/E/P scores and the model's justification. |
| `out/handcheck_sample.md` | 20 random scored items to check by hand from a phone. |
| `out/psi.sqlite` | The database behind all of the above. |
| `data/outlets_seed.csv` | The outlet universe. Edit this to add or remove outlets. |
| `data/reach_seed.csv` | One audience figure per outlet with source URL, quote, date and fact-check verdict. |
| `data/reach_sources.md` | How reach is sourced and normalised. `data/reach_table.md` is the auto-generated per-outlet table. |
| `data/type_weights.csv` | Pew platform shares used to compare across outlet types. |
| `data/mip_table.csv` / `data/mip_raw_gallup.csv` | Gallup MIP salience, collapsed and raw. |
| `psi/prompts/score_v1.md` | The scoring rubric given to the model. Versioned. |
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
4. `sample` — pulls up to 8 recent items (last 14 days, 300+ words) per outlet.
5. `score` — one Claude call per item. Skips items already scored, so reruns only pay for new items.
6. `aggregate` — computes R, S, D, I, rank and confidence; writes the CSV/JSON exports.
7. `report` — writes `out/report.html`, `docs/index.html` and `out/handcheck_sample.md`.

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
  re-checked by a second pass that fetched every URL. See
  `data/reach_sources.md` for the tiering and normalisation.
- **Salience** is Gallup's Most Important Problem table
  (news.gallup.com/poll/1675), latest monthly column.
- **Content** was fetched from each outlet's RSS feed, website or
  transcript pages, within the last 14 days.
- **Scores** were produced by `claude-sonnet-5` with the rubric in
  `psi/prompts/score_v1.md`, one call per item, strict JSON output.

## Known limitations

- **No fabricated figures, so there are gaps.** Outlets without a sourced
  reach figure appear in the tables with R = null and no rank. Flags
  (`unsourced`, `self_reported`, `unverified`) are shown everywhere.
- **Cross-type reach is a convention.** Viewers, visits, listeners and
  subscribers are not the same thing. Each type is scaled to its leader
  and then by Pew's platform share; treat cross-type comparisons as
  indicative.
- **Some big sites block automated fetching** (New York Times, Wall
  Street Journal, Reuters, Bloomberg, Washington Post). Their items are
  thin or missing in this run; see `RUNLOG.md`. Running the `sample` stage
  from a normal home connection fills most of these.
- **YouTube captions were blocked from the cloud runner**, so TV, cable,
  radio and podcast outlets were sampled from their own published
  transcripts and articles instead of broadcast captions. Podcasts that
  publish only show notes have few or no items.
- **Discursiveness is model-judged.** The rubric is public and versioned,
  the model's justification is stored per item, and
  `out/handcheck_sample.md` exists so a human can audit it.
- **Salience uses the topic's MIP share**, so an outlet that covers many
  low-salience topics scores low on S by design, not by accident.
- The legacy `streamlit_app.py` at the repo root is an earlier manual
  scoring demo and is not part of this pipeline.
