"""Stage 2b: narrow the cleaned data to the core, event-driven threads.

Reads the full tables from data/processed/ and writes a core subset to
data/processed_core/, leaving the full data untouched (it is the robustness
baseline). The rule, defined in config.py and identical for both windows and
all subreddits:

  1. Thread size: at least CORE_MIN_COMMENTS comments in the window.
  2. Relevance: an Iran term in the title, or at least CORE_MIN_BODY_MENTIONS
     mentions in the body.

Whole threads are kept or dropped. Comments are never cut inside a kept
thread, because dropping comments breaks reply chains and with them the
network the study is about.

Also writes event_days.csv: per window and day, comment volume, whether the
day is an event day (volume >= EVENT_DAY_FACTOR x the window's median day) and
the biggest thread that day. This is the data-derived event timeline.

Usage: python 02b_core.py
"""

import json
import os
import re
import shutil
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (CORE_DIR, CORE_MIN_BODY_MENTIONS, CORE_MIN_COMMENTS,
                    EVENT_DAY_FACTOR, FULL_PROCESSED_DIR, TOPIC_TERMS, WINDOWS)

TOPIC_RE = re.compile("|".join(re.escape(t) for t in TOPIC_TERMS), re.IGNORECASE)


def select_core(posts, comments):
    """Return (core_posts, core_comments, per-post frame with decisions)."""
    sizes = comments.groupby("post_id").size().rename("n_comments")
    posts = posts.merge(sizes, left_on="id", right_index=True, how="left")
    posts["n_comments"] = posts["n_comments"].fillna(0).astype(int)

    title = posts["title"].fillna("")
    body = posts["selftext"].fillna("")
    posts["iran_in_title"] = title.map(lambda s: bool(TOPIC_RE.search(s)))
    posts["body_mentions"] = body.map(lambda s: len(TOPIC_RE.findall(s)))

    posts["pass_size"] = posts["n_comments"] >= CORE_MIN_COMMENTS
    posts["pass_relevance"] = (posts["iran_in_title"]
                               | (posts["body_mentions"] >= CORE_MIN_BODY_MENTIONS))
    posts["is_core"] = posts["pass_size"] & posts["pass_relevance"]

    core_posts = posts[posts["is_core"]].drop(
        columns=["n_comments", "iran_in_title", "body_mentions",
                 "pass_size", "pass_relevance", "is_core"])
    core_comments = comments[comments["post_id"].isin(set(core_posts["id"]))]
    return core_posts, core_comments, posts


def event_days(posts, comments):
    """Per window/day volume, event-day flag and the largest thread that day."""
    rows = []
    daily = comments.groupby(["window", "date"]).size().rename("comments")
    top = (posts.sort_values("n_comments", ascending=False)
           .groupby(["window", "date"]).first()[["subreddit", "title", "n_comments"]])
    for window in WINDOWS:
        d = daily.loc[window]
        threshold = EVENT_DAY_FACTOR * d.median()
        for date, n in d.items():
            t = top.loc[(window, date)] if (window, date) in top.index else None
            rows.append({
                "window": window, "date": date, "comments": int(n),
                "is_event_day": bool(n >= threshold),
                "top_thread_subreddit": None if t is None else t["subreddit"],
                "top_thread_title": None if t is None else t["title"],
            })
    return pd.DataFrame(rows)


def main():
    posts = pd.read_csv(f"{FULL_PROCESSED_DIR}/posts.csv")
    comments = pd.read_csv(f"{FULL_PROCESSED_DIR}/comments.csv", low_memory=False)
    core_posts, core_comments, decided = select_core(posts, comments)

    os.makedirs(CORE_DIR, exist_ok=True)
    core_posts.to_csv(f"{CORE_DIR}/posts.csv", index=False)
    core_comments.to_csv(f"{CORE_DIR}/comments.csv", index=False)

    # Per subreddit x window: what the rule kept.
    decided["comments_total"] = decided["n_comments"]
    sel = (decided.groupby(["window", "subreddit"])
           .apply(lambda g: pd.Series({
               "posts_full": len(g),
               "posts_core": int(g["is_core"].sum()),
               "comments_full": int(g["n_comments"].sum()),
               "comments_core": int(g.loc[g["is_core"], "n_comments"].sum()),
               "dropped_by_size_only": int((~g["pass_size"]).sum()),
               "dropped_by_relevance_only": int((g["pass_size"] & ~g["pass_relevance"]).sum()),
           }), include_groups=False)
           .reset_index())
    sel["pct_comments_kept"] = (sel["comments_core"] / sel["comments_full"] * 100).round(1)
    sel.to_csv(f"{CORE_DIR}/core_selection.csv", index=False)

    days = event_days(decided, comments)
    days.to_csv(f"{CORE_DIR}/event_days.csv", index=False)

    # 07_report_pack.py reads the quality report; carry the full-data one over
    # and record the core rule next to it.
    quality = json.load(open(f"{FULL_PROCESSED_DIR}/quality_report.json", encoding="utf-8"))
    quality.update({
        "core_min_comments": CORE_MIN_COMMENTS,
        "core_min_body_mentions": CORE_MIN_BODY_MENTIONS,
        "core_posts": len(core_posts),
        "core_comments": len(core_comments),
        "core_share_of_comments_pct": round(len(core_comments) / len(comments) * 100, 1),
    })
    with open(f"{CORE_DIR}/quality_report.json", "w", encoding="utf-8") as f:
        json.dump(quality, f, indent=2)

    print(f"posts    {len(posts):>9,} -> {len(core_posts):>9,}")
    print(f"comments {len(comments):>9,} -> {len(core_comments):>9,} "
          f"({quality['core_share_of_comments_pct']}% kept)")
    print(sel.to_string(index=False))
    print(days[days.is_event_day].groupby("window").size().rename("event_days").to_string())


if __name__ == "__main__":
    main()
