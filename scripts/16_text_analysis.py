"""Stage 16: computational text analysis of every comment (RQ4).

Two methods, both applied to all cleaned comments rather than a sample:

  1. Dictionary frames. Each comment is checked against a word list per frame
     (the frames in qualitative/codebook.csv). A comment can mention several
     frames or none. Gives the share of comments mentioning each frame, per
     window and subreddit.
  2. Topic model. NMF on TF-IDF vectors, one document per thread (title plus
     all its comments). Finds themes without a predefined list, as a check on
     method 1.

Comments in one thread are not independent, so uncertainty comes from a
bootstrap that resamples whole threads. Narrative similarity between
subreddits is the mean pairwise cosine similarity of their frame profiles, the
same measure stage 5 uses for sources.

Word lists show what is talked about, not which side a comment takes.

Usage: python 16_text_analysis.py          (CSMA_VARIANT=core for core)
"""

import itertools
import os
import re
import sys

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PROCESSED_DIR, SUBREDDITS, VARIANT, WINDOWS

REPORT = ("reports/text_analysis.md" if VARIANT == "full"
          else "reports/core/text_analysis.md")
BOOTSTRAP = 1000
N_TOPICS = 10
SEED = 42

# Whole words or phrases; a trailing * also matches longer endings. "Iran" is
# left out on purpose: every thread was collected for mentioning it.
FRAMES = {
    "Military events": """strike* airstrike* attack* missile* drone* bomb* troops
        soldier* military army navy airforce intercept* retaliat* escalat*
        casualt* war warfare weapon* carrier* invasion""",
    "Diplomacy and ceasefire": """ceasefire* "cease fire" negotiat* diplomat*
        diplomacy "peace deal" "peace talks" talks treaty ally allies nato
        "united nations" sanctions mediat*""",
    "US domestic politics": """trump maga republican* democrat* gop congress
        senate senator* election* vote voter* voting biden harris obama
        impeach* "white house" hegseth vance rubio liberal* conservative*""",
    "Legitimacy and morality": """"war crime" "war crimes" illegal unlawful
        legal justified unjustified moral* immoral civilian* innocent* genocide
        "international law" constitution* hypocri* children murder*""",
    "Iranian regime and people": """regime khamenei ayatollah mullah* irgc
        "islamic republic" protest* protester* "iranian people" "people of iran"
        dictator* oppress* "regime change" pahlavi shah diaspora""",
    "Israel and regional conflict": """israel* idf netanyahu bibi gaza hamas
        hezbollah houthi* palestin* zionis* saudi* lebanon qatar syria iraq""",
    "Economy and energy": """oil "gas price" "gas prices" hormuz econom* market*
        inflation tanker* shipping recession tariff* "cost of living" dollar*""",
    "Nuclear programme": """nuclear nuke* uranium enrich* fordow natanz
        centrifuge* iaea "nuclear weapon" warhead*""",
    "Media and information": """media news propaganda misinformation
        disinformation fake bots "fox news" cnn bbc journalist* "source"
        censor* narrative*""",
}

EXTRA_STOP = ["like", "just", "dont", "don", "im", "people", "think", "know",
              "going", "really", "even", "also", "would", "one", "get", "got",
              "say", "said", "thing", "things", "way", "yeah", "lol", "https",
              "http", "www", "com", "amp", "gt", "re", "ve", "ll", "isn",
              "doesn", "didn", "removed", "deleted", "reddit", "iran", "iranian",
              "iranians", "make", "want", "time", "good", "right", "ll"]


def pattern(words):
    parts = []
    for token in re.findall(r'"[^"]+"|\S+', words):
        token = token.strip('"')
        stem = token.endswith("*")
        body = re.escape(token.rstrip("*")).replace(r"\ ", r"\s+")
        parts.append(body + (r"\w*" if stem else ""))
    return r"\b(?:" + "|".join(parts) + r")\b"


