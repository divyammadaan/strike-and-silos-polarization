"""Stage 5: the subreddit-to-source network (RQ3).

Builds a bipartite graph linking each subreddit to the external domains its
users shared, then measures how much the communities overlap in what they
read. Low overlap plus high within-community concentration is the
information-side counterpart to the reply-network separation in stage 4.

Outputs:
  figures/networks/sources_<window>.gexf
  data/processed/source_metrics.csv
  data/processed/source_overlap_<window>.csv   pairwise subreddit similarity

Usage: python 05_sources.py
"""

import itertools
import os
import sys

import networkx as nx
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FIG_DIR, PROCESSED_DIR, WINDOWS

GEXF_DIR = f"{FIG_DIR}/networks"
SELF_HOSTS = ("reddit.com", "redd.it", "old.reddit.com")


def share_events(posts, comments, window_key):
    """One row per (subreddit, domain) share, from link posts and comments."""
    p = posts[(posts["window"] == window_key) & (posts["is_external_link"] == True)]
    rows = [{"subreddit": s, "domain": d}
            for s, d in zip(p["subreddit"], p["link_domain"]) if isinstance(d, str)]

    c = comments[comments["window"] == window_key]
    for subreddit, domains in zip(c["subreddit"], c["domains"].fillna("")):
        for domain in str(domains).split("|"):
            if domain:
                rows.append({"subreddit": subreddit, "domain": domain})

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df[~df["domain"].str.endswith(SELF_HOSTS)]


def cosine_overlap(matrix):
    """Pairwise cosine similarity between subreddits' domain profiles."""
    normed = matrix.div(np.sqrt((matrix ** 2).sum(axis=1)), axis=0).fillna(0)
    return pd.DataFrame(normed.values @ normed.values.T,
                        index=matrix.index, columns=matrix.index)


def gini(values):
    """Concentration of a subreddit's source diet: 0 = even, 1 = one source."""
    v = np.sort(np.asarray(values, dtype=float))
    if v.sum() == 0:
        return float("nan")
    n = len(v)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(v) / (n * v.sum()))


def analyse(posts, comments, window_key):
    shares = share_events(posts, comments, window_key)
    if shares.empty:
        print(f"  {window_key}: no external links found")
        return None

    counts = shares.groupby(["subreddit", "domain"]).size().rename("weight").reset_index()
    matrix = counts.pivot(index="subreddit", columns="domain",
                          values="weight").fillna(0)

    graph = nx.Graph()
    for subreddit in matrix.index:
        graph.add_node(f"r/{subreddit}", kind="subreddit")
    for row in counts.itertuples(index=False):
        graph.add_node(row.domain, kind="domain")
        graph.add_edge(f"r/{row.subreddit}", row.domain, weight=int(row.weight))
    os.makedirs(GEXF_DIR, exist_ok=True)
    nx.write_gexf(graph, f"{GEXF_DIR}/sources_{window_key}.gexf")

    overlap = cosine_overlap(matrix)
    overlap.to_csv(f"{PROCESSED_DIR}/source_overlap_{window_key}.csv")

    pairs = [overlap.iloc[i, j] for i, j in
             itertools.combinations(range(len(overlap)), 2)]

    return {
        "window": window_key,
        "label": WINDOWS[window_key]["label"],
        "share_events": len(shares),
        "unique_domains": int(shares["domain"].nunique()),
        "subreddits": int(matrix.shape[0]),
        # Mean cosine similarity: lower means communities read different things.
        "mean_pairwise_source_overlap": round(float(np.mean(pairs)), 4) if pairs else None,
        "min_pairwise_source_overlap": round(float(np.min(pairs)), 4) if pairs else None,
        # Mean Gini: higher means each community leans on fewer sources.
        "mean_source_concentration_gini": round(
            float(np.nanmean([gini(matrix.loc[s]) for s in matrix.index])), 4),
        "domains_shared_by_all_subs": int(
            (matrix > 0).all(axis=0).sum()),
        "domains_exclusive_to_one_sub": int(
            ((matrix > 0).sum(axis=0) == 1).sum()),
    }


def main():
    posts = pd.read_csv(f"{PROCESSED_DIR}/posts.csv")
    comments = pd.read_csv(f"{PROCESSED_DIR}/comments.csv", low_memory=False)

    rows = []
    for window_key in WINDOWS:
        print(f"Source network for {window_key} ...")
        metrics = analyse(posts, comments, window_key)
        if metrics:
            rows.append(metrics)

    if rows:
        table = pd.DataFrame(rows)
        table.to_csv(f"{PROCESSED_DIR}/source_metrics.csv", index=False)
        print("\n" + table.to_string(index=False))


if __name__ == "__main__":
    main()
