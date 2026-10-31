"""Stage 2: clean the raw JSONL into two analysis tables.

Outputs data/processed/posts.csv and comments.csv plus a data-quality report
(data/processed/quality_report.json) that records exactly what was dropped and
why. The quality numbers feed the "data understanding" section of the report,
and the ethics of the pipeline (pseudonymised authors) are handled here.

Usage: python 02_clean.py
"""

import glob
import hashlib
import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (MIN_COMMENTS_TO_FETCH, PROCESSED_DIR, RAW_DIR, SUBREDDITS,
                    WINDOWS)

# Reddit returns the subreddit name with whatever casing the record was stored
# with ("iran" and "Iran" both occur), which would otherwise split one
# community into two categories in every groupby downstream.
CANONICAL_SUB = {s.lower(): s for s in SUBREDDITS}


def canonical_subreddit(name):
    if not isinstance(name, str):
        return name
    return CANONICAL_SUB.get(name.lower(), name)

# Salt for pseudonymising usernames. Authors are replaced by a salted hash so
# that reply networks can still be built while individual Reddit accounts are
# not identifiable in the shared dataset or repository.
SALT = "cse3729-csma-2026"

DELETED_MARKERS = {"[deleted]", "[removed]", ""}

# Automated accounts contribute edges that are not human interaction.
BOT_PATTERN = re.compile(
    r"(^|[-_])bot([-_]|$)|automoderator|^b0t|remindme|sneakpeekbot|auto_?mod",
    re.I)

URL_RE = re.compile(r"https?://[^\s\)\]\>\"]+")
TRACKING_PARAM_RE = re.compile(r"[?&](utm_[^=]+|fbclid|gclid|ref|ref_src)=[^&]*")


def pseudonymise(author):
    if not author or author in DELETED_MARKERS:
        return None
    return "u_" + hashlib.sha256((SALT + author.lower()).encode()).hexdigest()[:12]


# Different hostnames that are the same publisher. Without this, the mobile
# and desktop forms of one source count as two separate sources, which inflates
# the domain count and distorts every source-overlap measure in RQ3.
DOMAIN_ALIASES = {
    "youtu.be": "youtube.com",
    "m.youtube.com": "youtube.com",
    "np.reddit.com": "reddit.com",
    "old.reddit.com": "reddit.com",
    "new.reddit.com": "reddit.com",
    "amp.cnn.com": "cnn.com",
    "edition.cnn.com": "cnn.com",
}


def extract_domain(url):
    """Registered-ish domain of a URL, used for the source-sharing network."""
    if not url:
        return None
    match = re.match(r"https?://([^/]+)", url)
    if not match:
        return None
    host = match.group(1).lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    # "en.m.wikipedia.org" -> "en.wikipedia.org", "m.bbc.com" -> "bbc.com"
    host = re.sub(r"^m\.", "", host)
    host = re.sub(r"\.m\.", ".", host)
    host = re.sub(r"^amp\.", "", host)
    host = DOMAIN_ALIASES.get(host, host)
    return host or None


def extract_urls(text):
    if not text:
        return []
    urls = []
    for raw in URL_RE.findall(text):
        raw = raw.rstrip(".,;:'\"")
        urls.append(TRACKING_PARAM_RE.sub("", raw))
    return urls


