"""Stage 12: tidy, long-format CSVs for the Tableau Public dashboard.

The EDA figures (03_eda.py) are rendered straight to PNG and never saved as
data. This stage recomputes the same aggregates and writes them as CSVs that
Tableau can import directly, plus the already-computed comparison tables
reshaped into a tidy long format (metric/value rows) so they drop straight
into a single Tableau sheet without a calculated field.

Usage: CSMA_VARIANT=core python 12_tableau_export.py
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PROCESSED_DIR, SUBREDDITS, WINDOWS

OUT_DIR = "tableau"


def day_index(df, window_key):
    start = pd.Timestamp(WINDOWS[window_key]["start"])
    dates = pd.to_datetime(df["date"])
    return (dates - start).dt.days


def daily_volume(posts, comments):
    rows = []
    for key in WINDOWS:
        for df, metric in [(posts, "posts"), (comments, "comments")]:
            sub = df[df["window"] == key]
            if sub.empty:
                continue
            counts = day_index(sub, key).value_counts().sort_index()
            for day, n in counts.items():
                rows.append({"window": key, "label": WINDOWS[key]["label"],
                             "day": int(day), "metric": metric, "count": int(n)})
    return pd.DataFrame(rows)


def subreddit_share(comments):
    table = (comments.groupby(["window", "subreddit"]).size()
             .unstack(fill_value=0).reindex(columns=SUBREDDITS, fill_value=0))
    rows = []
    for key in WINDOWS:
        if key not in table.index:
            continue
        share = table.loc[key] / table.loc[key].sum() * 100
        for sub, pct in share.items():
            rows.append({"window": key, "label": WINDOWS[key]["label"],
                         "subreddit": sub, "comments": int(table.loc[key, sub]),
                         "pct_of_window": round(pct, 2)})
    return pd.DataFrame(rows)


def comment_length_hist(comments, bins=40, clip=1500):
    rows = []
    for key in WINDOWS:
        sub = comments[(comments["window"] == key) & (~comments["is_deleted"])]
        if sub.empty:
            continue
        counts, edges = pd.cut(sub["body_len"].clip(upper=clip), bins=bins,
                                retbins=True)
        dist = counts.value_counts(normalize=True, sort=False)
        for interval, density in dist.items():
            rows.append({"window": key, "label": WINDOWS[key]["label"],
                         "bin_start": round(interval.left, 1),
                         "bin_end": round(interval.right, 1),
                         "density": round(float(density), 6)})
    return pd.DataFrame(rows)


def domain_counts(posts, comments, window_key, top=15):
    from_posts = posts[(posts["window"] == window_key) & posts["is_external_link"]]
    counts = from_posts["link_domain"].value_counts()
    comment_rows = comments[comments["window"] == window_key]
    exploded = (comment_rows["domains"].str.split("|").explode()
                .replace("", pd.NA).dropna())
    exploded = exploded[~exploded.str.contains("redd.it|reddit.com", na=False)]
    counts = counts.add(exploded.value_counts(), fill_value=0)
    return counts.sort_values(ascending=False).head(top)


def top_domains(posts, comments):
    rows = []
    for key in WINDOWS:
        counts = domain_counts(posts, comments, key)
        for domain, n in counts.items():
            rows.append({"window": key, "label": WINDOWS[key]["label"],
                         "domain": domain, "times_shared": int(n)})
    return pd.DataFrame(rows)


def melt_metrics(path, id_cols=("window", "label")):
    df = pd.read_csv(path)
    return df.melt(id_vars=list(id_cols), var_name="metric", value_name="value")


def community_composition():
    rows = []
    for key in WINDOWS:
        p = f"{PROCESSED_DIR}/community_profile_{key}.csv"
        if not os.path.exists(p):
            continue
        df = pd.read_csv(p)
        df.insert(0, "window", key)
        df.insert(1, "label", WINDOWS[key]["label"])
        rows.append(df)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def robustness_runs():
    """Every subsample run, one row per metric, so spread can be plotted."""
    rows = []
    for file, kind in [("robustness_networks.csv", "reply network"),
                       ("robustness_sources.csv", "source sharing")]:
        df = pd.read_csv(f"{PROCESSED_DIR}/{file}")
        df = df[df["rep"].astype(str) != "full"]
        metrics = [c for c in ["modularity", "ei_index_louvain",
                               "ei_index_by_subreddit",
                               "mean_pairwise_source_overlap"] if c in df]
        long = df.melt(id_vars=["window", "rep"], value_vars=metrics,
                       var_name="metric", value_name="value")
        long.insert(0, "network", kind)
        rows.append(long)
    out = pd.concat(rows, ignore_index=True)
    out.insert(1, "label", out["window"].map(lambda k: WINDOWS[k]["label"]))
    return out


def source_overlap():
    """Pairwise subreddit source similarity as one row per pair, for a heatmap."""
    rows = []
    for key in WINDOWS:
        matrix = pd.read_csv(f"{PROCESSED_DIR}/source_overlap_{key}.csv")
        long = matrix.melt(id_vars="subreddit", var_name="other_subreddit",
                           value_name="overlap")
        long.insert(0, "window", key)
        long.insert(1, "label", WINDOWS[key]["label"])
        rows.append(long)
    return pd.concat(rows, ignore_index=True)


def subreddit_edges():
    """Replies between home subreddits, with each pair's share of the window."""
    rows = []
    for key in WINDOWS:
        df = pd.read_csv(f"{PROCESSED_DIR}/subreddit_edges_{key}.csv")
        df["pct_of_replies"] = df["replies"] / df["replies"].sum() * 100
        df.insert(0, "window", key)
        df.insert(1, "label", WINDOWS[key]["label"])
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    posts = pd.read_csv(f"{PROCESSED_DIR}/posts.csv")
    comments = pd.read_csv(f"{PROCESSED_DIR}/comments.csv", low_memory=False)
    comments["domains"] = comments["domains"].fillna("")

    daily_volume(posts, comments).to_csv(f"{OUT_DIR}/daily_volume.csv", index=False)
    subreddit_share(comments).to_csv(f"{OUT_DIR}/subreddit_share.csv", index=False)
    comment_length_hist(comments).to_csv(f"{OUT_DIR}/comment_length_hist.csv", index=False)
    top_domains(posts, comments).to_csv(f"{OUT_DIR}/top_domains.csv", index=False)
    community_composition().to_csv(f"{OUT_DIR}/community_composition.csv", index=False)

    melt_metrics(f"{PROCESSED_DIR}/network_metrics.csv").to_csv(
        f"{OUT_DIR}/network_metrics_long.csv", index=False)
    melt_metrics(f"{PROCESSED_DIR}/source_metrics.csv").to_csv(
        f"{OUT_DIR}/source_metrics_long.csv", index=False)

    robustness_runs().to_csv(f"{OUT_DIR}/robustness_runs.csv", index=False)
    source_overlap().to_csv(f"{OUT_DIR}/source_overlap.csv", index=False)
    subreddit_edges().to_csv(f"{OUT_DIR}/subreddit_edges.csv", index=False)

    import shutil
    shutil.copy(f"{PROCESSED_DIR}/cross_community_summary.csv", f"{OUT_DIR}/cross_community_summary.csv")
    shutil.copy(f"{PROCESSED_DIR}/network_metrics.csv", f"{OUT_DIR}/network_metrics_wide.csv")

    print(f"Wrote Tableau-ready CSVs to {OUT_DIR}/")
    for f in sorted(os.listdir(OUT_DIR)):
        print(" ", f)


if __name__ == "__main__":
    main()
