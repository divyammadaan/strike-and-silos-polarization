"""Stage 10: how much of the collected data each analysis actually uses.

A million rows is only justified if the rows do work. This audits, per
analysis, how many comments actually contribute - and shows where they do not,
which is as important for the limitations section as the headline counts are
for the results.

Usage: python 10_utilisation.py  ->  data/processed/utilisation.csv
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PROCESSED_DIR, WINDOWS


def audit(posts, comments, window_key):
    c = comments[comments["window"] == window_key]
    p = posts[posts["window"] == window_key]
    total = len(c)

    post_author = dict(zip(p["id"], p["author_hash"]))
    comment_author = dict(zip(c["id"], c["author_hash"]))

    # A comment contributes a network edge only if we know who wrote it AND
    # who it was replying to. Deleted accounts break both halves.
    has_author = c["author_hash"].notna()
    parent_author = c.apply(
        lambda r: post_author.get(r["parent_ref"]) if r["parent_kind"] == "t3"
        else comment_author.get(r["parent_ref"]), axis=1)
    has_parent = parent_author.notna()
    not_self = c["author_hash"] != parent_author
    usable_edge = has_author & has_parent & not_self

    # Text analysis needs surviving text.
    has_text = (~c["is_deleted"]) & (c["body_len"] > 0)

    # Source analysis needs a link.
    has_link = c["n_links"] > 0

    # How concentrated is participation? One-comment users are most of the
    # accounts but little of the volume.
    per_user = c.loc[has_author].groupby("author_hash").size()
    singletons = int((per_user == 1).sum())
    top1pct_n = max(1, int(len(per_user) * 0.01))
    top1pct_share = per_user.nlargest(top1pct_n).sum() / total * 100

    return {
        "window": window_key,
        "comments_total": total,
        "usable_for_network": int(usable_edge.sum()),
        "pct_usable_for_network": round(usable_edge.mean() * 100, 1),
        "usable_for_text": int(has_text.sum()),
        "pct_usable_for_text": round(has_text.mean() * 100, 1),
        "usable_for_sources": int(has_link.sum()),
        "pct_usable_for_sources": round(has_link.mean() * 100, 1),
        "lost_deleted_author": int((~has_author).sum()),
        "lost_parent_missing": int((has_author & ~has_parent).sum()),
        "unique_users": int(len(per_user)),
        "single_comment_users": singletons,
        "pct_users_with_one_comment": round(singletons / len(per_user) * 100, 1),
        "pct_volume_from_top_1pct_users": round(top1pct_share, 1),
        "posts_total": len(p),
        "posts_with_any_usable_comment": int(
            c.loc[usable_edge, "post_id"].nunique()),
    }


def main():
    posts = pd.read_csv(f"{PROCESSED_DIR}/posts.csv")
    comments = pd.read_csv(f"{PROCESSED_DIR}/comments.csv", low_memory=False)

    rows = [audit(posts, comments, key) for key in WINDOWS]
    table = pd.DataFrame(rows)
    table.to_csv(f"{PROCESSED_DIR}/utilisation.csv", index=False)
    print(table.T.to_string())


if __name__ == "__main__":
    main()
