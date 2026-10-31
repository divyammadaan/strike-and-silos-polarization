"""Thin client for the Arctic Shift Reddit archive API.

Arctic Shift serves the public Reddit archive dumps over HTTP. We use it
instead of PRAW because the Reddit API cannot search by date and stops at
about 1000 results per listing, which makes it unusable for reconstructing a
past three-week window.
"""

import time
import requests

from config import API_BASE, REQUEST_SLEEP

_session = requests.Session()
_session.headers.update({"User-Agent": "csma-cse3729-academic-project/1.0"})

PAGE_LIMIT = 100  # API maximum


# Arctic Shift answers an overloaded/rate-limited request with 422 and the
# body "Timeout. Maybe slow down a bit", so 422 is retryable here even though
# it normally means a malformed request.
RETRY_STATUS = (422, 429, 500, 502, 503, 504)


def _get(path, params, retries=6):
    """GET with exponential backoff; Arctic Shift rate-limits under load."""
    last = None
    for attempt in range(retries):
        try:
            resp = _session.get(API_BASE + path, params=params, timeout=120)
        except requests.RequestException as exc:  # transient network problem
            last = str(exc)
            time.sleep(2 ** attempt)
            continue
        if resp.status_code == 200:
            return resp.json()["data"]
        last = f"{resp.status_code}: {resp.text[:150]}"
        if resp.status_code in RETRY_STATUS:
            time.sleep(2 ** attempt)
            continue
        raise RuntimeError(f"{path} -> {last}")
    raise RuntimeError(f"{path} failed after {retries} attempts ({last})")


def paginate(path, params, cap=None):
    """Yield every record for a query, walking forward through created_utc.

    The API returns at most 100 records sorted ascending by creation time, so
    we page by moving `after` to the last record we saw.
    """
    params = dict(params)
    params["limit"] = PAGE_LIMIT
    params.setdefault("sort", "asc")
    seen = set()
    fetched = 0

    while True:
        batch = _get(path, params)
        if not batch:
            return

        new = [r for r in batch if r["id"] not in seen]
        for record in new:
            seen.add(record["id"])
            yield record
            fetched += 1
            if cap and fetched >= cap:
                return

        if len(batch) < PAGE_LIMIT:
            return

        last_ts = batch[-1]["created_utc"]
        # +1s would skip records sharing the timestamp; the `seen` set above
        # is what actually protects against duplicates, so step by 0.
        params["after"] = int(last_ts)
        if not new:  # every record in the page was already seen: we are stuck
            params["after"] = int(last_ts) + 1
        time.sleep(REQUEST_SLEEP)


def search_posts(subreddit, after, before, cap=None):
    return paginate("/posts/search",
                    {"subreddit": subreddit, "after": after, "before": before},
                    cap=cap)


def search_comments_by_post(link_id, cap=None):
    return paginate("/comments/search", {"link_id": link_id}, cap=cap)


def count_posts(subreddit, after, before):
    """Cheap-ish size probe: counts by paging, used for the feasibility check."""
    return sum(1 for _ in search_posts(subreddit, after, before))