def load_jsonl(pattern):
    rows = []
    for path in sorted(glob.glob(pattern)):
        window = os.path.basename(path).split("_")[1:3]
        window_key = "_".join(window)
        with open(path, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                record["window"] = window_key
                rows.append(record)
    return pd.DataFrame(rows)


def clean_posts(df, quality):
    quality["posts_raw"] = len(df)
    df["subreddit"] = df["subreddit"].map(canonical_subreddit)

    df = df.drop_duplicates(subset="id").copy()
    quality["posts_after_dedup"] = len(df)

    df["created_dt"] = pd.to_datetime(df["created_utc"], unit="s", utc=True)
    df["date"] = df["created_dt"].dt.date.astype(str)

    # Verify every post really falls inside its declared window. This is the
    # check that the Phase 1 sample failed.
    in_window = pd.Series(False, index=df.index)
    for key, window in WINDOWS.items():
        mask = (df["window"] == key)
        in_window |= mask & (df["date"] >= window["start"]) & (df["date"] < window["end"])
    quality["posts_outside_declared_window"] = int((~in_window).sum())
    df = df[in_window]

    df["author_hash"] = df["author"].map(pseudonymise)
    quality["posts_deleted_author"] = int(df["author_hash"].isna().sum())

    df["is_bot"] = df["author"].fillna("").map(lambda a: bool(BOT_PATTERN.search(a)))
    quality["posts_by_bots"] = int(df["is_bot"].sum())
    df = df[~df["is_bot"]]

    df["removed"] = df["removed_by_category"].notna()
    quality["posts_removed_by_mods"] = int(df["removed"].sum())

    # Apply the thread-size rule here as well as in collection, so that every
    # window obeys the same rule even if an earlier collection run used a
    # different threshold.
    small = df["num_comments"].fillna(0) < MIN_COMMENTS_TO_FETCH
    quality["posts_below_thread_size_threshold"] = int(small.sum())
    quality["thread_size_threshold"] = MIN_COMMENTS_TO_FETCH
    df = df[~small]

    df["text"] = (df["title"].fillna("") + " " + df["selftext"].fillna("")).str.strip()
    df["text_len"] = df["text"].str.len()

    # A post's own outbound link (link posts) is the primary shared source.
    df["link_domain"] = df["url"].map(extract_domain)
    self_hosts = {"reddit.com", "old.reddit.com", "i.redd.it", "v.redd.it",
                  "redd.it", "self." + "reddit.com"}
    df["is_external_link"] = df["link_domain"].notna() & ~df["link_domain"].isin(self_hosts)
    quality["posts_with_external_link"] = int(df["is_external_link"].sum())

    df = df.drop(columns=["author", "is_bot"])  # raw usernames never persisted
    quality["posts_final"] = len(df)
    return df


def clean_comments(df, valid_post_ids, quality):
    quality["comments_raw"] = len(df)
    df["subreddit"] = df["subreddit"].map(canonical_subreddit)

    df = df.drop_duplicates(subset="id").copy()
    quality["comments_after_dedup"] = len(df)

    # link_id / parent_id arrive as "t3_abc" (post) or "t1_abc" (comment).
    df["post_id"] = df["link_id"].str.replace("^t3_", "", regex=True)
    df["parent_kind"] = df["parent_id"].str[:2]
    df["parent_ref"] = df["parent_id"].str.replace("^t[0-9]_", "", regex=True)

    orphans = ~df["post_id"].isin(valid_post_ids)
    quality["comments_without_kept_post"] = int(orphans.sum())
    df = df[~orphans]

    df["created_dt"] = pd.to_datetime(df["created_utc"], unit="s", utc=True)
    df["date"] = df["created_dt"].dt.date.astype(str)

    # Restrict comments to the observation window by their OWN timestamp, not
    # their post's. A thread started on the last day of the window keeps
    # attracting replies for months, and June 2025 has had far longer to
    # accumulate them than February 2026 - so without this filter the older
    # window is credited with extra late activity and the two are not
    # comparable.
    in_window = pd.Series(False, index=df.index)
    for key, window in WINDOWS.items():
        mask = (df["window"] == key)
        in_window |= mask & (df["date"] >= window["start"]) & (df["date"] < window["end"])
    quality["comments_after_window_close"] = int((~in_window).sum())
    df = df[in_window]

    df["is_deleted"] = df["body"].fillna("").isin(DELETED_MARKERS)
    quality["comments_deleted_or_removed"] = int(df["is_deleted"].sum())

    df["author_hash"] = df["author"].map(pseudonymise)
    quality["comments_deleted_author"] = int(df["author_hash"].isna().sum())

    df["is_bot"] = df["author"].fillna("").map(lambda a: bool(BOT_PATTERN.search(a)))
    quality["comments_by_bots"] = int(df["is_bot"].sum())
    df = df[~df["is_bot"]]

    df["body_len"] = df["body"].fillna("").str.len()
    df["urls"] = df["body"].map(extract_urls)
    df["domains"] = df["urls"].map(lambda us: [d for d in (extract_domain(u) for u in us) if d])
    df["n_links"] = df["domains"].map(len)
    quality["comments_with_link"] = int((df["n_links"] > 0).sum())

    df["is_top_level"] = df["parent_kind"] == "t3"
    quality["comments_top_level"] = int(df["is_top_level"].sum())
    quality["comments_nested_replies"] = int((~df["is_top_level"]).sum())

    df = df.drop(columns=["author", "is_bot"])
    quality["comments_final"] = len(df)
    return df


def main():
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    quality = {}

    posts = load_jsonl(f"{RAW_DIR}/posts_*.jsonl")
    comments = load_jsonl(f"{RAW_DIR}/comments_*.jsonl")
    if posts.empty:
        raise SystemExit("No raw posts found - run 01_collect.py first.")

    posts = clean_posts(posts, quality)
    comments = clean_comments(comments, set(posts["id"]), quality)

    # Per-window summary for the progress report.
    quality["by_window"] = {
        key: {
            "posts": int((posts["window"] == key).sum()),
            "comments": int((comments["window"] == key).sum()),
            "unique_post_authors": int(posts.loc[posts["window"] == key, "author_hash"].nunique()),
            "unique_comment_authors": int(comments.loc[comments["window"] == key, "author_hash"].nunique()),
            "subreddits": int(posts.loc[posts["window"] == key, "subreddit"].nunique()),
        }
        for key in WINDOWS
    }

    posts.to_csv(f"{PROCESSED_DIR}/posts.csv", index=False)
    # Lists do not survive CSV round-trips cleanly; store domains as a string.
    out = comments.copy()
    out["domains"] = out["domains"].map(lambda ds: "|".join(ds))
    out = out.drop(columns=["urls"])
    out.to_csv(f"{PROCESSED_DIR}/comments.csv", index=False)

    with open(f"{PROCESSED_DIR}/quality_report.json", "w", encoding="utf-8") as f:
        json.dump(quality, f, indent=2)

    print(json.dumps(quality, indent=2))


if __name__ == "__main__":
    main()