def load():
    comments = pd.read_csv(
        f"{PROCESSED_DIR}/comments.csv",
        usecols=["post_id", "window", "subreddit", "body", "is_deleted"])
    comments = comments[~comments["is_deleted"] & comments["body"].notna()]
    text = comments["body"].str.lower()
    text = text.str.replace(r"https?://\S+", " ", regex=True)
    return comments.assign(text=text.str.replace("’", "'", regex=False))


def frame_flags(comments):
    return pd.DataFrame(
        {name: comments["text"].str.contains(pattern(words), regex=True)
         for name, words in FRAMES.items()}, index=comments.index)


def bootstrap_shares(per_thread, rng):
    """(share, low, high) in % per frame, resampling whole threads."""
    hits = per_thread[list(FRAMES)].to_numpy(float)
    sizes = per_thread["n"].to_numpy(float)
    draws = rng.integers(0, len(sizes), (BOOTSTRAP, len(sizes)))
    boot = np.array([hits[d].sum(0) / sizes[d].sum() for d in draws]) * 100
    point = hits.sum(0) / sizes.sum() * 100
    return point, np.percentile(boot, 2.5, axis=0), np.percentile(boot, 97.5, axis=0), boot


def similarity(profiles):
    unit = profiles / np.linalg.norm(profiles, axis=1, keepdims=True)
    return float(np.mean([unit[i] @ unit[j] for i, j in
                          itertools.combinations(range(len(unit)), 2)]))


def similarity_interval(per_thread, rng):
    """Mean pairwise cosine between subreddit frame profiles, with 95% CI."""
    groups = [(g[list(FRAMES)].to_numpy(float), g["n"].to_numpy(float))
              for _, g in per_thread.groupby("subreddit")]
    point = similarity(np.array([h.sum(0) / n.sum() for h, n in groups]))
    boot = []
    for _ in range(BOOTSTRAP):
        rows = []
        for hits, sizes in groups:
            d = rng.integers(0, len(sizes), len(sizes))
            rows.append(hits[d].sum(0) / sizes[d].sum())
        boot.append(similarity(np.array(rows)))
    return point, np.percentile(boot, 2.5), np.percentile(boot, 97.5)


def topic_model(comments):
    posts = pd.read_csv(f"{PROCESSED_DIR}/posts.csv", usecols=["id", "title"])
    docs = comments.groupby(["window", "post_id"])["text"].agg(" ".join).reset_index()
    docs = docs.merge(posts, left_on="post_id", right_on="id", how="left")
    docs["text"] = docs["title"].fillna("").str.lower() + " " + docs["text"]
    vectoriser = TfidfVectorizer(
        stop_words=list(ENGLISH_STOP_WORDS.union(EXTRA_STOP)), min_df=10,
        max_df=0.6, max_features=15000, sublinear_tf=True,
        token_pattern=r"(?u)\b[a-z][a-z]{2,}\b")
    matrix = vectoriser.fit_transform(docs["text"])
    model = NMF(n_components=N_TOPICS, init="nndsvd", random_state=SEED, max_iter=2000)
    weights = model.fit_transform(matrix)
    terms = vectoriser.get_feature_names_out()
    docs["topic"] = weights.argmax(1) + 1
    words = [", ".join(terms[i] for i in row.argsort()[::-1][:10])
             for row in model.components_]
    sizes = comments.groupby(["window", "post_id"]).size().rename("n").reset_index()
    docs = docs.merge(sizes, on=["window", "post_id"])
    share = docs.pivot_table(index="topic", columns="window", values="n",
                             aggfunc="sum", fill_value=0)
    share = (share / share.sum() * 100).round(1).reindex(columns=list(WINDOWS))
    table = share.reset_index()
    table.insert(1, "top_words", [words[t - 1] for t in table["topic"]])
    return table, len(docs)


