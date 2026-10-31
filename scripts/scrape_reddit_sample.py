"""
Sample Reddit dataset collector for CSMA Project Phase 1 demo.

Uses Reddit's public, unauthenticated JSON endpoints (no API credentials
required) to pull a small sample of posts + top-level comments from the
target subreddits, for both conflict periods. Intended as a feasibility
demo dataset, not the full Phase 2 collection (which will use PRAW +
proper API credentials for larger-scale, rate-limit-friendly collection).
"""

import csv
import time
import requests

HEADERS = {"User-Agent": "csma-project-demo/0.1 by academic-research"}

SUBREDDITS = ["geopolitics", "worldnews", "Iran", "Israel"]

QUERIES = {
    "june_2025_strikes": "Iran strike OR Iran nuclear OR Iran attack",
    "feb_2026_strikes": "Iran Israel strike OR Iran Israel attack",
}

POSTS_PER_QUERY = 25


def search_subreddit(subreddit, query, limit=25):
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": query,
        "restrict_sr": 1,
        "sort": "relevance",
        "limit": limit,
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()["data"]["children"]


def get_top_comments(subreddit, post_id, limit=5):
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
    params = {"limit": limit, "depth": 1}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if len(data) < 2:
        return []
    comments = []
    for child in data[1]["data"]["children"]:
        if child["kind"] != "t1":
            continue
        c = child["data"]
        comments.append(c)
    return comments


def main():
    posts_rows = []
    comments_rows = []

    for period_label, query in QUERIES.items():
        for subreddit in SUBREDDITS:
            print(f"Fetching r/{subreddit} for period={period_label} ...")
            try:
                children = search_subreddit(subreddit, query, POSTS_PER_QUERY)
            except Exception as e:
                print(f"  failed: {e}")
                continue

            for child in children:
                if child["kind"] != "t3":
                    continue
                p = child["data"]
                posts_rows.append({
                    "period": period_label,
                    "subreddit": p.get("subreddit"),
                    "post_id": p.get("id"),
                    "title": p.get("title"),
                    "selftext": (p.get("selftext") or "")[:500],
                    "author": p.get("author"),
                    "created_utc": p.get("created_utc"),
                    "score": p.get("score"),
                    "num_comments": p.get("num_comments"),
                    "url": p.get("url"),
                    "permalink": "https://www.reddit.com" + p.get("permalink", ""),
                })

                time.sleep(1)
                try:
                    comments = get_top_comments(subreddit, p.get("id"))
                except Exception as e:
                    print(f"  comment fetch failed for {p.get('id')}: {e}")
                    comments = []

                for c in comments:
                    comments_rows.append({
                        "period": period_label,
                        "subreddit": subreddit,
                        "post_id": p.get("id"),
                        "comment_id": c.get("id"),
                        "parent_id": c.get("parent_id"),
                        "author": c.get("author"),
                        "body": (c.get("body") or "")[:500],
                        "created_utc": c.get("created_utc"),
                        "score": c.get("score"),
                    })

                time.sleep(1)

    with open("data/sample_posts.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(posts_rows[0].keys()))
        writer.writeheader()
        writer.writerows(posts_rows)

    if comments_rows:
        with open("data/sample_comments.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(comments_rows[0].keys()))
            writer.writeheader()
            writer.writerows(comments_rows)

    print(f"\nDone. {len(posts_rows)} posts, {len(comments_rows)} comments saved to data/")


if __name__ == "__main__":
    main()
