"""Stage 9: Gephi-sized exports of the reply networks.

The full user graphs are ~90k and ~120k nodes, which Gephi will not lay out
comfortably on a laptop (the raw .gexf files are 75-110 MB). This produces two
smaller views of the same data:

  1. <window>_core.gexf - the k-core of the user network, keeping only users
     with at least K mutual-ish connections. Removes the huge fringe of
     one-reply accounts that contributes no visible structure but most of the
     nodes.
  2. subreddits_<window>.gexf - the same edges aggregated to 8 subreddit
     nodes, weighted by how many replies ran between each pair. This is the
     view to put in the report: it shows cross-community interaction directly.

Also writes data/processed/subreddit_edges_<window>.csv, the aggregated
numbers behind the second graph.

Usage:
    python 09_export_gephi.py           # default k
    python 09_export_gephi.py --k 3
"""

import argparse
import importlib
import os
import sys
from collections import Counter

import networkx as nx
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FIG_DIR, PROCESSED_DIR, WINDOWS

networks = importlib.import_module("04_networks")

GEXF_DIR = f"{FIG_DIR}/networks"


def export_core(graph, homes, window_key, k):
    """k-core of the undirected projection, with community labels kept."""
    undirected = graph.to_undirected()
    core = nx.k_core(undirected, k=k)
    if core.number_of_nodes() == 0:
        print(f"  {window_key}: {k}-core is empty, skipping")
        return

    partition, modularity, _ = networks.detect_communities(core)
    nx.set_node_attributes(core, partition, "community")
    nx.set_node_attributes(core, {n: homes.get(n, "unknown") for n in core},
                           "home_subreddit")
    nx.set_node_attributes(core, dict(core.degree()), "degree")

    path = f"{GEXF_DIR}/{window_key}_core{k}.gexf"
    nx.write_gexf(core, path)
    print(f"  {window_key}: {k}-core has {core.number_of_nodes()} nodes, "
          f"{core.number_of_edges()} edges, modularity {modularity:.3f} -> {path}")


def export_subreddit_graph(edges, homes, window_key):
    """Collapse user-user replies into subreddit-subreddit reply counts."""
    pair_counts = Counter()
    for source, target, _ in edges:
        hs, ht = homes.get(source), homes.get(target)
        if hs and ht:
            pair_counts[(hs, ht)] += 1

    graph = nx.DiGraph()
    for (source, target), weight in pair_counts.items():
        graph.add_edge(f"r/{source}", f"r/{target}", weight=weight)

    # Node size = how much of the window's reply activity the community holds.
    totals = Counter()
    for (source, target), weight in pair_counts.items():
        totals[source] += weight
        totals[target] += weight
    nx.set_node_attributes(graph, {f"r/{s}": int(v) for s, v in totals.items()},
                           "activity")

    path = f"{GEXF_DIR}/subreddits_{window_key}.gexf"
    nx.write_gexf(graph, path)

    rows = [{"source": s, "target": t, "replies": w,
             "is_cross_community": s != t}
            for (s, t), w in sorted(pair_counts.items(), key=lambda kv: -kv[1])]
    df = pd.DataFrame(rows)
    df.to_csv(f"{PROCESSED_DIR}/subreddit_edges_{window_key}.csv", index=False)

    cross = df.loc[df["is_cross_community"], "replies"].sum()
    total = df["replies"].sum()
    print(f"  {window_key}: subreddit graph -> {path}; "
          f"{cross / total * 100:.1f}% of replies cross communities")

    # The headline cross-community share is dominated by one pair of large,
    # general-audience US communities. RQ2 asks about contact between
    # *different* discussion communities, so the share is also reported with
    # that pair removed - which is a materially different number.
    dominant = df[df["is_cross_community"]].nlargest(1, "replies")
    if not dominant.empty:
        a, b = dominant.iloc[0]["source"], dominant.iloc[0]["target"]
        pair = df[(df["source"].isin([a, b])) & (df["target"].isin([a, b]))
                  & df["is_cross_community"]]["replies"].sum()
        print(f"    dominant pair r/{a}<->r/{b} is {pair / total * 100:.2f}% of all "
              f"replies; excluding it, cross-community = "
              f"{(cross - pair) / total * 100:.2f}%")
        return df, {
            "window": window_key,
            "pct_cross_community": round(cross / total * 100, 2),
            "dominant_pair": f"{a}<->{b}",
            "pct_dominant_pair": round(pair / total * 100, 2),
            "pct_cross_excluding_dominant_pair": round((cross - pair) / total * 100, 2),
        }
    return df, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--skip-core", action="store_true",
                        help="only the cheap subreddit-level export")
    args = parser.parse_args()

    posts = pd.read_csv(f"{PROCESSED_DIR}/posts.csv")
    comments = pd.read_csv(f"{PROCESSED_DIR}/comments.csv", low_memory=False)
    os.makedirs(GEXF_DIR, exist_ok=True)

    summaries = []
    for window_key in WINDOWS:
        print(f"{WINDOWS[window_key]['label']}:")
        edges = networks.build_reply_edges(posts, comments, window_key)
        homes = networks.home_subreddit(comments, window_key)

        _, summary = export_subreddit_graph(edges, homes, window_key)
        if summary:
            summaries.append(summary)

        if not args.skip_core:
            export_core(networks.build_graph(edges), homes, window_key, args.k)

    if summaries:
        out = f"{PROCESSED_DIR}/cross_community_summary.csv"
        pd.DataFrame(summaries).to_csv(out, index=False)
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
