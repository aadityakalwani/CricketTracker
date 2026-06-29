# Open questions / things for Aadi (fire away when back)

Updated 2026-06-29 while you were away. Status: P1–P3 done, P4 (sync) in progress.
Sheet: https://docs.google.com/spreadsheets/d/1XyMrLZq5XSJ-65acMeqxAL42iFfp1jl0YhNc4GYNTRc/edit

## 1. "Make it an actual table" + the headers
The header row IS there (row 1, all 31 columns named). I can't *format* via the
Sheets proxy (it only reads/writes cell values, not freezing/bold/table styling).
**Your 20-second job:** in the sheet → `Format ▸ Convert to table` (auto-detects
headers + types), and `View ▸ Freeze ▸ 1 row`. That turns the data dump into a
real sortable/filterable table. If you'd rather I reorder or hide columns first,
say so.

## 2. The "duplicate" Old Leightonians game — it's not a duplicate
There's only **one** row for that game (row 87). What looked like a second copy
"to the right" is the new **Play-Cricket extension columns** (V onward): MatchID,
Season, Competition, Venue, H/A, Toss, Result, Margin, Bat Pos, Scorecard URL.
Columns A–U are the familiar Notion fields; V–AE are the extras the scraper adds.
Once row 1 is frozen it reads as one wide row. Tell me if you'd rather the extra
columns live on a separate tab or be dropped.

## 3. BIGGEST open item: full league/all-time auto-discovery is unsolved
- Your `player_stats` pages only surface ~39 games (friendlies you batted/bowled
  in) and **do not list league games at all** (your example 7276745 is absent,
  with or without the rule_type filter). So `rule_type_id` isn't the lever.
- The proper "all matches" page (`/Matches`) loads results via JavaScript/AJAX
  after you pick filters, so there are no static links to scrape yet.
- **For now** `--sync` captures: your friendly games from player_stats + whatever
  is on the homepage results widget (newest ~7) + any IDs I pass by hand. That
  catches recent games but NOT a full historical league backfill.
- **Question for you:** is "capture new games going forward (+ paste-link the odd
  older one)" enough, or do you want me to crack the `/Matches` AJAX for a
  complete all-time league + friendly backfill? The latter is more work but
  doable. Either way, paste me any specific older scorecard URLs you want in now
  and `--game`/`--sync --ids` will add them.

## 4. Confirm the column set is final
Current order = your Notion columns mirrored 1:1, then the 10 Play-Cricket extras.
Happy with that, or want a different layout before I build the stats tab?

## 5. (FYI) sync perf note, not blocking
`--sync` currently re-loads every candidate game page to read its date, so it's a
few minutes and gets slower as history grows. Easy fix later: read the date from
the stats table directly and skip old games without loading them. Logged as debt.
