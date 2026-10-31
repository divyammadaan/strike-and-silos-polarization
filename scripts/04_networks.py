"""Stage 4: user reply networks, community detection and separation measures.

For each window we build a directed user-to-user graph: an edge A -> B means
A replied to a comment or post written by B. We then detect communities and
measure how separated they are, which is how this project operationalises
"polarization" (RQ1, RQ2).

Outputs:
  figures/networks/<window>.gexf      for Gephi
  data/processed/network_metrics.csv  the comparison table
  data/processed/community_profile_<window>.csv  which subreddits each
                                       detected community actually came from

Usage: python 04_networks.py
"""

import os
import sys

import networkx as nx
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FIG_DIR, PROCESSED_DIR, WINDOWS

GEXF_DIR = f"{FIG_DIR}/networks"
BETWEENNESS_PIVOTS = 100  # sample size for approximate betweenness


def build_reply_edges(posts, comments, window_key):
    """Edges from replier -> author being replied to.

    A comment's parent is either the post (t3_) or another comment (t1_), so we
    look the author up in whichever table applies.
    """
    p = posts[posts["window"] == window_key]
    c = comments[comments["window"] == window_key]

    post_author = dict(zip(p["id"], p["author_hash"]))
    comment_author = dict(zip(c["id"], c["author_hash"]))

    edges = []
    for row in c.itertuples(index=False):
        source = row.author_hash
        if not isinstance(source, str):
            continue  # deleted account: no identity to attach an edge to
        if row.parent_kind == "t3":
            target = post_author.get(row.parent_ref)
        else:
            target = comment_author.get(row.parent_ref)
        if not isinstance(target, str) or target == source:
            continue  # missing parent (not collected / deleted), or self-reply
        edges.append((source, target, row.subreddit))
    return edges


def build_graph(edges):
    g = nx.DiGraph()
    for source, target, subreddit in edges:
        if g.has_edge(source, target):
            g[source][target]["weight"] += 1
        else:
            g.add_edge(source, target, weight=1, subreddit=subreddit)
    return g


def home_subreddit(comments, window_key):
    """The subreddit where each user commented most, used to label nodes."""
    c = comments[comments["window"] == window_key]
    counts = c.groupby(["author_hash", "subreddit"]).size().reset_index(name="n")
    counts = counts.sort_values("n", ascending=False).drop_duplicates("author_hash")
    return dict(zip(counts["author_hash"], counts["subreddit"]))


def detect_communities(graph):
    """Louvain on the undirected projection (Louvain needs undirected input).

    Reply direction matters for who-answers-whom, but community detection asks
    who is in conversation with whom, which is symmetric.
    """
    undirected = graph.to_undirected()
    for u, v, data in undirected.edges(data=True):
        data.setdefault("weight", 1)
    communities = nx.community.louvain_communities(undirected, seed=42,
                                                   weight="weight")
    partition = {n: i for i, com in enumerate(communities) for n in com}
    modularity = nx.community.modularity(undirected, communities,
                                         weight="weight")
    return partition, modularity, undirected


def ei_index(graph, partition):
    """External-Internal index over edges: +1 all ties external, -1 all internal.

    More negative means groups talk mostly to themselves.

    Computed twice in this script, deliberately. Over Louvain communities it is
    partly circular, because Louvain *chooses* the partition that maximises
    internal density, so the value is bounded to be negative and mostly
    reflects how well the algorithm fit. Over home subreddits - a grouping
    fixed before any algorithm runs - it is not circular, and it is the version
    to lead with when answering RQ2.

    Edges where either user has no group are left out. Post authors who never
    commented have no home subreddit, and counting them as "external" would
    overstate cross-subreddit contact. With home subreddits as groups this
    makes E-I equal to 2 x cross-subreddit share - 1.
    """
    internal = external = 0
    for u, v, data in graph.edges(data=True):
        w = data.get("weight", 1)
        if partition.get(u) is None or partition.get(v) is None:
            continue
        if partition[u] == partition[v]:
            internal += w
        else:
            external += w
    total = internal + external
    return (external - internal) / total if total else float("nan")


def cross_subreddit_share(graph, homes):
    """Share of reply weight where the two users' home subreddits differ."""
    crossing = total = 0
    for u, v, data in graph.edges(data=True):
        hu, hv = homes.get(u), homes.get(v)
        if hu is None or hv is None:
            continue
        w = data.get("weight", 1)
        total += w
        if hu != hv:
            crossing += w
    return crossing / total if total else float("nan")


