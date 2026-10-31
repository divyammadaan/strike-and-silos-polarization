"""Stage 14: tabulate the qualitative codes (RQ4) and check them.

All sampled threads are coded with AI assistance (qualitative/ai_codes.csv).
Team members independently code the same random subset, without seeing the AI
labels, in qualitative/check_sheet_<coder>.xlsx. This stage tabulates the AI
codes, reports how far each completed check agrees with them (percent agreement
and Cohen's kappa) and how far the team members agree with each other.

Every output states how many team checks are complete, so unchecked labels
cannot be mistaken for checked ones. A sheet counts only once every thread in
it has a primary_frame, stance_on_strikes and tone.

Usage: python 14_qualitative_summary.py
"""

import glob
import itertools
import os
from collections import Counter

import openpyxl
import pandas as pd
from sklearn.metrics import cohen_kappa_score

DIR = "qualitative"
FIELDS = ["primary_frame", "stance_on_strikes", "tone"]
REPORT = "reports/qualitative_summary.md"
TABLEAU = "tableau/qualitative_codes.csv"
WINDOW_ORDER = ["june_2025", "feb_2026"]


def read_check(path):
    book = openpyxl.load_workbook(path, read_only=True)
    rows = book["coding"].values
    header = next(rows)
    df = pd.DataFrame(rows, columns=header)
    book.close()
    for field in FIELDS:
        df[field] = df[field].fillna("").astype(str).str.strip()
    return df[["thread_id", *FIELDS]]


def load_checks(directory, sample_ids):
    """(completed {coder: codes}, {coder: threads done} for unfinished sheets)."""
    done, unfinished = {}, {}
    for path in sorted(glob.glob(f"{directory}/check_sheet_*.xlsx")):
        coder = os.path.basename(path)[len("check_sheet_"):-len(".xlsx")]
        df = read_check(path)
        filled = df[(df[FIELDS] != "").all(axis=1)]
        if set(filled["thread_id"]) >= sample_ids:
            done[coder] = filled.set_index("thread_id")
        elif len(filled) or (df[FIELDS] != "").any().any():
            unfinished[coder] = len(filled)
    return done, unfinished


def compare(a, b):
    """Agreement between two code tables indexed by thread id."""
    ids = a.index.intersection(b.index)
    rows = []
    for field in FIELDS:
        x, y = a.loc[ids, field], b.loc[ids, field]
        # Kappa is undefined when both coders use one and the same single label.
        constant = len(set(x) | set(y)) < 2
        rows.append({
            "field": field, "threads": len(ids),
            "percent_agreement": round((x == y).mean() * 100, 1),
            "cohens_kappa": "n/a" if constant
            else round(cohen_kappa_score(x, y), 2)})
    return pd.DataFrame(rows)


def majority(checks):
    """Label chosen by more than half of the coders; threads without one drop."""
    first = next(iter(checks.values()))
    out = {}
    for field in FIELDS:
        labels = {}
        for thread in first.index:
            label, votes = Counter(
                c.loc[thread, field] for c in checks.values()).most_common(1)[0]
            if votes * 2 > len(checks):
                labels[thread] = label
        out[field] = pd.Series(labels, dtype=object)
    return out


def source_label(completed):
    if not completed:
        return "AI-coded, not yet checked by the team"
    people = "member" if completed == 1 else "members"
    return f"AI-coded, checked by {completed} team {people}"


def shares(df, field):
    table = pd.crosstab(df[field], df["window"]).reindex(
        columns=WINDOW_ORDER, fill_value=0)
    return table.sort_values(WINDOW_ORDER, ascending=False).reset_index()


def agreement_section(ai, checks):
    lines = ["## Agreement check", ""]
    for coder, codes in checks.items():
        lines += [f"### {coder} compared with the AI codes", "",
                  compare(codes, ai).to_markdown(index=False), ""]
    for a, b in itertools.combinations(checks, 2):
        lines += [f"### {a} compared with {b}", "",
                  compare(checks[a], checks[b]).to_markdown(index=False), ""]
    if len(checks) >= 3:
        rows = []
        for field, labels in majority(checks).items():
            if len(labels):
                match = (ai.loc[labels.index, field] == labels).mean() * 100
                rows.append({"field": field, "threads_with_majority": len(labels),
                             "percent_agreement_with_ai": round(match, 1)})
        lines += ["### Team majority compared with the AI codes", "",
                  pd.DataFrame(rows).to_markdown(index=False), ""]
    return lines


def main():
    ai = pd.read_csv(f"{DIR}/ai_codes.csv")
    sample = pd.read_csv(f"{DIR}/check_sample.csv")
    checks, unfinished = load_checks(DIR, set(sample["id"]))
    source = source_label(len(checks))

    lines = [
        "# RQ4: qualitative coding summary", "",
        f"**Labels: {source}.**", "",
        f"All {len(ai)} sampled threads were coded by an AI model (Claude) from",
        "the title, post text and up to 15 top-level comments, each shortened",
        "to at most 600 characters, using `qualitative/codebook.csv`. Team",
        f"members code a random {len(sample)} of them without seeing those labels.",
        "",
        "Counts are of sampled threads (most-commented, contested and",
        "cross-community), so they describe that sample, not all discussion.",
        "",
    ]
    for coder, count in unfinished.items():
        lines += [f"_{coder}: {count} of {len(sample)} threads complete, "
                  "not counted yet._", ""]
    if checks:
        lines += agreement_section(ai.set_index("thread_id"), checks)
    for field in FIELDS:
        lines += [f"## Threads by {field.replace('_', ' ')}", "",
                  shares(ai, field).to_markdown(index=False), ""]

    lines += ["## Stance by subreddit", ""]
    for window in WINDOW_ORDER:
        sub = ai[ai["window"] == window]
        table = pd.crosstab(sub["subreddit"], sub["stance_on_strikes"])
        lines += [f"### {window}", "", table.reset_index().to_markdown(index=False), ""]

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    out = ai[["window", "subreddit", "thread_id", *FIELDS]].assign(label_source=source)
    os.makedirs("tableau", exist_ok=True)
    out.to_csv(TABLEAU, index=False)
    print(f"Wrote {REPORT} and {TABLEAU} ({source})")
    for coder, count in unfinished.items():
        print(f"  {coder}: unfinished ({count}/{len(sample)} threads)")


if __name__ == "__main__":
    main()
