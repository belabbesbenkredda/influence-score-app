# Reach (R) — sources and normalisation

This note says where every audience figure comes from and how it becomes the
0–1 `R` in `I = R × S × D`. The per-outlet table with links is generated into
`reach_table.md` by `python run.py reach`. The editable source file is
`reach_seed.csv`; the raw collector output is under `data/raw/`.

## The rule that matters

No figure is ever written from memory or inferred. Every row either has a
URL that was fetched, a verbatim quote from that page containing the number,
and a date — or it has `reach_raw` empty and `flag = unsourced`. 16 of 124
outlets are unsourced and they are visible as such everywhere.

## What was used, by type

| Type | Unit | Source | Sourced |
|---|---|---|---|
| print_digital | monthly visits | Semrush website-overview pages, July 2026 (June for smaller domains; the month is on each row) | 43 / 52 |
| cable | average total-day viewers | Nielsen via MediaPost (July 2026); Fox Business Q2 2026 press release for FBN/CNBC | 7 / 8 |
| tv | average total viewers, flagship newscast | Nielsen via Deadline (Q2 2026); The Desk (Univision/Telemundo, week to 12 July 2026); Pew (PBS, 2022) | 6 / 7 |
| radio | estimated weekly listeners | Talkers estimates reproduced in Wikipedia's most-listened-to radio programs table | 9 / 12 |
| podcast | YouTube channel subscribers | The channel's own public count, read off the page | 29 / 30 |
| newsletter | subscribers | The publication's own page ("Over N subscribers") | 14 / 15 |

### Why Semrush and not Press Gazette or Comscore

The brief asked for Comscore or Press Gazette monthly US uniques. Press
Gazette's "Top 50 news websites in the US" page returns 403 to this runner and
publishes no machine-readable table; Comscore publishes no free ranking. Both
would also have covered only the largest 50 outlets, leaving most of the 52
digital outlets here unsourced. Semrush's per-domain overview page gives one
estimate, in one unit, for every domain it covers, which is what a
within-type ranking needs. It is a panel-and-clickstream estimate like
Similarweb's, not a census. Eight outlets have no Semrush page and stay
unsourced rather than being filled from a different unit.

### Why radio is weak

There is no public per-host audience table for American talk radio. Nielsen
does not compile nationwide figures by host, Arbitron said in 2009 the job was
"too complicated, expensive and difficult", and Talkers' own top-talk-audiences
page now 404s. The figures used are Talkers' estimates as reproduced in
Wikipedia's table, which Talkers itself describes as non-scientific and which
carries no date. They are flagged `secondary` and should be read as an ordering,
not a measurement.

## Provenance flags

| Flag | Meaning |
|---|---|
| `ok` | third-party figure, source page re-fetched and the quote found |
| `self_reported` | the outlet's own published figure (newsletters, NPR, Fox Business release) |
| `secondary` | a trade estimate reproduced by another publication (all radio rows) |
| `stale` | sourced but older than the rest (PBS NewsHour, 2022) |
| `unverified` | the source page could not be re-fetched to confirm the number |
| `unsourced` | no figure found; `R` is null and the outlet is unranked |

## Verification

`python -m psi.tools.verify_reach` re-fetches every source URL and checks that
the recorded quote appears in the live page — or, failing an exact match, that
the quote's distinctive number and a distinctive word from it both appear.
It writes `verify_verdict` back into `reach_seed.csv`:

- `verified` → the flag stands.
- `unverifiable` (page blocked or timed out) → flag becomes `unverified`; the
  figure is kept.
- `refuted` (page loaded, number absent) → `run.py reach` **nulls the figure**
  and sets `unsourced`, keeping the candidate value in `notes` for a human.

No model is involved. It is a deterministic text search, so it can be rerun.

## Normalisation (two steps)

**Within type.** Inside each `(type, unit)` group the largest outlet is 1.0:

    reach_norm_type = reach_raw / max(reach_raw in the same type and unit)

Grouping on unit as well as type means a Nielsen total-day figure is never
divided by a monthly-visits figure. Groups with fewer than three outlets are
noted per row.

**Across types.** Each type is then scaled by how much of the American public
that platform reaches for news, from Pew's News Platform Fact Sheet (survey of
US adults, 18–24 August 2025), in `type_weights.csv` with quote and URL:

    weight[type] = platform_share[type] / max(platform_share over types)
    reach_norm   = reach_norm_type × weight[type]

Pew shares used: television 64, news websites or apps 65, radio 44, podcasts
32, email newsletters 30 (percent who get news there often or sometimes).
Cable borrows the television share because Pew does not split cable from
broadcast; that row is flagged `proxy`.

## What this does not claim

- Viewers, visits, listeners and subscribers are not converted into one
  another. A 1.0 means "largest in its type", scaled by that platform's
  overall news reach. Cross-type comparison is a ranking convention, not an
  equivalence.
- Reach is outlet-level. No per-item audience data is used in v0.2.
- Estimates from panel-based vendors (Semrush) and trade estimates (Talkers)
  carry real error bars that are not modelled here.
