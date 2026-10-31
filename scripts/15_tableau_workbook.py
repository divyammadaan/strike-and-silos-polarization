"""Stage 15: build the Tableau workbook from the CSVs in tableau/.

Writes tableau/strikes_and_silos.twbx, a packaged workbook holding the data and
four dashboards (activity, separation, sources, topics). Each table is
stored as a CSV plus a .hyper extract, which Tableau Public requires. Only
aggregate tables go into it: no usernames and no comment text, so it is safe to
publish on Tableau Public.

Usage: python 15_tableau_workbook.py   (after stages 12 and 16)
"""

import io
import os
import tempfile
import uuid
import zipfile
from xml.sax.saxutils import quoteattr

import pandas as pd
from tableauhyperapi import (Connection, CreateMode, HyperProcess, Inserter,
                             SqlType, TableDefinition, TableName, Telemetry)

DATA_DIR = "tableau"
OUT = f"{DATA_DIR}/strikes_and_silos.twbx"

# Labels that sort in time order without any manual sort in Tableau.
LABELS = {"june_2025": "2025 June strikes", "feb_2026": "2026 February strikes"}


# Readable names shown on axes, headers and legends.
CAPTIONS = {
    "label": "Window", "count": "Comments", "day": "Days since first strikes",
    "pct_of_window": "% of window's comments", "value": "Value",
    "pct_of_replies": "% of all replies", "overlap": "Similarity",
    "times_shared": "Times shared", "thread_id": "Threads",
    "primary_frame": "Main frame", "stance_on_strikes": "Stance on strikes",
    "subreddit": "Subreddit", "other_subreddit": "Compared with",
    "source": "Replier's subreddit", "target": "Replied-to subreddit",
    "domain": "Domain", "frame": "Topic",
    "pct_of_comments": "% of comments",
}


def attr(value):
    return quoteattr(str(value))


def uid(name):
    return "{" + str(uuid.uuid5(uuid.NAMESPACE_URL, name)).upper() + "}"


def load(name):
    df = pd.read_csv(f"{DATA_DIR}/{name}.csv")
    if "window" in df:
        df["label"] = df["window"].map(LABELS)
    return df


def kind(series):
    """(datatype, role, type, remote OLE type) of a column."""
    if series.dtype == bool:
        return "boolean", "dimension", "nominal", 11
    if pd.api.types.is_integer_dtype(series):
        return "integer", "measure", "quantitative", 20
    if pd.api.types.is_float_dtype(series):
        return "real", "measure", "quantitative", 5
    return "string", "dimension", "nominal", 129


class Source:
    def __init__(self, name):
        self.name = name
        self.df = load(name)
        self.id = "federated." + uuid.uuid5(uuid.NAMESPACE_URL, name).hex[:24]
        self.conn = "textscan." + uuid.uuid5(uuid.NAMESPACE_DNS, name).hex[:24]

    def write_extract(self, hyper, path):
        """Write the table to a .hyper file as Extract.Extract."""
        sql = {"boolean": SqlType.bool, "integer": SqlType.big_int,
               "real": SqlType.double, "string": SqlType.text}
        table = TableDefinition(
            TableName("Extract", "Extract"),
            [TableDefinition.Column(f, sql[kind(self.df[f])[0]]())
             for f in self.df.columns])
        rows = self.df.astype(object).where(self.df.notna(), None).values.tolist()
        with Connection(hyper.endpoint, path,
                        CreateMode.CREATE_AND_REPLACE) as connection:
            connection.catalog.create_schema("Extract")
            connection.catalog.create_table(table)
            with Inserter(connection, table) as inserter:
                inserter.add_rows(rows)
                inserter.execute()

    def column(self, field):
        datatype, role, type_, _ = kind(self.df[field])
        caption = (f"caption={attr(CAPTIONS[field])} "
                   if field in CAPTIONS else "")
        if field == "value":
            caption += "default-format='n#,##0.000;-#,##0.000' "
        return (f"<column {caption}datatype='{datatype}' name='[{field}]' "
                f"role='{role}' type='{type_}' />")

    def xml(self):
        columns, records, extract_records = [], [], []
        for i, field in enumerate(self.df.columns):
            datatype, _, _, remote = kind(self.df[field])
            columns.append(f"<column datatype='{datatype}' name={attr(field)} ordinal='{i}' />")
            records.append(
                "<metadata-record class='column'>"
                f"<remote-name>{field}</remote-name><remote-type>{remote}</remote-type>"
                f"<local-name>[{field}]</local-name>"
                f"<parent-name>[{self.name}.csv]</parent-name>"
                f"<remote-alias>{field}</remote-alias><ordinal>{i}</ordinal>"
                f"<local-type>{datatype}</local-type>"
                "<contains-null>true</contains-null></metadata-record>")
            extract_records.append(records[-1].replace(
                f"<parent-name>[{self.name}.csv]</parent-name>",
                "<parent-name>[Extract]</parent-name>"))
        return f"""
    <datasource caption={attr(self.name)} inline='true' name='{self.id}' version='18.1'>
      <connection class='federated'>
        <named-connections>
          <named-connection caption={attr(self.name)} name='{self.conn}'>
            <connection class='textscan' directory='Data' filename='{self.name}.csv' password='' server='' />
          </named-connection>
        </named-connections>
        <relation connection='{self.conn}' name='{self.name}.csv' table='[{self.name}#csv]' type='table'>
          <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>
            {''.join(columns)}
          </columns>
        </relation>
        <metadata-records>{''.join(records)}</metadata-records>
      </connection>
      {''.join(self.column(f) for f in self.df.columns)}
      <extract count='-1' enabled='true' units='records'>
        <connection access_mode='readonly' class='hyper' dbname='Data/Extracts/{self.name}.hyper' default-settings='yes' schema='Extract' sslmode='' tablename='Extract' username=''>
          <relation name='Extract' table='[Extract].[Extract]' type='table' />
          <metadata-records>{''.join(extract_records)}</metadata-records>
        </connection>
      </extract>
    </datasource>"""