def main():
    rng = np.random.default_rng(SEED)
    comments = load()
    flags = frame_flags(comments)
    data = pd.concat([comments[["window", "subreddit", "post_id"]], flags], axis=1)
    per_thread = data.groupby(["window", "subreddit", "post_id"])[list(FRAMES)].sum()
    per_thread["n"] = data.groupby(["window", "subreddit", "post_id"]).size()
    per_thread = per_thread.reset_index()
    june, feb = list(WINDOWS)

    stats = {w: bootstrap_shares(per_thread[per_thread["window"] == w], rng)
             for w in WINDOWS}
    diff = stats[feb][3] - stats[june][3]
    rows = []
    for i, frame in enumerate(FRAMES):
        low, high = np.percentile(diff[:, i], [2.5, 97.5])
        rows.append({
            "frame": frame,
            "june_pct": round(stats[june][0][i], 1),
            "june_95ci": f"{stats[june][1][i]:.1f} to {stats[june][2][i]:.1f}",
            "feb_pct": round(stats[feb][0][i], 1),
            "feb_95ci": f"{stats[feb][1][i]:.1f} to {stats[feb][2][i]:.1f}",
            "change_points": round(stats[feb][0][i] - stats[june][0][i], 1),
            "clear_change": "yes" if low > 0 or high < 0 else "no"})
    overall = pd.DataFrame(rows).sort_values("june_pct", ascending=False)

    by_sub = (data.groupby(["window", "subreddit"])[list(FRAMES)].mean() * 100)
    long = by_sub.stack().rename("pct_of_comments").reset_index()
    long.columns = ["window", "subreddit", "frame", "pct_of_comments"]

    sims = []
    for window in WINDOWS:
        point, low, high = similarity_interval(
            per_thread[per_thread["window"] == window], rng)
        sims.append({"window": window, "frame_similarity": round(point, 3),
                     "95ci": f"{low:.3f} to {high:.3f}"})

    topics, n_docs = topic_model(comments)

    counts = comments.groupby("window").size()
    covered = flags.any(axis=1).groupby(comments["window"]).mean() * 100
    lines = [
        f"# RQ4: text analysis of all comments ({VARIANT} dataset)", "",
        f"Comments analysed: {len(comments):,} "
        f"({june}: {counts[june]:,}; {feb}: {counts[feb]:,}), "
        f"in {n_docs:,} threads. Deleted and removed comments are excluded.", "",
        f"Comments mentioning at least one frame: {june} {covered[june]:.1f}%, "
        f"{feb} {covered[feb]:.1f}%.", "",
        "## Frames mentioned (% of comments)", "",
        "A comment can count for several frames. Intervals come from "
        f"{BOOTSTRAP} bootstrap resamples of whole threads; a change is "
        "'clear' when the 95% interval of the difference excludes zero. With "
        "nine frames compared, treat marginal ones with caution.", "",
        overall.to_markdown(index=False), "",
        "## Narrative similarity between subreddits", "",
        "Mean pairwise cosine similarity of the subreddits' frame profiles "
        "(1 = identical mix of frames).", "",
        pd.DataFrame(sims).to_markdown(index=False), "",
    ]
    for window in WINDOWS:
        table = by_sub.loc[window].reindex(SUBREDDITS).round(1).T
        lines += [f"## Frames by subreddit: {window} (% of comments)", "",
                  table.to_markdown(), ""]
    lines += [
        "## Topic model (NMF, one document per thread)", "",
        "Share of each window's comments in threads whose strongest topic is "
        "this one. Topics are numbered, not named: name them from their words.", "",
        topics.to_markdown(index=False), "",
        "## Word lists", "",
        *[f"- **{name}:** {' '.join(words.split())}" for name, words in FRAMES.items()],
        "",
    ]
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    if VARIANT == "full":
        os.makedirs("tableau", exist_ok=True)
        long.to_csv("tableau/text_frames_by_subreddit.csv", index=False)
        pd.concat([overall[["frame", f"{key}_pct"]]
                   .set_axis(["frame", "pct_of_comments"], axis=1)
                   .assign(window=window)
                   for key, window in [("june", june), ("feb", feb)]]
                  ).to_csv("tableau/text_frames_overall.csv", index=False)
    print("\n".join(lines[:lines.index("## Word lists")]))
    print(f"\nWrote {REPORT}")


if __name__ == "__main__":
    main()
