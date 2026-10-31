"""Stage 1: collect raw posts and comments for both conflict windows.

Writes newline-delimited JSON to data/raw/, one file per subreddit per
window, plus a collection log recording what was fetched and what was
capped. Raw files are never edited afterwards; all cleaning happens in
02_clean.py, so the collection can be audited and re-run.

Usage:
    python 01_collect.py                 # both windows, all subreddits
    python 01_collect.py --window feb_2026
    python 01_collect.py --probe         # one day per window, for size checks
"""

import argparse
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arctic
from config import (CONCURRENCY, MAX_COMMENTS_PER_POST,
                    MIN_COMMENTS_TO_FETCH, RAW_DIR, SUBREDDITS, TOPIC_TERMS,
                    WINDOWS)

TOPIC_RE = re.compile("|".join(re.escape(t) for t in TOPIC_TERMS), re.I)

POST_FIELDS = ["id", "subreddit", "title", "selftext", "author", "created_utc",
               "score", "num_comments", "upvote_ratio", "url", "permalink",
               "domain", "is_self", "link_flair_text", "over_18", "locked",
               "removed_by_category"]

COMMENT_FIELDS = ["id", "subreddit", "link_id", "parent_id", "author", "body",
                  "created_utc", "score", "controversiality", "distinguished",
                  "is_submitter"]


def is_on_topic(post):
    """A post is in scope if it names Iran (or an Iran-specific referent).

    The same test is applied to every subreddit and both windows, so the
    sampling rule is identical across the comparison.
    """
    text = f"{post.get('title') or ''} {post.get('selftext') or ''}"
    return bool(TOPIC_RE.search(text))


def slim(record, fields):
    return {f: record.get(f) for f in fields}


def collect_window(window_key, probe=False):
    window = WINDOWS[window_key]
    start, end = window["start"], window["end"]
    if probe:  # single day, for feasibility checks
        end = (dt.date.fromisoformat(start) + dt.timedelta(days=1)).isoformat()

    os.makedirs(RAW_DIR, exist_ok=True)
    log = []

    for subreddit in SUBREDDITS:
        # Probe runs write to their own files: a one-day sample must never
        # overwrite a completed full-window collection.
        prefix = "probe_" if probe else ""
        posts_path = f"{RAW_DIR}/{prefix}posts_{window_key}_{subreddit}.jsonl"
        comments_path = f"{RAW_DIR}/{prefix}comments_{window_key}_{subreddit}.jsonl"
        # The marker is written only after both files are complete, so an
        # interrupted run is re-done rather than silently left half-collected.
        done_marker = f"{RAW_DIR}/.done_{window_key}_{subreddit}"
        if os.path.exists(done_marker) and not probe:
            print(f"  skip r/{subreddit} (already collected)")
            continue

        t0 = time.time()
        if os.path.exists(posts_path) and not probe:
            # Post scan already finished on an earlier run; only the comment
            # fetch below was interrupted, so do not pay for the scan again.
            with open(posts_path, encoding="utf-8") as f:
                kept = [json.loads(line) for line in f]
            scanned = -1  # unknown: the scan happened in a previous run
            print(f"  r/{subreddit}: reusing {len(kept)} posts already scanned")
        else:
            print(f"  r/{subreddit}: fetching posts {start} -> {end}")
            scanned = 0
            kept = []
            for post in arctic.search_posts(subreddit, start, end):
                scanned += 1
                if is_on_topic(post):
                    kept.append(slim(post, POST_FIELDS))

            with open(posts_path, "w", encoding="utf-8") as f:
                for post in kept:
                    f.write(json.dumps(post) + "\n")

        n_comments = 0
        n_capped = 0
        n_skipped = 0
        failures = []

        todo = [p for p in kept
                if (p.get("num_comments") or 0) >= MIN_COMMENTS_TO_FETCH]
        n_skipped = len(kept) - len(todo)

        def fetch_thread(post):
            """Returns (post_id, rows, error). Runs in a worker thread."""
            try:
                rows = [slim(c, COMMENT_FIELDS) for c in
                        arctic.search_comments_by_post(
                            post["id"], cap=MAX_COMMENTS_PER_POST)]
                return post["id"], rows, None
            except RuntimeError as exc:
                return post["id"], [], str(exc)[:200]

        # Most threads are small, so the run is dominated by per-request
        # latency rather than bandwidth; a few workers cut the wall time
        # substantially. Kept low, with backoff in arctic._get, to stay within
        # what the public archive tolerates.
        with open(comments_path, "w", encoding="utf-8") as f, \
                ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            done = 0
            for post_id, rows, error in pool.map(fetch_thread, todo):
                done += 1
                if error:
                    # One unreachable thread should not lose the whole run;
                    # record it so the loss is visible in the quality report.
                    failures.append({"post_id": post_id, "error": error})
                    print(f"    ! comments failed for {post_id}: {error[:80]}")
                for row in rows:
                    f.write(json.dumps(row) + "\n")
                n_comments += len(rows)
                if len(rows) >= MAX_COMMENTS_PER_POST:
                    n_capped += 1
                if done % 50 == 0:
                    f.flush()
                    print(f"    {done}/{len(todo)} threads, {n_comments} comments")

        entry = {
            "window": window_key, "subreddit": subreddit,
            "start": start, "end": end,
            "posts_scanned": scanned, "posts_kept": len(kept),
            "comments": n_comments, "posts_hitting_comment_cap": n_capped,
            "posts_below_comment_threshold": n_skipped,
            "comment_fetch_failures": len(failures),
            "seconds": round(time.time() - t0, 1),
        }
        log.append(entry)
        if not probe:
            with open(done_marker, "w", encoding="utf-8") as f:
                f.write(json.dumps(entry))
        print(f"    done: {entry['posts_kept']}/{scanned} posts, "
              f"{n_comments} comments in {entry['seconds']}s")

    log_path = f"{RAW_DIR}/collection_log_{window_key}.json"
    existing = []
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as f:
            existing = json.load(f)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(existing + log, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", choices=list(WINDOWS), default=None)
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()

    windows = [args.window] if args.window else list(WINDOWS)
    for window_key in windows:
        print(f"\n=== {WINDOWS[window_key]['label']} ===")
        collect_window(window_key, probe=args.probe)


if __name__ == "__main__":
    main()
