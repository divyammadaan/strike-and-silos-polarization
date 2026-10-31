"""Stage 8: robustness checks for the two headline comparisons.

Both headline results are confounded by size, and the confound runs in the
direction of the result, so they cannot be reported without this check:

  * February 2026 produced a bigger reply network on every count. Modularity
    is not size-invariant, so a lower Feb modularity might mean "less
    separated" or might just mean "bigger graph".
  * February 2026 produced more link shares, and more shares means a longer
    tail of rare domains, which mechanically lowers cosine overlap and raises
    the count of single-subreddit domains.

  (Current values are in data/processed/network_metrics.csv and
  source_metrics.csv; they are not repeated here so this note cannot go stale.)

Two controls, both by subsampling the larger window down to the smaller one:

  1. Reply network: sample edges down to the smaller window's edge count,
     recompute modularity and the E-I index, repeat, and compare distributions.
     Also compares each window against a degree-preserving random null, so
     "how much more clustered than chance" is comparable across sizes.
  2. Source network: sample share events down to the smaller window's count
     and recompute the overlap and concentration measures.

Usage:
    python 08_robustness.py            # default replicates
    python 08_robustness.py --reps 5
"""

import argparse
import os
import random
import sys

import networkx as nx
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PROCESSED_DIR, WINDOWS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
networks = importlib.import_module("04_networks")
sources = importlib.import_module("05_sources")


NULL_REPS = 3  # random graphs averaged for the null-model baseline


def sampled_graph_metrics(edges, homes, n_edges, seed):
    """Modularity / E-I on a random subsample of the edge list."""
    rng = random.Random(seed)
    sample = rng.sample(edges, n_edges)
    graph = networks.build_graph(sample)
    partition, modularity, _ = networks.detect_communities(graph)
    return {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "modularity": modularity,
        "ei_index_louvain": networks.ei_index(graph, partition),
        "ei_index_by_subreddit": networks.ei_index(graph, homes),
    }


def unweighted_modularity(graph):
    """Louvain modularity ignoring edge weights.

    The random null graph has no weights, so the observed value it is compared
    with has to be computed without them too.
    """
    undirected = graph.to_undirected()
    communities = nx.community.louvain_communities(undirected, seed=42,
                                                   weight=None)
    return nx.community.modularity(undirected, communities, weight=None)


def null_modularity(graph, seed):
    """Modularity of a degree-preserving random graph with the same degrees.

    The gap between observed and null modularity is the part of the clustering
    that is not explained by the degree distribution alone, which is what makes
    two differently sized networks comparable.
    """
    undirected = graph.to_undirected()
    degrees = [d for _, d in undirected.degree()]
    rng = np.random.default_rng(seed)
    null = nx.configuration_model(degrees, seed=int(rng.integers(1 << 30)))
    null = nx.Graph(null)          # collapse parallel edges
    null.remove_edges_from(nx.selfloop_edges(null))
    communities = nx.community.louvain_communities(null, seed=42, weight=None)
    return nx.community.modularity(null, communities, weight=None)


def network_checks(posts, comments, reps):
    edge_lists = {}
    for key in WINDOWS:
        edges = networks.build_reply_edges(posts, comments, key)
        edge_lists[key] = edges
        print(f"  {key}: {len(edges)} edge events")

    target = min(len(e) for e in edge_lists.values())
    print(f"  subsampling both windows to {target} edge events, {reps} reps")

    rows = []
    for key, edges in edge_lists.items():
        graph = networks.build_graph(edges)
        observed_partition, observed_mod, _ = networks.detect_communities(graph)
        homes = networks.home_subreddit(comments, key)
        print(f"  {key}: computing random null ({NULL_REPS} graphs) ...")
        observed_unweighted = unweighted_modularity(graph)
        null_mod = float(np.mean([null_modularity(graph, seed=7 + i)
                                  for i in range(NULL_REPS)]))

        for rep in range(reps):
            metrics = sampled_graph_metrics(edges, homes, target, seed=100 + rep)
            rows.append({"window": key, "rep": rep, **metrics})
            print(f"    rep {rep}: modularity {metrics['modularity']:.4f}, "
                  f"E-I {metrics['ei_index_louvain']:.4f}")

        rows.append({"window": key, "rep": "full",
                     "nodes": graph.number_of_nodes(),
                     "edges": graph.number_of_edges(),
                     "modularity": observed_mod,
                     "ei_index_louvain": networks.ei_index(graph, observed_partition),
                     "ei_index_by_subreddit": networks.ei_index(graph, homes),
                     "modularity_unweighted": observed_unweighted,
                     "null_modularity": null_mod,
                     "modularity_above_null": observed_unweighted - null_mod})
    return pd.DataFrame(rows)


def source_checks(posts, comments, reps):
    shares = {key: sources.share_events(posts, comments, key) for key in WINDOWS}
    target = min(len(s) for s in shares.values())
    print(f"  subsampling share events to {target}, {reps} reps")

    rows = []
    for key, df in shares.items():
        for rep in range(reps):
            sample = df.sample(n=target, random_state=200 + rep)
            counts = (sample.groupby(["subreddit", "domain"]).size()
                      .rename("weight").reset_index())
            matrix = counts.pivot(index="subreddit", columns="domain",
                                  values="weight").fillna(0)
            overlap = sources.cosine_overlap(matrix)
            pairs = [overlap.iloc[i, j]
                     for i in range(len(overlap)) for j in range(i + 1, len(overlap))]
            rows.append({
                "window": key, "rep": rep,
                "share_events": len(sample),
                "unique_domains": int(sample["domain"].nunique()),
                "mean_pairwise_source_overlap": float(np.mean(pairs)),
                "mean_source_concentration_gini": float(np.nanmean(
                    [sources.gini(matrix.loc[s]) for s in matrix.index])),
                "domains_exclusive_to_one_sub": int(((matrix > 0).sum(axis=0) == 1).sum()),
            })
    return pd.DataFrame(rows)


def summarise(df, label, columns):
    print(f"\n{label} (mean over subsamples):")
    summary = df[df["rep"] != "full"].groupby("window")[columns].mean().round(4)
    print(summary.to_string())
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reps", type=int, default=10)
    args = parser.parse_args()

    posts = pd.read_csv(f"{PROCESSED_DIR}/posts.csv")
    comments = pd.read_csv(f"{PROCESSED_DIR}/comments.csv", low_memory=False)

    print("Source-sharing robustness ...")
    source_df = source_checks(posts, comments, args.reps)
    source_df.to_csv(f"{PROCESSED_DIR}/robustness_sources.csv", index=False)
    summarise(source_df, "Source metrics at equal share count",
              ["unique_domains", "mean_pairwise_source_overlap",
               "mean_source_concentration_gini", "domains_exclusive_to_one_sub"])

    print("\nReply-network robustness ...")
    net_df = network_checks(posts, comments, args.reps)
    net_df.to_csv(f"{PROCESSED_DIR}/robustness_networks.csv", index=False)
    summarise(net_df, "Network metrics at equal edge count",
              ["nodes", "modularity", "ei_index_louvain",
               "ei_index_by_subreddit"])

    full = net_df[net_df["rep"] == "full"]
    if "modularity_above_null" in full:
        print("\nObserved vs degree-preserving random null (unweighted):")
        print(full[["window", "modularity_unweighted", "null_modularity",
                    "modularity_above_null"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
