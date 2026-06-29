"""Merge scraped scorecard rows with the handwritten Notion log, then rewrite the
Log tab as one clean row per game (sorted by date).

- Scraped data (backfill_rows.json) is authoritative for stats + context.
- Your Notion notes/video/drops (the API has none of these) are merged on by Date.
- Any Notion game with no matching scraped row (e.g. no published scorecard) is
  kept as-is, so nothing is lost.

Usage: python reconcile.py <notion_all.csv> <backfill_rows.json> <sheetId> [--apply]
Without --apply it only prints what it would do (dry run).
"""

import csv
import glob
import json
import sys
from datetime import datetime

from parse_match import COLUMNS
import sheet

# Fields worth keeping from the handwritten log (not in the scorecard API).
CARRY = ["Notes / Memory Trigger / Game Review", "Video?", "Drops"]


def _norm_date(s):
    s = (s or "").strip()
    if not s:
        return ""
    try:
        return datetime.strptime(s, "%B %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        return s[:10]


def load_notion(csv_path):
    rows = []
    with open(csv_path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            d = {c: (r.get(c, "") or "").strip() for c in COLUMNS}
            d["Date"] = _norm_date(r.get("Date"))
            rows.append(d)
    return rows


def reconcile(notion_rows, scraped):
    by_date = {}
    for nr in notion_rows:
        by_date.setdefault(nr["Date"], []).append(nr)

    final = []
    merged = scraped_only = 0
    for row in sorted(scraped.values(), key=lambda r: str(r["Date"])):
        row = dict(row)
        pool = by_date.get(row["Date"][:10])
        if pool:
            nr = pool.pop(0)  # consume one Notion row for this date
            for f in CARRY:
                if not row.get(f) and nr.get(f):
                    row[f] = nr[f]
            merged += 1
        else:
            scraped_only += 1
        final.append(row)

    leftover = [nr for pool in by_date.values() for nr in pool]
    final.extend(leftover)
    final.sort(key=lambda r: str(r.get("Date", "")))
    return final, dict(merged=merged, scraped_only=scraped_only, leftover_notion=len(leftover))


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else glob.glob("/tmp/ctexport/*_all.csv")[0]
    rows_json = sys.argv[2]
    sid = sys.argv[3]
    apply = "--apply" in sys.argv

    notion = load_notion(csv_path)
    scraped = json.loads(open(rows_json).read())
    final, stats = reconcile(notion, scraped)
    print(f"notion={len(notion)} scraped={len(scraped)} -> final={len(final)}  {stats}")
    if stats["leftover_notion"]:
        print("leftover Notion rows (no scraped match — check for date-mismatch dupes):")
        for pool in sorted({r["Date"]: r for r in final if not r.get("MatchID")}.items()):
            print("   ", pool[0], pool[1].get("Team"), pool[1].get("Opposition"))

    if not apply:
        print("\n(dry run — pass --apply to rewrite the Log tab)")
        return
    grid = [[r.get(c, "") for c in COLUMNS] for r in final]
    sheet.call({"action": "clear", "sheetId": sid, "tab": sheet.TAB, "range": f"A2:{sheet._col_letter(len(COLUMNS)-1)}2000"})
    sheet.ensure_header(sid)
    sheet.write_values(sid, f"A2:{sheet._col_letter(len(COLUMNS)-1)}{len(grid)+1}", grid)
    print(f"APPLIED: wrote {len(grid)} rows to Log")


if __name__ == "__main__":
    main()
