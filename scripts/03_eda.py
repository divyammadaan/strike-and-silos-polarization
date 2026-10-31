"""Stage 3: exploratory analysis and figures (Phase 2 "preliminary analysis").

Produces:
  figures/volume_by_day.png        activity around each escalation
  figures/posts_by_subreddit.png   where the discussion happened
  figures/comment_length.png       distribution of comment length
  figures/top_domains.png          most-shared external sources per window
  data/processed/eda_summary.csv   the numbers behind the figures

Usage: python 03_eda.py
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FIG_DIR, PROCESSED_DIR, SUBREDDITS, WINDOWS

plt.rcParams.update({"figure.dpi": 140, "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False})

WINDOW_COLORS = {"june_2025": "#4C78A8", "feb_2026": "#E45756"}


def load():
    posts = pd.read_csv(f"{PROCESSED_DIR}/posts.csv")
    comments = pd.read_csv(f"{PROCESSED_DIR}/comments.csv", low_memory=False)
    comments["domains"] = comments["domains"].fillna("")
    return posts, comments


def day_index(df, window_key):
    """Days since the start of that window, so the two can be overlaid."""
    start = pd.Timestamp(WINDOWS[window_key]["start"])
    dates = pd.to_datetime(df["date"])
    return (dates - start).dt.days


def plot_volume(posts, comments):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4), sharex=True)
    for ax, (df, name) in zip(axes, [(posts, "Posts"), (comments, "Comments")]):
        for key in WINDOWS:
            sub = df[df["window"] == key]
            if sub.empty:
                continue
            counts = day_index(sub, key).value_counts().sort_index()
            ax.plot(counts.index, counts.values, marker="o", ms=3,
                    color=WINDOW_COLORS[key], label=WINDOWS[key]["label"])
        ax.set_title(f"{name} per day")
        ax.set_xlabel("Days since first strike")
        ax.set_ylabel(name.lower())
    axes[0].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/volume_by_day.png", bbox_inches="tight")
    plt.close(fig)


def plot_by_subreddit(posts, comments):
    table = (comments.groupby(["window", "subreddit"]).size()
             .unstack(fill_value=0).reindex(columns=SUBREDDITS, fill_value=0))
    fig, ax = plt.subplots(figsize=(8, 3.4))
    x = range(len(SUBREDDITS))
    width = 0.4
    for i, key in enumerate(WINDOWS):
        if key not in table.index:
            continue
        # Share of the window's comments, so the two windows are comparable
        # even though Feb 2026 produced far more volume overall.
        share = table.loc[key] / table.loc[key].sum() * 100
        ax.bar([xi + i * width for xi in x], share.values, width,
               color=WINDOW_COLORS[key], label=WINDOWS[key]["label"])
    ax.set_xticks([xi + width / 2 for xi in x])
    ax.set_xticklabels([f"r/{s}" for s in SUBREDDITS], rotation=30, ha="right")
    ax.set_ylabel("% of window's comments")
    ax.set_title("Where the discussion happened")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/posts_by_subreddit.png", bbox_inches="tight")
    plt.close(fig)


def plot_comment_length(comments):
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    for key in WINDOWS:
        sub = comments[(comments["window"] == key) & (~comments["is_deleted"])]
        if sub.empty:
            continue
        ax.hist(sub["body_len"].clip(upper=1500), bins=60, histtype="step",
                density=True, color=WINDOW_COLORS[key], label=WINDOWS[key]["label"])
    ax.set_xlabel("comment length (characters, clipped at 1500)")
    ax.set_ylabel("density")
    ax.set_title("Comment length distribution")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/comment_length.png", bbox_inches="tight")
    plt.close(fig)


def domain_counts(posts, comments, window_key, top=15):
    """External domains shared in link posts and in comment bodies."""
    from_posts = posts[(posts["window"] == window_key) & posts["is_external_link"]]
    counts = from_posts["link_domain"].value_counts()

    comment_rows = comments[comments["window"] == window_key]
    exploded = (comment_rows["domains"].str.split("|").explode()
                .replace("", pd.NA).dropna())
    exploded = exploded[~exploded.str.contains("redd.it|reddit.com", na=False)]
    counts = counts.add(exploded.value_counts(), fill_value=0)
    return counts.sort_values(ascending=False).head(top)


def plot_top_domains(posts, comments):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, key in zip(axes, WINDOWS):
        counts = domain_counts(posts, comments, key)
        if counts.empty:
            continue
        ax.barh(counts.index[::-1], counts.values[::-1], color=WINDOW_COLORS[key])
        ax.set_title(WINDOWS[key]["label"])
        ax.set_xlabel("times shared")
    fig.suptitle("Most-shared external sources")
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/top_domains.png", bbox_inches="tight")
    plt.close(fig)


def summary_table(posts, comments):
    rows = []
    for key in WINDOWS:
        p = posts[posts["window"] == key]
        c = comments[comments["window"] == key]
        rows.append({
            "window": key,
            "label": WINDOWS[key]["label"],
            "posts": len(p),
            "comments": len(c),
            "subreddits": p["subreddit"].nunique(),
            "unique_commenters": c["author_hash"].nunique(),
            "comments_per_post": round(len(c) / max(len(p), 1), 1),
            "median_comment_len": int(c.loc[~c["is_deleted"], "body_len"].median() or 0),
            "pct_deleted_comments": round(c["is_deleted"].mean() * 100, 1),
            "pct_comments_with_link": round((c["n_links"] > 0).mean() * 100, 1),
            "pct_nested_replies": round((~c["is_top_level"]).mean() * 100, 1),
            "cross_sub_users": None,  # filled below
        })
    table = pd.DataFrame(rows)

    # Users active in more than one subreddit: an early signal for RQ2.
    for i, key in enumerate(WINDOWS):
        c = comments[comments["window"] == key]
        per_user = c.groupby("author_hash")["subreddit"].nunique()
        table.loc[i, "cross_sub_users"] = int((per_user > 1).sum())

    table.to_csv(f"{PROCESSED_DIR}/eda_summary.csv", index=False)
    return table


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    posts, comments = load()
    plot_volume(posts, comments)
    plot_by_subreddit(posts, comments)
    plot_comment_length(comments)
    plot_top_domains(posts, comments)
    table = summary_table(posts, comments)
    print(table.to_string(index=False))
    print(f"\nFigures written to {FIG_DIR}/")


if __name__ == "__main__":
    main()