class Pill:
    """One field on a shelf, e.g. Pill('count', 'sum') or Pill('label')."""

    DERIVATION = {"none": "None", "sum": "Sum", "avg": "Avg", "cnt": "Count"}

    def __init__(self, field, agg="none", continuous=False):
        self.field, self.agg = field, agg
        self.continuous = continuous or agg != "none"
        suffix = "qk" if self.continuous else "nk"
        self.name = f"[{agg}:{field}:{suffix}]"

    def instance(self):
        type_ = "quantitative" if self.continuous else "nominal"
        return (f"<column-instance column='[{self.field}]' "
                f"derivation='{self.DERIVATION[self.agg]}' name='{self.name}' "
                f"pivot='key' type='{type_}' />")

    def ref(self, source):
        return f"[{source.id}].{self.name}"


def worksheet(name, title, source, rows, cols, mark="Automatic", color=None,
              text=None, keep=None, show_filter=False):
    """keep: (field, value) restricting the sheet to one member of a field."""
    pills = [*rows, *cols, *(p for p in (color, text) if p)]
    filter_pill = Pill(keep[0]) if keep else None
    if filter_pill:
        pills.append(filter_pill)
    unique = {p.name: p for p in pills}
    fields = dict.fromkeys(p.field for p in unique.values())

    filter_xml = ""
    if keep:
        value = keep[1]
        member = "true" if value is True else f'"{value}"'
        filter_xml = (
            f"<filter class='categorical' column='{filter_pill.ref(source)}'>"
            f"<groupfilter function='member' level='{filter_pill.name}' "
            f"member={attr(member)} user:ui-domain='database' "
            "user:ui-enumeration='inclusive' user:ui-marker='enumerate' /></filter>"
            f"<slices><column>{filter_pill.ref(source)}</column></slices>")

    encodings = ""
    if color:
        encodings += f"<color column='{color.ref(source)}' />"
    if text:
        encodings += f"<text column='{text.ref(source)}' />"
    labels = ("<style><style-rule element='mark'><format attr='mark-labels-show' "
              "value='true' /></style-rule></style>") if text else ""

    def shelf(items):
        if not items:
            return ""
        refs = [p.ref(source) for p in items]
        return refs[0] if len(refs) == 1 else "(" + " / ".join(refs) + ")"

    sheet = f"""
    <worksheet name={attr(name)}>
      <layout-options><title><formatted-text><run fontsize='12'>{title}</run></formatted-text></title></layout-options>
      <table>
        <view>
          <datasources><datasource caption={attr(source.name)} name='{source.id}' /></datasources>
          <datasource-dependencies datasource='{source.id}'>
            {''.join(source.column(f) for f in fields)}
            {''.join(p.instance() for p in unique.values())}
          </datasource-dependencies>
          {filter_xml}
          <aggregation value='true' />
        </view>
        <style />
        <panes>
          <pane>
            <view><breakdown value='auto' /></view>
            <mark class='{mark}' />
            <encodings>{encodings}</encodings>
            {labels}
          </pane>
        </panes>
        <rows>{shelf(rows)}</rows>
        <cols>{shelf(cols)}</cols>
      </table>
      <simple-id uuid='{uid("sheet:" + name)}' />
    </worksheet>"""
    card = (f"<edge name='right'><strip size='180'><card param='{filter_pill.ref(source)}' "
            "type='filter' /></strip></edge>") if show_filter else ""
    window = f"""
    <window class='worksheet' name={attr(name)}>
      <cards>
        <edge name='left'><strip size='160'><card type='pages' /><card type='filters' /><card type='marks' /></strip></edge>
        <edge name='top'><strip size='2147483647'><card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip><strip size='31'><card type='title' /></strip></edge>
        {card}
      </cards>
      <viewpoint><zoom type='entire-view' /></viewpoint>
      <simple-id uuid='{uid("window:" + name)}' />
    </window>"""
    return name, sheet, window


