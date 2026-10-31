# Strikes and Silos: Polarization Dynamics on Reddit during the US–Iran Conflict

This project compares Reddit discussion around two escalations of the US–Iran
conflict — the June 2025 US strikes and the February 2026 US–Israeli strikes —
and asks whether the second period shows stronger separation between
discussion communities. Polarization is operationalised structurally (who
replies to whom, and who shares which sources), not as sentiment.

## Research questions

| RQ | Question | Answered by |
|----|----------|-------------|
| RQ1 | How did discussion and interaction patterns differ between the two periods? | `03_eda.py` |
| RQ2 | Did Feb 2026 show stronger community separation? | `04_networks.py` (modularity, E–I index) |
| RQ3 | How did external source sharing differ across communities? | `05_sources.py` |
| RQ4 | What topics and narratives accompanied the separation? | `16_text_analysis.py` (all comments) |

## Study design

- **Windows:** two equal 21-day windows, each starting on the first day of
  major strikes — 13 Jun–3 Jul 2025 and 28 Feb–20 Mar 2026. Equal length
  matters because volume, network size and modularity all depend on how long
  we observed.
- **Communities:** r/worldnews, r/geopolitics, r/Iran, r/Israel, r/NewIran,
  r/IsraelPalestine, r/politics, r/Conservative — general news, regional and
  political communities, so there is something for community detection to
  separate.
- **Sampling rule:** a post is in scope if its title or body names Iran or an
  Iran-specific referent (see `TOPIC_TERMS` in `config.py`). The identical
  rule is applied to every subreddit and both windows.
- **Core dataset:** `02b_core.py` further narrows the cleaned data to threads
  that carry real discussion of the escalation — at least 50 comments, and
  either the Iran term in the title or multiple mentions in the body (not
  just a passing reference). Whole threads are kept or dropped, never
  individual comments, so reply chains stay intact. This keeps 87% of
  comments and drops small or only passingly relevant threads. Those threads
  do carry some reply edges (the core networks have about 11–14% fewer than
  the full ones), so every result is also reported on the full dataset.

## Data source

Posts and comments come from the **Arctic Shift** archive of the public Reddit
dumps, not the live Reddit API. The Reddit API cannot filter by date and stops
at roughly 1,000 results per listing, which makes it unusable for
reconstructing a past three-week window; Arctic Shift serves the same public
data with date filters and full comment trees.

## Pipeline

```
python scripts/01_collect.py     # raw JSONL into data/raw/   (long-running, resumable)
python scripts/02_clean.py       # tidy tables + quality report
python scripts/02b_core.py       # narrow to the "core" relevance-filtered dataset
python scripts/03_eda.py         # figures + summary table
python scripts/04_networks.py    # reply networks, communities, separation measures
python scripts/05_sources.py     # subreddit–source network
python scripts/06_sample_threads.py  # thread sample for the qualitative pass
python scripts/08_robustness.py      # size controls for both headline comparisons
python scripts/09_export_gephi.py    # subreddit-level + k-core graphs for Gephi
python scripts/10_utilisation.py     # how much of the collected data each analysis uses
python scripts/11_demo_networks.py   # small laptop-sized networks for the demo (figures/*/demo/)
python scripts/12_tableau_export.py  # aggregate CSVs for Tableau -> tableau/ (core only)
python scripts/07_report_pack.py     # computed numbers -> reports/ (run after 08)
python scripts/13_coding_sheet.py    # blank check sheets for RQ4 -> qualitative/ (core only)
python scripts/14_qualitative_summary.py  # RQ4 tables and agreement -> reports/
python scripts/16_text_analysis.py        # topic frames and topic model on all comments
python scripts/15_tableau_workbook.py     # tableau/strikes_and_silos.twbx (run after 12 and 16)
```

## Tableau dashboard

Open `tableau/strikes_and_silos.twbx` in Tableau Public. It has four
dashboards (activity, separation, sources, topics) built only from
aggregate tables: no usernames or comment text.

## Text analysis of all comments (RQ4)

`16_text_analysis.py` measures how often each topic frame is mentioned (word
lists, listed in the report) and runs a topic model, on every comment that was
not deleted or removed. Results: `reports/text_analysis.md` (full data) and
`reports/core/text_analysis.md` (core). The word lists show what was discussed,
not stance, and have not been validated against hand labels.

## Exploratory thread coding (not part of the findings)

An AI model (Claude) labelled the 84 sampled threads for topic, stance and tone
using `qualitative/codebook.csv` (labels in `qualitative/ai_codes.csv`, summary
in `reports/qualitative_summary.md`). **No team member has verified these
labels**, so they are exploratory only. `13_coding_sheet.py` can draw 20 threads
for an independent check, and `14_qualitative_summary.py` then reports
agreement. No script regenerates the AI labels.

## Ethics and data handling

- Usernames are replaced by a salted hash in `02_clean.py`; raw usernames are
  never written to the processed tables or the repository.
- Only public posts and comments are collected.
- Deleted and moderator-removed content is retained as a *count* (for the
  limitations section) but carries no author identity.
- `data/` is gitignored: the repository holds code, not redistributed Reddit
  content.

## Known limitations

- Comments per post are capped at 1,500, and threads with fewer than 10
  comments are skipped. Both caps apply equally to both windows and the number
  of posts affected is recorded in `data/raw/collection_log_*.json`.
- Reddit is not the general public; it skews young, male, English-speaking and
  Western.
- Content deleted before the archive snapshot is invisible to us, and
  moderation intensity may itself differ between the two windows.
- Keyword sampling misses discussion that never names Iran explicitly.

## Repository layout

```
scripts/           pipeline stages, plus config.py (study design) and arctic.py (API client)
data/raw/          collected JSONL + collection logs             (gitignored)
data/processed/    full-dataset analysis tables + quality report (gitignored)
data/processed_core/  core-dataset analysis tables               (gitignored)
figures/           full-dataset EDA charts and .gexf network files for Gephi
figures/core/      same, for the core dataset
figures/core/demo/ small networks (community bubbles + ~1,300-user samples) that open on a laptop;
                   the full .gexf files in figures/core/networks/ are too large to draw
reports/           generated numbers tables (full vs. core dataset) and RQ4 summary
tableau/           aggregate CSVs and the packaged Tableau workbook
qualitative/       RQ4 codebook, AI codes and check sample (sheets stay local)
```
