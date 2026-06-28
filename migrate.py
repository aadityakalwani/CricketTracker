"""One-time: map the Notion 'Cricket Log' CSV export to Log-tab rows.

Notion has only the 21 mirror columns; the 10 Play-Cricket extension columns are
left blank for historic rows (they predate scraping; MatchID gets backfilled
later where a row matches a real scorecard). Dates are normalised to YYYY-MM-DD
to match scraped rows.

Usage: python migrate.py "<path to ..._all.csv>" <sheetId>
"""

import csv
import sys
from datetime import datetime

from parse_match import COLUMNS
import sheet


def _norm_date(s):
    s = (s or "").strip()
    if not s:
        return ""
    try:
        return datetime.strptime(s, "%B %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        return s  # leave anything unexpected as-is rather than dropping it


def csv_to_rows(csv_path):
    """Return a list of row-lists in COLUMNS order."""
    rows = []
    with open(csv_path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            d = {c: "" for c in COLUMNS}            # extensions stay blank
            for c in COLUMNS:
                if c in r:
                    d[c] = (r[c] or "").strip()
            d["Date"] = _norm_date(r.get("Date"))
            rows.append([d[c] for c in COLUMNS])
    return rows


def main():
    csv_path, sid = sys.argv[1], sys.argv[2]
    rows = csv_to_rows(csv_path)
    print(f"mapped {len(rows)} rows")
    sheet.write_values(sid, f"A2:{sheet._col_letter(len(COLUMNS)-1)}{len(rows)+1}", rows)
    print("written to Log")


if __name__ == "__main__":
    main()