LEGEND_WIDTH = 15000  # of 100000, a column on the right of each dashboard


TAKEAWAY_HEIGHT = 8000  # of 100000, a text line across the top


def dashboard(name, takeaway, grid, legends):
    """grid: list of rows, each a list of worksheet names, split evenly.
    legends: list of (worksheet name, source, pill) colour keys to show."""
    zones = [f"<zone h='{TAKEAWAY_HEIGHT}' id='2' type-v2='text' w='100000' x='0' y='0'>"
             f"<formatted-text><run bold='true' fontsize='12'>{takeaway}</run>"
             "</formatted-text></zone>"]
    zone_id = 3
    height = (100000 - TAKEAWAY_HEIGHT) // len(grid)
    for r, row in enumerate(grid):
        width = (100000 - LEGEND_WIDTH) // len(row)
        for c, sheet in enumerate(row):
            zones.append(f"<zone h='{height}' id='{zone_id}' name={attr(sheet)} "
                         f"w='{width}' x='{c * width}' y='{TAKEAWAY_HEIGHT + r * height}' />")
            zone_id += 1
    for i, (sheet, source, pill) in enumerate(legends):
        zones.append(f"<zone h='14000' id='{zone_id}' name={attr(sheet)} "
                     f"param='{pill.ref(source)}' type-v2='color' "
                     f"w='{LEGEND_WIDTH}' x='{100000 - LEGEND_WIDTH}' y='{TAKEAWAY_HEIGHT + i * 14000}' />")
        zone_id += 1
    board = f"""
    <dashboard name={attr(name)}>
      <style />
      <size sizing-mode='automatic' />
      <zones>
        <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>{''.join(zones)}</zone>
      </zones>
      <simple-id uuid='{uid("dashboard:" + name)}' />
    </dashboard>"""
    views = "".join(f"<viewpoint name={attr(s)}><zoom type='entire-view' /></viewpoint>"
                    for row in grid for s in row)
    window = f"""
    <window class='dashboard' name={attr(name)}>
      <viewpoints>{views}</viewpoints>
      <active id='-1' />
      <simple-id uuid='{uid("dashboard-window:" + name)}' />
    </window>"""
    return board, window