def subreddit_alignment(partition, homes):
    """How well detected communities line up with subreddit boundaries.

    If users cluster exactly by subreddit, the communities are just subreddits;
    if not, the separation is behavioural rather than structural.
    """
    rows = [{"user": u, "community": c, "subreddit": homes.get(u)}
            for u, c in partition.items() if homes.get(u)]
    df = pd.DataFrame(rows)
    if df.empty:
        return float("nan"), df
    try:
        from sklearn.metrics import normalized_mutual_info_score
        nmi = normalized_mutual_info_score(df["subreddit"], df["community"])
    except ImportError:
        nmi = float("nan")
    return nmi, df


def analyse(posts, comments, window_key):
    edges = build_reply_edges(posts, comments, window_key)
    graph = build_graph(edges)
    if graph.number_of_nodes() < 10:
        print(f"  {window_key}: too few nodes ({graph.number_of_nodes()}) - skipping")
        return None, None

    homes = home_subreddit(comments, window_key)
    partition, modularity, undirected = detect_communities(graph)

    sizes = pd.Series(partition).value_counts()
    big = sizes[sizes >= max(5, 0.01 * graph.number_of_nodes())]

    nmi, profile_rows = subreddit_alignment(partition, homes)

    print(f"    {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges, "
          f"{len(set(partition.values()))} communities, modularity {modularity:.3f}")

    largest_cc = max(nx.connected_components(undirected), key=len)
    degrees = dict(graph.degree())
    # Exact betweenness is O(nm) and hopeless at this size; k pivots give an
    # estimate good enough for ranking bridge users. Kept small deliberately:
    # the measure is used for node size in Gephi, not for a headline claim.
    print("    estimating betweenness ...")
    betweenness = nx.betweenness_centrality(
        graph, k=min(BETWEENNESS_PIVOTS, graph.number_of_nodes()), seed=42)

    nx.set_node_attributes(graph, partition, "community")
    nx.set_node_attributes(graph, homes, "home_subreddit")
    nx.set_node_attributes(graph, betweenness, "betweenness")
    os.makedirs(GEXF_DIR, exist_ok=True)
    nx.write_gexf(graph, f"{GEXF_DIR}/{window_key}.gexf")

    # Which subreddits feed each sizeable community
    profile = (profile_rows[profile_rows["community"].isin(big.index)]
               .groupby(["community", "subreddit"]).size()
               .rename("users").reset_index())
    profile["pct_of_community"] = (
        profile.groupby("community")["users"]
        .transform(lambda s: s / s.sum() * 100).round(1))
    profile = profile.sort_values(["community", "pct_of_community"],
                                  ascending=[True, False])
    profile.to_csv(f"{PROCESSED_DIR}/community_profile_{window_key}.csv", index=False)

    metrics = {
        "window": window_key,
        "label": WINDOWS[window_key]["label"],
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "density": round(nx.density(graph), 6),
        "reciprocity": round(nx.reciprocity(graph) or 0, 4),
        "largest_component_pct": round(len(largest_cc) / graph.number_of_nodes() * 100, 3),
        "communities_total": int(sizes.size),
        "communities_over_1pct": int(big.size),
        "modularity": round(modularity, 4),
        "ei_index_louvain": round(ei_index(graph, partition), 4),
        # The non-circular version: groups are subreddits, fixed in advance.
        "ei_index_by_subreddit": round(ei_index(graph, homes), 4),
        "pct_edges_crossing_subreddits": round(
            cross_subreddit_share(graph, homes) * 100, 2),
        "nmi_community_vs_subreddit": round(nmi, 4),
        "mean_degree": round(sum(degrees.values()) / len(degrees), 2),
        # Sampled: exact average clustering is too slow at this node count.
        "clustering": round(nx.average_clustering(
            undirected, nodes=list(undirected.nodes())[:5000]), 4),
    }
    return metrics, profile


def main():
    posts = pd.read_csv(f"{PROCESSED_DIR}/posts.csv")
    comments = pd.read_csv(f"{PROCESSED_DIR}/comments.csv", low_memory=False)

    rows = []
    for window_key in WINDOWS:
        print(f"Building network for {window_key} ...")
        metrics, _ = analyse(posts, comments, window_key)
        if metrics:
            rows.append(metrics)
            print("  " + ", ".join(f"{k}={v}" for k, v in metrics.items()
                                   if k not in ("window", "label")))

    if rows:
        table = pd.DataFrame(rows)
        table.to_csv(f"{PROCESSED_DIR}/network_metrics.csv", index=False)
        print("\n" + table.to_string(index=False))
        print(f"\nGEXF files for Gephi in {GEXF_DIR}/")


if __name__ == "__main__":
    main()
