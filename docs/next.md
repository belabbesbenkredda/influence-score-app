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

## Scoring paywalled items from source metadata (BB, 4 Sep)

Summary-only items currently give the model 30–40 words and little else. BB's
point is that a great deal of discursiveness is carried by the source rather
than the prose, and all of it is available in the feed:

- **Author.** RSS carries `dc:creator`. Who is speaking is not a hint about
  ethos, it *is* ethos under the corrected rubric — a named columnist with a
  standing readership scores differently from an unsigned wire report.
- **Format.** The URL section says most of it: `/opinion/`, `/editorial/`,
  `/analysis/` is argument by construction and sits high on logos; a straight
  news headline is narrow reporting and sits low. This is a prior, not a
  measurement, and should be passed as context rather than as a score.
- **Role priors.** An author or programme with a known role in the public
  sphere occupies a narrower band on ethos and logos than an unknown one.
  Priors should widen, never replace, what the text supports.

Implementation: capture `author` and `section` on `items` during sampling, pass
both to the scorer for `summary_only` items, and record in the item's raw JSON
that the score leaned on metadata. Keep them out of full-text scoring so the two
populations stay separable and the effect of the priors stays measurable.

The caveat BB also made: none of this substitutes for full text once the seven
determinants are built. Truth, civility and pluralism cannot be assessed from a
headline.

## Other loose ends

- YouTube transcripts were blocked from the cloud runner in this run, and 20
  of the 30 podcasts have no other public transcript, so they carry a reach
  figure but no score. Running `python run.py sample` from a residential IP
  (or with cookies) fills that gap and would add roughly 150 items.
- Ten large publishers block automated article fetching. As of v0.4 they enter
  the index through their public RSS summaries, flagged `summary_only`. A
  licensed feed or a browser-based fetch is still what closes the hole properly.
- The Wall Street Journal's public feed is roughly 19 months stale, so it has no
  usable current items at all by this route. It needs a licensed feed or nothing:
  a stale item in a fortnightly index is worse than an absent one.
- Canada: set `PSI_COUNTRY=CA`, add a `data/outlets_seed_CA.csv` and a
  Canadian salience table (Environics/Abacus "most important issue"), and the
  schema already keeps countries apart.
- Item-level reach (per-story audience) would let `I` be computed per item
  rather than per outlet; the formula is unchanged.
