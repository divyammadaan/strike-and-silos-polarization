"""Stage 13: reading material for the qualitative pass (RQ4).

RQ4 is coded with AI assistance and checked by the team on a random subset.
Both work from the same material: each thread's title, post text and
highest-scored top-level comments, as selected by 06_sample_threads.py.

Writes:
  qualitative/reading_dump.txt         all sampled threads, for the AI pass
  qualitative/check_sheet_<coder>.xlsx one blank sheet per team member, holding
                                       the same random threads and no AI labels
  qualitative/check_sample.csv         which threads were drawn for the check

The dump and sheets quote Reddit text, so they are gitignored.

Usage: CSMA_VARIANT=core python 13_coding_sheet.py [--coders a b c]
"""

import argparse
import os
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.hyperlink import Hyperlink

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PROCESSED_DIR, WINDOWS

OUT_DIR = "qualitative"
TOP_COMMENTS = 15     # highest-scored top-level comments shown per thread
COMMENT_CHARS = 600
POST_CHARS = 800
CHECK_PER_WINDOW = 10  # threads per window in the team's check sample
SEED = 2026
CHECK_FIELDS = ["primary_frame", "stance_on_strikes", "tone"]


def clean(text, limit):
    if not isinstance(text, str):
        return ""
    text = ILLEGAL_CHARACTERS_RE.sub("", " ".join(text.split()))
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def threads_to_code():
    """One row per thread; a thread can be sampled for more than one reason."""
    sample = pd.read_csv(f"{PROCESSED_DIR}/qualitative_sample.csv")
    keys = ["window", "subreddit", "id", "title", "num_comments", "permalink"]
    threads = (sample.groupby(keys, dropna=False)["selection_reason"]
               .agg("; ".join).reset_index())
    order = {key: i for i, key in enumerate(WINDOWS)}
    threads = threads.sort_values(
        ["window", "subreddit", "num_comments"],
        key=lambda s: s.map(order) if s.name == "window" else s,
        ascending=[True, True, False]).reset_index(drop=True)
    threads.insert(0, "n", range(1, len(threads) + 1))

    posts = pd.read_csv(f"{PROCESSED_DIR}/posts.csv", usecols=["id", "selftext"])
    return threads.merge(posts, on="id", how="left")


def top_comments(ids):
    """{thread id: [(score, text), ...]} for the sampled threads."""
    c = pd.read_csv(f"{PROCESSED_DIR}/comments.csv", low_memory=False)
    c = c[c["post_id"].isin(ids) & c["is_top_level"] & ~c["is_deleted"]
          & c["author_hash"].notna()]
    c = c.sort_values("score", ascending=False).groupby("post_id").head(TOP_COMMENTS)
    return {post_id: [(int(r.score), clean(r.body, COMMENT_CHARS))
                      for r in group.itertuples()]
            for post_id, group in c.groupby("post_id")}


def write_dump(threads, comments):
    with open(f"{OUT_DIR}/reading_dump.txt", "w", encoding="utf-8") as f:
        for t in threads.itertuples():
            f.write(f"#{t.n} {t.window} r/{t.subreddit} [{t.id}]\n"
                    f"TITLE: {clean(t.title, 300)}\n")
            body = clean(t.selftext, POST_CHARS)
            if body and body not in ("[removed]", "[deleted]"):
                f.write(f"POST: {body}\n")
            for score, text in comments.get(t.id, []):
                f.write(f"- {text}\n")
            f.write("\n")


def add_row(sheet, values):
    sheet.append(values)
    for cell in sheet[sheet.max_row]:
        # Reddit text can start with "=", which Excel would run as a formula.
        if isinstance(cell.value, str):
            cell.data_type = "s"
        cell.alignment = Alignment(wrap_text=True, vertical="top")


def style_header(sheet, widths):
    for i, width in enumerate(widths):
        sheet.column_dimensions[sheet.cell(1, i + 1).column_letter].width = width
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDE5F0")
    sheet.freeze_panes = "A2"


def check_workbook(sample, comments, codebook):
    book = Workbook()
    coding = book.active
    coding.title = "coding"
    reading = book.create_sheet("reading")
    header = ["n", "window", "subreddit", "thread_id", "title", "read", "link",
              *CHECK_FIELDS, "notes"]
    coding.append(header)
    reading.append(["n", "score", "text"])

    for t in sample.itertuples():
        start = reading.max_row + 1
        add_row(reading, [t.n, "title", clean(t.title, 300)])
        body = clean(t.selftext, POST_CHARS)
        if body and body not in ("[removed]", "[deleted]"):
            add_row(reading, [t.n, "post", body])
        for score, text in comments.get(t.id, []):
            add_row(reading, [t.n, score, text])
        reading.cell(start, 3).font = Font(bold=True)

        link = "https://www.reddit.com" + t.permalink
        add_row(coding, [t.n, t.window, t.subreddit, t.id, clean(t.title, 300),
                         "read comments", link, *[""] * (len(CHECK_FIELDS) + 1)])
        row = coding.max_row
        # A "location" link jumps within the workbook.
        coding.cell(row, 6).hyperlink = Hyperlink(
            ref=f"F{row}", location=f"reading!A{start}")
        coding.cell(row, 7).hyperlink = link
        for column in (6, 7):
            coding.cell(row, column).font = Font(color="0563C1", underline="single")

    style_header(coding, [5, 11, 15, 10, 55, 15, 30, 28, 20, 16, 30])
    style_header(reading, [5, 8, 120])

    guide = book.create_sheet("codebook")
    guide.append(["field", "code", "definition"])
    for r in codebook.itertuples():
        add_row(guide, [r.field, r.code, r.definition])
    style_header(guide, [22, 32, 100])

    for field in CHECK_FIELDS:
        rows = codebook.index[codebook["field"] == field]
        # Codebook rows start on sheet row 2 and each field's codes are contiguous.
        rule = DataValidation(
            type="list", allow_blank=True,
            formula1=f"=codebook!$B${rows.min() + 2}:$B${rows.max() + 2}")
        coding.add_data_validation(rule)
        column = coding.cell(1, header.index(field) + 1).column_letter
        rule.add(f"{column}2:{column}{coding.max_row}")
    return book


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coders", nargs="+",
                        default=["coder1", "coder2", "coder3"])
    args = parser.parse_args()

    threads = threads_to_code()
    comments = top_comments(set(threads["id"]))
    codebook = pd.read_csv(f"{OUT_DIR}/codebook.csv")
    write_dump(threads, comments)

    sample = (threads.groupby("window", group_keys=False)
              .sample(CHECK_PER_WINDOW, random_state=SEED)
              .sort_values("n"))
    sample[["n", "window", "subreddit", "id"]].to_csv(
        f"{OUT_DIR}/check_sample.csv", index=False)

    for coder in args.coders:
        out = f"{OUT_DIR}/check_sheet_{coder}.xlsx"
        if os.path.exists(out):
            print(f"{out} already exists; left unchanged so coding is not lost.")
            continue
        check_workbook(sample, comments, codebook).save(out)
        print(f"{len(sample)} threads written to {out}")
    print(f"{len(threads)} threads written to {OUT_DIR}/reading_dump.txt")


if __name__ == "__main__":
    main()
