"""Stage 6: select threads for the qualitative pass (RQ4).

Network measures say *whether* communities separated; reading threads is what
lets us say *what* they were separating over. This script picks a defensible
sample rather than whatever we happen to notice:

  - the most-commented threads per subreddit per window (where the discussion was)
  - the most controversial threads (high comment volume, low upvote ratio)
  - threads that drew commenters from more than one detected community
    (the places where cross-community contact actually happened)

Writes data/processed/qualitative_sample.csv with permalinks, for the team to
read and code by hand.

Usage: python 06_sample_threads.py
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PROCESSED_DIR, WINDOWS

PER_BUCKET = 10


def top_by(df, column, n, reason, ascending=False):
    picked = df.sort_values(column, ascending=ascending).head(n).copy()
    picked["selection_reason"] = reason
    return picked


def cross_community_threads(posts, comments, window_key, n):
    """Threads whose commenters came from the widest mix of subreddits.

    Users are labelled by the subreddit they comment in most, so a thread with
    a high mix drew people who normally post elsewhere.
    """
    c = comments[comments["window"] == window_key]
    homes = (c.groupby(["author_hash", "subreddit"]).size()
             .reset_index(name="n").sort_values("n", ascending=False)
             .drop_duplicates("author_hash"))
    home_map = dict(zip(homes["author_hash"], homes["subreddit"]))

    c = c.assign(home=c["author_hash"].map(home_map))
    mix = (c.groupby("post_id")["home"].nunique().rename("home_subreddits")
           .reset_index())
    busy = c.groupby("post_id").size().rename("n_comments").reset_index()
    mix = mix.merge(busy, on="post_id")
    mix = mix[mix["n_comments"] >= 25]

    merged = posts.merge(mix, left_on="id", right_on="post_id")
    merged = merged[merged["window"] == window_key]
    return top_by(merged, "home_subreddits", n, "cross-community contact")


def main():
    posts = pd.read_csv(f"{PROCESSED_DIR}/posts.csv")
    comments = pd.read_csv(f"{PROCESSED_DIR}/comments.csv", low_memory=False)

    picks = []
    for window_key in WINDOWS:
        p = posts[posts["window"] == window_key]
        if p.empty:
            continue

        for subreddit, group in p.groupby("subreddit"):
            picks.append(top_by(group, "num_comments", 3,
                                f"most-commented in r/{subreddit}"))

        busy = p[p["num_comments"] >= 50]
        if not busy.empty and busy["upvote_ratio"].notna().any():
            picks.append(top_by(busy, "upvote_ratio", PER_BUCKET,
                                "contested (low upvote ratio, high volume)",
                                ascending=True))

        picks.append(cross_community_threads(posts, comments, window_key, PER_BUCKET))

    sample = pd.concat(picks, ignore_index=True)
    cols = ["window", "subreddit", "id", "title", "num_comments", "score",
            "upvote_ratio", "selection_reason", "permalink"]
    cols = [c for c in cols if c in sample.columns]
    sample = sample[cols].drop_duplicates(subset=["id", "selection_reason"])

    out = f"{PROCESSED_DIR}/qualitative_sample.csv"
    sample.to_csv(out, index=False)
    print(sample.groupby(["window", "selection_reason"]).size().to_string())
    print(f"\n{len(sample)} threads written to {out}")


if __name__ == "__main__":
    main()
