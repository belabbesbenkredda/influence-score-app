# What comes next (not built in v0.2)

## The seven-determinant health matrix

The PSI health matrix (Truth, Equal Opportunity, Common Concern, Shared
Arenas, Civility, Pluralism, Efficacy) is out of scope for v0.2 and nothing in
this repo computes it. Here is how it would attach without rewriting the
pipeline.

1. **Item level.** Add a second scoring prompt (`psi/prompts/health_v1.md`)
   and a `health_scores` table keyed by `item_id` with one 0–10 column per
   determinant plus `raw_json`, `model`, `prompt_version`. `score.py` already
   isolates the API call and resume logic, so a `--rubric health` flag can
   reuse it.
2. **Outlet level.** `aggregate.py` averages item scores per outlet; the same
   `mean over items` step gives a 7-vector per outlet. Weight it by each
   outlet's influence `I` to get a reach-weighted public-sphere profile.
3. **Public-sphere level.** Sum over outlets: `H_k = Σ_o I_o · h_{o,k} / Σ_o I_o`
   for each determinant `k`. That is one row per country per run.
4. **Determinants that are not text-scorable.** Equal Opportunity and
   Pluralism need audience or ownership data, not content; attach them at the
   outlet level from external tables (ownership concentration, audience
   demographics) with the same `source`/`flag` provenance rules as `reach`.
5. **Report.** `report.py` renders one panel per section; a radar or small
   multiples panel for the 7-vector slots in after the topic-salience panel.

## Other loose ends

- YouTube transcripts were blocked from the cloud runner in this run, and 20
  of the 30 podcasts have no other public transcript, so they carry a reach
  figure but no score. Running `python run.py sample` from a residential IP
  (or with cookies) fills that gap and would add roughly 150 items.
- Ten large publishers (New York Times, Wall Street Journal, Washington Post,
  Bloomberg, Reuters, USA Today, The Hill and others) block automated article
  fetching, so they are sourced for reach but unscored. A licensed feed, or a
  browser-based fetch, closes that hole.
- Canada: set `PSI_COUNTRY=CA`, add a `data/outlets_seed_CA.csv` and a
  Canadian salience table (Environics/Abacus "most important issue"), and the
  schema already keeps countries apart.
- Item-level reach (per-story audience) would let `I` be computed per item
  rather than per outlet; the formula is unchanged.
