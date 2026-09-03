# Reach (R) — sources and normalisation

This note explains where every audience figure comes from and how it is
turned into the 0–1 `R` used in `I = R × S × D`. The per-outlet table with
links is auto-generated in `reach_table.md` by `python run.py reach`; the
editable source file is `reach_seed.csv`.

## Provenance rules

- Every figure has `reach_source_url`, a verbatim `reach_source_quote`
  copied from that page, and `reach_date` (the period the figure describes).
- Figures were found by research agents and then re-checked by a separate
  fact-check pass that fetched each URL and looked for the number, the
  outlet name and the unit. `verify_verdict` in `reach_seed.csv` records the
  outcome:
  - `verified` → flag stays `ok` (or `self_reported`).
  - `unverifiable` (page blocked the checker) → flag becomes `unverified`.
  - `refuted` (page loaded but did not support the figure) → `reach_raw` is
    set to null and the flag becomes `unsourced`. The candidate figure is
    kept in `notes` for a human to check.
- No figure is ever typed in from memory. Missing = `null` + `unsourced`.

Source tiers (from the brief, best first):

| Tier | Source |
|---|---|
| 1 | Pew Research Center fact sheets |
| 2 | Nielsen (via trade press) |
| 3 | Comscore / Press Gazette (Similarweb) |
| 4 | Reuters Institute Digital News Report |
| 5 | Edison Research, YouTube public counts |
| 6 | Publisher-stated (`self_reported`) |

## Units by outlet type

Units differ by type because the industry measures them differently.

| Type | Unit |
|---|---|
| tv | average total viewers, flagship evening newscast (Nielsen) |
| cable | average total-day viewers (Nielsen); primetime noted when that is all that exists |
| print_digital | monthly US visits (Press Gazette / Similarweb) or Comscore monthly US uniques |
| radio | estimated weekly listeners (Talkers, Nielsen Audio, syndicator) |
| podcast | YouTube channel subscribers (public); Edison rank in notes |
| newsletter | subscribers as printed by the publication or reported in press |

## Normalisation (two steps)

**Step 1 — within type.** Inside each `(type, unit)` group the largest
outlet is 1.0 and everyone else is a fraction of it:

    reach_norm_type = reach_raw / max(reach_raw in same type and unit)

Groups are keyed on unit as well as type so that, say, a Comscore
unique-visitor figure is never divided by a Similarweb visits figure.
Groups with fewer than 3 outlets are noted in `notes`.

**Step 2 — across types.** Each type's leader is scaled by how much of the
US adult public that platform reaches for news, from Pew Research Center's
News Platform Fact Sheet (`type_weights.csv`, with URL, quote and date):

    weight[type] = platform_share[type] / max(platform_share over types)
    reach_norm   = reach_norm_type × weight[type]

Where Pew has no platform figure for a type, the nearest platform's share
is borrowed and flagged `proxy` (cable ← television; newsletter ← news
websites/apps). The weights in force for this run are printed at the top
of `reach_table.md`.

## What this does not do

- It does not convert viewers, visits, listeners and subscribers into one
  another. A "1.0" in each type means "the biggest in its type", scaled by
  the platform's overall reach. That is a ranking convenience, not a claim
  that one Fox News viewer equals one NYT visit.
- It does not measure attention per item. Reach is outlet-level in v0.2.
- Self-reported figures (`self_reported`) are included but visibly flagged.