def main():
    sources = {n: Source(n) for n in [
        "daily_volume", "subreddit_share", "robustness_runs", "subreddit_edges",
        "source_overlap", "top_domains",
        "text_frames_overall", "text_frames_by_subreddit"]}
    s = sources
    label = Pill("label")

    def runs(name, title, metric):
        return worksheet(name, title, s["robustness_runs"],
                         rows=[Pill("value", "avg")], cols=[label], mark="Bar",
                         color=label, text=Pill("value", "avg"),
                         keep=("metric", metric))

    sheets = [
        worksheet("Daily comments", "Comments per day (day 0 = first strikes)",
                  s["daily_volume"], rows=[Pill("count", "sum")],
                  cols=[Pill("day", continuous=True)], mark="Line", color=label,
                  keep=("metric", "comments"), show_filter=True),
        worksheet("Subreddit share", "Share of each window's comments (%)",
                  s["subreddit_share"], rows=[Pill("subreddit"), label],
                  cols=[Pill("pct_of_window", "sum")], mark="Bar", color=label),
        runs("Modularity", "Modularity (equal size)",
             "modularity"),
        runs("EI by subreddit", "E-I by subreddit (equal size)",
             "ei_index_by_subreddit"),
        runs("Source overlap", "Source overlap (equal size)",
             "mean_pairwise_source_overlap"),
        worksheet("Cross replies", "Replies between different subreddits (% of all replies)",
                  s["subreddit_edges"], rows=[Pill("source")],
                  cols=[label, Pill("target")], mark="Square",
                  color=Pill("pct_of_replies", "sum"),
                  keep=("is_cross_community", True)),
        worksheet("Overlap heatmap", "Source similarity between subreddit pairs (cosine)",
                  s["source_overlap"], rows=[Pill("subreddit")],
                  cols=[label, Pill("other_subreddit")], mark="Square",
                  color=Pill("overlap", "avg")),
        worksheet("Top domains", "Most-shared link domains",
                  s["top_domains"], rows=[Pill("domain")],
                  cols=[label, Pill("times_shared", "sum")], mark="Bar", color=label),
        worksheet("Topics overall", "Share of all comments mentioning each topic (%)",
                  s["text_frames_overall"], rows=[Pill("frame"), label],
                  cols=[Pill("pct_of_comments", "sum")], mark="Bar", color=label),
        worksheet("Topics by subreddit", "Topic mentions by subreddit (% of comments)",
                  s["text_frames_by_subreddit"], rows=[Pill("frame")],
                  cols=[label, Pill("subreddit")], mark="Square",
                  color=Pill("pct_of_comments", "avg")),
    ]
    dashboards = [
        dashboard("1 Activity",
                  "February 2026 drew more comments overall. June 2025 spiked around "
                  "day 9 (22 June) and faded; February stayed busy. (Core dataset)",
                  [["Daily comments"], ["Subreddit share"]],
                  [("Daily comments", s["daily_volume"], label)]),
        dashboard("2 Separation",
                  "February 2026 was not more separated in who replied to whom: "
                  "modularity and E-I both moved slightly towards more mixing, while "
                  "shared sources overlapped less. (Core dataset)",
                  [["Modularity", "EI by subreddit", "Source overlap"],
                   ["Cross replies"]],
                  [("Modularity", s["robustness_runs"], label),
                   ("Cross replies", s["subreddit_edges"],
                    Pill("pct_of_replies", "sum"))]),
        dashboard("3 Sources",
                  "Subreddits' link sources were less alike in February 2026. Paler "
                  "squares mean less similar sources. (Core dataset)",
                  [["Overlap heatmap", "Top domains"]],
                  [("Top domains", s["top_domains"], label),
                   ("Overlap heatmap", s["source_overlap"], Pill("overlap", "avg"))]),
        dashboard("4 Topics",
                  "Discussion moved from Israel and the nuclear programme towards oil "
                  "and US politics. A comment can mention several topics. (All comments)",
                  [["Topics overall"], ["Topics by subreddit"]],
                  [("Topics overall", s["text_frames_overall"], label),
                   ("Topics by subreddit", s["text_frames_by_subreddit"],
                    Pill("pct_of_comments", "avg"))]),
    ]

    workbook = f"""<?xml version='1.0' encoding='utf-8' ?>
<workbook original-version='18.1' source-build='2022.2.0 (20222.22.0624.2136)' source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <document-format-change-manifest>
    <SheetIdentifierTracking />
    <WindowsPersistSimpleIdentifiers />
  </document-format-change-manifest>
  <preferences />
  <datasources>{''.join(src.xml() for src in sources.values())}</datasources>
  <worksheets>{''.join(sheet for _, sheet, _ in sheets)}</worksheets>
  <dashboards>{''.join(board for board, _ in dashboards)}</dashboards>
  <windows source-height='30'>{''.join(w for _, w in dashboards)}{''.join(w for _, _, w in sheets)}</windows>
</workbook>
"""
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as archive,             tempfile.TemporaryDirectory() as tmp,             HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU,
                         parameters={"log_dir": tmp}) as hyper:
        archive.writestr("strikes_and_silos.twb", workbook)
        for src in sources.values():
            buffer = io.StringIO()
            src.df.to_csv(buffer, index=False, lineterminator="\n")
            archive.writestr(f"Data/{src.name}.csv", buffer.getvalue())
            path = os.path.join(tmp, f"{src.name}.hyper")
            src.write_extract(hyper, path)
            archive.write(path, f"Data/Extracts/{src.name}.hyper")
    print(f"Wrote {OUT}: {len(sheets)} worksheets, {len(dashboards)} dashboards")


if __name__ == "__main__":
    main()
