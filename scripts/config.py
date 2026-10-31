"""Shared configuration for the CSMA project pipeline.

Everything that defines the study design (which subreddits, which time
windows, which keywords) lives here so that the collection, cleaning and
analysis scripts all work from one definition.
"""

import os

# --- Observation windows -------------------------------------------------
# Two windows of equal length (21 days), each starting on the first day of
# major strikes in that escalation. Equal length matters because almost every
# comparison below (volume, network size, modularity) is sensitive to how long
# we observed.
WINDOWS = {
    "june_2025": {
        "label": "June 2025 strikes",
        "start": "2025-06-13",
        "end": "2025-07-04",  # exclusive
        "baseline_start": "2025-06-06",  # 7 quiet days before, for comparison
    },
    "feb_2026": {
        "label": "February 2026 strikes",
        "start": "2026-02-28",
        "end": "2026-03-21",  # exclusive
        "baseline_start": "2026-02-21",
    },
}

# --- Communities ---------------------------------------------------------
# Mix of general news, analysis and the two region-focused communities, so
# that there is something for community detection to actually separate.
SUBREDDITS = [
    "worldnews",
    "geopolitics",
    "Iran",
    "Israel",
    "NewIran",
    "IsraelPalestine",
    "politics",
    "Conservative",
]

# --- Query -------------------------------------------------------------
# A post is in scope if its title or selftext contains any of these terms
# (case-insensitive). Applied identically to every subreddit and both windows,
# so the sampling rule is the same on both sides of the comparison.
#
# Every term names Iran or something Iran-specific. Deliberately no generic
# war vocabulary ("strike", "nuclear", "bombing"): in r/politics and
# r/worldnews those match labour strikes, unrelated bombings and energy policy,
# and adding them alongside an Iran term changes nothing, because the Iran term
# already had to match.
TOPIC_TERMS = [
    "iran", "iranian", "tehran", "irgc", "khamenei", "ayatollah",
    "fordow", "natanz", "isfahan", "bushehr",
    "hormuz", "persian gulf",
]

# --- Collection limits -------------------------------------------------
# A pilot count (1 day, 8 subreddits) returned ~22k comments for June 2025 and
# ~47k for Feb 2026, i.e. roughly 1.4M comments over the two 21-day windows.
# That is far more than the analysis needs and a multi-GB download, so we cap
# comments per post and skip threads too small to contribute reply edges.
# Both limits are applied identically to both windows, and the number of posts
# that hit the cap is logged, so the effect on the comparison is measurable
# rather than invisible.
MAX_COMMENTS_PER_POST = 1500
# Threads with fewer than 10 comments are ~45% of on-topic posts but hold only
# ~3% of the comments and almost no nested replies, so excluding them costs
# very little signal and roughly halves collection time. 02_clean.py applies
# the same threshold when building the analysis tables, so the rule is uniform
# across both windows regardless of what an earlier run happened to collect.
MIN_COMMENTS_TO_FETCH = 10
API_BASE = "https://arctic-shift.photon-reddit.com/api"
REQUEST_SLEEP = 0.3  # seconds between paged calls, to stay polite
CONCURRENCY = 8      # parallel comment fetches in 01_collect.py

# --- Core dataset ----------------------------------------------------------
# 02b_core.py narrows the cleaned data to the threads that carry the
# discussion of the escalations. Whole threads are kept or dropped, never
# individual comments, so reply chains (the network's edges) stay intact.
# The same rule is applied to both windows and every subreddit.
CORE_MIN_COMMENTS = 50       # threads below this hold ~11% of comments
# Relevance: Iran term in the title, or at least this many mentions in the
# body. Drops threads that only mention Iran in passing (e.g. a US budget
# thread), which the keyword sampling in 01_collect.py cannot tell apart.
CORE_MIN_BODY_MENTIONS = 2
# A day is an "event day" if its comment volume is at least this multiple of
# the window's median day. Data-driven, so it flags the same kind of day in
# both windows without hand-picked dates.
EVENT_DAY_FACTOR = 1.25

# --- Paths ---------------------------------------------------------------
# CSMA_VARIANT=core makes stages 03-10 read the core dataset and write to
# separate folders, so the full-data results are never overwritten.
VARIANT = os.environ.get("CSMA_VARIANT", "full")
RAW_DIR = "data/raw"
FULL_PROCESSED_DIR = "data/processed"
CORE_DIR = "data/processed_core"
PROCESSED_DIR = FULL_PROCESSED_DIR if VARIANT == "full" else CORE_DIR
FIG_DIR = "figures" if VARIANT == "full" else "figures/core"
