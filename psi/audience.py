"""Converting each medium's native currency into one comparable quantity:
estimated US adults who encountered a single item.

The problem this solves (decision D05, rejected by BB): the v0.2 index compared
YouTube subscribers, monthly web visits, average TV viewers and newsletter
subscribers by dividing each by its own category leader. A subscriber is a
standing relationship, a visit is one event, a viewer is an average moment;
scaling each to its own maximum does not make them comparable, it only hides
the fact that they aren't.

The method here is the one BB proposed for radio (D09), generalised:

    every medium gives us a reliable AGGREGATE (weekly listeners, monthly
    visits, subscribers) and, where we can observe it, a per-item SIGNAL
    (views on that episode, engagement on that URL).

    R_item = aggregate x (this item's signal / all signals this period)

The aggregate sets the level; the signal sets the distribution. R is then
expressed as a share of the US adult population, so it is an absolute
penetration rate rather than a rank — comparable across media, across time,
and across countries.

Per-item signals are not yet collected, so this module currently supplies the
LEVEL ONLY: the estimated audience of a *typical* item from each outlet. Every
row it produces is flagged `modelled` and carries the basis string naming which
rule and which constants produced it. The distribution step is the next build.

EVERY CONSTANT BELOW IS AN ASSUMPTION, NOT A MEASUREMENT. They are gathered
here, named, and documented so they can be argued with and replaced one at a
time. Nothing in this file is sourced data; the sourced figures live in
data/reach_seed.csv.
"""
from __future__ import annotations

# US adults, the denominator that turns a headcount into a penetration rate.
# Census Bureau resident population 18+, 2024 vintage, rounded.
US_ADULTS = 262_000_000
US_ADULTS_SOURCE = "US Census Bureau resident population 18+, 2024 vintage (rounded)"

# --- assumptions, each one editable and each one currently unvalidated -------

# A weekly-listener figure is a cume: unique people across the whole week, not
# the sum of episode audiences. Dividing by episodes per week understates the
# per-episode audience where listening is habitual and overstates it where it
# is occasional. Talk radio is habitual, so this is a conservative floor.
RADIO_EPISODES_PER_WEEK = 5

# What share of a channel's subscribers watch any given episode. Subscribers
# accumulate for ever and never decay, so this is small. Replaced outlet by
# outlet as soon as real per-video view counts are collected.
PODCAST_EPISODE_VIEW_RATE = 0.10

# Podcast audio listening that never appears in YouTube numbers, as a multiple
# of the video audience. For talk shows the audio feed is usually the larger
# half; this is the single crudest constant in the file.
PODCAST_AUDIO_MULTIPLE = 1.0

# Share of newsletter subscribers who open a given issue. Substack does not
# publish per-publication open rates; industry reporting clusters around 40%.
NEWSLETTER_OPEN_RATE = 0.40

# Articles a national digital outlet publishes in a month, used to turn monthly
# visits into visits per article. This is the weakest constant here: real output
# ranges from tens (Jacobin) to thousands (NY Post), so it should be replaced by
# a per-outlet count as soon as the sampler records one.
DIGITAL_ITEMS_PER_MONTH = 800

# Fraction of a TV programme's average audience that any one segment reaches.
# Total-day and evening-newscast averages already describe a typical minute, so
# a segment is close to the whole; kept explicit so it can be tuned.
TV_SEGMENT_SHARE = 1.0

ASSUMPTIONS = {
    "RADIO_EPISODES_PER_WEEK": (RADIO_EPISODES_PER_WEEK, "weekly cume divided across this many episodes"),
    "PODCAST_EPISODE_VIEW_RATE": (PODCAST_EPISODE_VIEW_RATE, "share of subscribers watching a given episode"),
    "PODCAST_AUDIO_MULTIPLE": (PODCAST_AUDIO_MULTIPLE, "audio listeners per video viewer"),
    "NEWSLETTER_OPEN_RATE": (NEWSLETTER_OPEN_RATE, "share of subscribers opening an issue"),
    "DIGITAL_ITEMS_PER_MONTH": (DIGITAL_ITEMS_PER_MONTH, "articles per month, to split monthly visits"),
    "TV_SEGMENT_SHARE": (TV_SEGMENT_SHARE, "share of a programme's average audience reached by one segment"),
}


def us_share(unit: str | None, notes: str | None) -> tuple[float, str]:
    """How much of a figure is American.

    Semrush publishes a per-domain country split and the collector records it in
    `notes` as 'US visits (NN.N% of worldwide)'. Nielsen and Talkers figures are
    US-only by construction. Anything else is unadjusted and says so.
    """
    unit = unit or ""
    if unit in {"avg_total_day_viewers", "avg_total_viewers_flagship_newscast", "weekly_listeners"}:
        return 1.0, "US-only by construction"
    if notes and "US visits (" in notes:
        return 1.0, "already US-only (Semrush country split)"
    if unit == "monthly_visits_semrush":
        return 1.0, "UNADJUSTED: worldwide visits, no US split published"
    if unit in {"youtube_subscribers", "subscribers"}:
        return 1.0, "UNADJUSTED: no public country split for this platform"
    return 1.0, "UNADJUSTED: unknown unit"


def people_per_item(outlet_type: str, unit: str | None, raw: float | None, notes: str | None) -> tuple[float | None, str]:
    """Estimated US adults reaching one typical item from this outlet.

    Returns (people, basis). `people` is None when the medium's currency cannot
    be converted at all, which is a gap to report rather than a number to guess.
    """
    if raw is None or not unit:
        return None, "no sourced reach figure"
    share, share_note = us_share(unit, notes)
    base = raw * share

    if unit in {"avg_total_day_viewers", "avg_total_viewers_flagship_newscast"}:
        return base * TV_SEGMENT_SHARE, f"programme average viewers x TV_SEGMENT_SHARE ({share_note})"
    if unit == "weekly_listeners":
        return base / RADIO_EPISODES_PER_WEEK, (
            f"weekly cume / RADIO_EPISODES_PER_WEEK ({share_note}); cume overlap not modelled")
    if unit == "youtube_subscribers":
        return base * PODCAST_EPISODE_VIEW_RATE * (1 + PODCAST_AUDIO_MULTIPLE), (
            f"subscribers x PODCAST_EPISODE_VIEW_RATE x (1 + PODCAST_AUDIO_MULTIPLE) ({share_note})")
    if unit == "subscribers":
        return base * NEWSLETTER_OPEN_RATE, f"subscribers x NEWSLETTER_OPEN_RATE ({share_note})"
    if unit == "monthly_visits_semrush":
        return base / DIGITAL_ITEMS_PER_MONTH, (
            f"monthly visits / DIGITAL_ITEMS_PER_MONTH ({share_note}); a visit is not a read")
    if unit.startswith("monthly_downloads"):
        return base, f"stated downloads per episode ({share_note})"
    return None, f"no conversion rule for unit {unit!r}"


def penetration(people: float | None) -> float | None:
    """People reached, as a share of US adults."""
    return None if people is None else people / US_ADULTS
