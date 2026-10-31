"""Stage 11: small, laptop-friendly networks for the demo and the report figures.

The full reply networks (100k+ nodes) are the basis for every statistic, but
they are too large to draw on a laptop. This stage builds two smaller views
from the same core networks:

  communities_<window>.gexf  one node per detected community (about 15-20
                             sizeable ones), edges weighted by how many replies
                             cross between them. Readable at a glance.
  sample_<window>.gexf       a few hundred to a couple of thousand of the most
                             active users, taken from every sizeable community
                             in proportion to its size, keeping the reply edges
                             among them. Looks like the classic Gephi pictures.

Both are illustrations. The numbers in the report come from the full network.

Usage: CSMA_VARIANT=core python 11_demo_networks.py
"""

import os
import sys

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FIG_DIR, WINDOWS

OUT_DIR = f"{FIG_DIR}/demo"
SAMPLE_SIZE = 1500
MIN_COMMUNITY_SHARE = 0.01


def load(window_key):
    return nx.read_gexf(f"{FIG_DIR}/networks/{window_key}.gexf")


def community_graph(graph, window_key):
    members = {}
    for node, data in graph.nodes(data=True):
        members.setdefault(data["community"], []).append(node)
    total = graph.number_of_nodes()
    big = {c: m for c, m in members.items() if len(m) >= MIN_COMMUNITY_SHARE * total}

    label_of = {}
    cg = nx.DiGraph()
    for c, nodes in big.items():
        subs = {}
        for n in nodes:
            s = graph.nodes[n].get("home_subreddit", "unknown")
            subs[s] = subs.get(s, 0) + 1
        top = max(subs, key=subs.get)
        share = subs[top] / len(nodes) * 100
        label = f"{top} ({share:.0f}%)"
        label_of[c] = label
        cg.add_node(str(c), label=label, users=len(nodes), dominant_subreddit=top)

    for u, v, data in graph.edges(data=True):
        cu, cv = graph.nodes[u]["community"], graph.nodes[v]["community"]
        if cu == cv or cu not in big or cv not in big:
            continue
        a, b = str(cu), str(cv)
        w = data.get("weight", 1)
        if cg.has_edge(a, b):
            cg[a][b]["weight"] += w
        else:
            cg.add_edge(a, b, weight=w)
    return cg


def sample_graph(graph):
    members = {}
    for node, data in graph.nodes(data=True):
        members.setdefault(data["community"], []).append(node)
    total = graph.number_of_nodes()
    keep = []
    for c, nodes in members.items():
        if len(nodes) < MIN_COMMUNITY_SHARE * total:
            continue
        quota = max(1, round(SAMPLE_SIZE * len(nodes) / total))
        nodes.sort(key=lambda n: graph.degree(n), reverse=True)
        keep.extend(nodes[:quota])
    sub = graph.subgraph(keep).copy()
    sub.remove_nodes_from([n for n in list(sub.nodes) if sub.degree(n) == 0])
    return sub


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for window_key in WINDOWS:
        graph = load(window_key)
        cg = community_graph(graph, window_key)
        nx.write_gexf(cg, f"{OUT_DIR}/communities_{window_key}.gexf")
        print(f"{window_key}: community graph {cg.number_of_nodes()} nodes, "
              f"{cg.number_of_edges()} edges")

        sg = sample_graph(graph)
        nx.write_gexf(sg, f"{OUT_DIR}/sample_{window_key}.gexf")
        print(f"{window_key}: sample graph {sg.number_of_nodes()} nodes, "
              f"{sg.number_of_edges()} edges")


if __name__ == "__main__":
    main()
