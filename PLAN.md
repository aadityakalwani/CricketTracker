# Cricket Tracker — Build Plan (Play-Cricket → Google Sheets)

Status: DESIGN — interview locked, ready to build. Nothing built yet.
Last updated 2026-06-29. See §1b for the locked decisions. Blocked on Notion
MCP auth (Notion-first build order).

## 0. The one-line summary

Replace the manual Notion cricket database with a Google Sheet that is fed,
per game, by a Playwright scraper logged in as Aadi. Two ways to add a game:
paste a scorecard URL, or say "update my cricket sheet" and it pulls anything
new. A second tab computes career stats with plain formulas, replacing the
Play-Cricket stats page. One-time job up front: copy the existing Notion rows
across.

## 1b. Decisions locked from the second interview (2026-06-29)

- **Session:** persistent Chrome profile + manual `--login`, no stored password
  (see §5.1, corrected). Reuses BaianaBot's real mechanism.
- **Build order:** sequential, **Notion migration first, then scraper**. So
  P0 → P5 (port history) → P1-P4 (scraper) → P6 (skill). Not parallel.
- **Critical-path prerequisite:** Notion MCP must be authorised before next
  session (`/mcp` → claude.ai Notion). Notion-first means this now blocks the
  start, not just the migration.
- **Scope v1:** Log tab only. Summary/career-stats tab deferred (confirmed
  again — add later once the Log is populated).
- **Destination:** create a **fresh** Google Sheet, Log tab only.

## 1. Decisions locked from the interview (2026-06-28)

- Source: **scrape while logged in** as Aadi. Not the official API (reasons in §3).
- Scope: **all-time at BNHCC** (Basingstoke & North Hants CC), every season.
- Track: **batting + bowling + fielding + match context**, columns mirroring
  the existing Notion database (the columns Aadi already cares about).
- Trigger: **paste-a-link OR on-demand command** (a mix). No unattended cron.
- Destination: **Google Sheet** (Notion explicitly rejected as bloated).

## 2. Open dependency (blocks only the schema + migration)

Read the existing Notion cricket database to (a) lock the exact column list and
(b) copy the rows over. Needs Notion MCP authorised (`/mcp` → claude.ai Notion).
Everything else below is independent of this and can be designed/built first.

## 3. Why scrape, not the official API

Researched the ECB Play-Cricket API (play-cricket.ecb.co.uk). Two blockers:

1. The `api_token` is issued only to a **club admin/committee member who signs
   an agreement** with the ECB help desk. Aadi is a player, not an admin, so the
   token isn't realistically obtainable.
2. Even with a token, the docs state **"Play-Cricket does not offer endpoints
   for statistics"**. The API exposes raw *scorecards* (Result Summary API),
   not the aggregated batting/bowling/fielding numbers. So the API would still
   require computing Aadi's per-game contributions ourselves.

Given (1) makes the token a non-starter and (2) removes its main advantage,
scraping the authenticated pages with Aadi's own login is the correct path.
The per-game data we need (his row in each scorecard) lives on the same
`/website/results/<id>` pages the API would return anyway.

Note: the Play-Cricket player stats page sits behind a login wall ("You must be
registered to view these player statistics"), confirmed during research. The
scraper must hold an authenticated session, exactly like BaianaBot does for
Fatsoma — reuse that pattern.

## 4. Architecture

```
                 ┌─────────────────────────┐
  paste URL ───► │  cricket skill (/cricket)│ ◄─── "update my cricket sheet"
                 └────────────┬────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ cricket_scraper.py│  (Playwright, headless)
                    │  - login + session│
                    │  - discover matches
                    │  - parse scorecard│
                    └─────────┬─────────┘
                              │ structured dict per game
                    ┌─────────▼─────────┐
                    │  sheet writer     │  (existing $CLAUDE_SHEETS_URL proxy /
                    │  - dedup by MatchID│   sheet-edit skill)
                    │  - append row     │
                    └─────────┬─────────┘
                              │
                  ┌───────────▼───────────┐
                  │  Google Sheet         │
                  │  Tab 1: Log (per game)│  ← source of truth
                  │  Tab 2: Summary       │  ← formulas, career stats
                  └───────────────────────┘
```

Components, each independently testable:

- **cricket_scraper.py** — pure data in/out. Given a scorecard URL, returns a
  dict of Aadi's contributions + match context. Given "discover", returns the
  list of his BNHCC match URLs across all seasons. Owns login + cookie reuse.
- **sheet writer** — takes a dict, dedups against existing MatchIDs, appends a
  row. Uses the proxy Aadi already has; no new Sheets code.
- **the /cricket skill** — the glue + UX. Routes "here's a URL" vs "update".
- **Summary tab** — not code. Spreadsheet formulas over the Log tab.

Lives at `~/Documents/CricketTracker/`. Stack matches BaianaBot (Python +
Playwright), so login/session handling is a copy-adapt, not a from-scratch.

## 5. The scraper in detail

### 5.1 Login + session (LOCKED 2026-06-29: persistent profile, no stored password)
Copy BaianaBot's *actual* pattern (the plan previously misdescribed it):
- Use a **persistent Chrome profile** via
  `launch_persistent_context(user_data_dir=PROFILE_DIR, channel="chrome")`.
  The session lives in that profile dir, not a cookie JSON, not a `.env`.
- `python cricket_scraper.py --login` opens a **visible** Chrome at
  `https://bnhcc.play-cricket.com/users/sign_in`; Aadi logs in by hand once,
  closes the window, session persists. **No Play-Cricket password stored
  anywhere** (more secure and less code than form-fill from `.env`).
- Normal runs launch the same profile **headless** and reuse the session; only
  re-run `--login` when the session is dead.
- `PROFILE_DIR` must be gitignored (it holds the live session).

### 5.2 Match discovery (all-time BNHCC)
- Aadi's player ID is **5464998** (from the stats URL).
- Discovery step maps, once, how Play-Cricket lists a player's matches:
  candidates are the player profile page, or the per-season batting/bowling
  breakdown tables (which link to individual scorecards), or the club results
  list filtered to matches he appears in. The first build task is a 15-minute
  reconnaissance of the logged-in DOM to pick the cleanest list. (Marked as a
  ponytail discovery task — don't over-design before seeing the real pages.)
- Output: a de-duplicated set of scorecard URLs + their match IDs.

### 5.3 Per-scorecard parsing
For one `/website/results/<id>` page, Playwright renders the SCORECARD tab and
we extract:
- **Match context**: date, competition (e.g. FRIENDLY), venue, home/away,
  which BNHCC XI (Sunday XI / Saturday 1st XI / etc.), opponent, toss, result,
  margin, team total/wickets/overs.
- **Aadi's batting row** (find "Kalwani"): position, runs, balls, 4s, 6s,
  strike rate, dismissal type (not out / bowled / caught / lbw / run out /
  stumped) and the bowler/fielder where shown.
- **Aadi's bowling row** (if he bowled): overs, maidens, runs, wickets,
  economy, wides, no-balls.
- **Aadi's fielding**: catches, stumpings, run-outs — parsed from the
  opposition's dismissal strings ("c Kalwani b ...", "st Kalwani", "run out
  (Kalwani)").

### 5.4 Output contract
A single flat dict per game keyed by the final sheet columns (§6). Missing
disciplines become explicit blanks (DNB = did not bat, no bowling = blank, not
NaN). This is the only interface the sheet writer depends on.

## 6. Google Sheet design

### Tab 1 — "Log" (one row per game, source of truth)
Proposed columns (TO BE RECONCILED with the actual Notion columns in §2):

| Group | Columns |
|---|---|
| Key | MatchID (hidden, = scorecard id, used for dedup) |
| Context | Date, Season, Competition, Team (which XI), Opponent, Venue (H/A), Toss, Result, Margin |
| Batting | Bat Pos, Runs, Balls, 4s, 6s, SR, How Out |
| Bowling | Overs, Maidens, Runs Conceded, Wickets, Econ, Wides, No-balls |
| Fielding | Catches, Stumpings, Run-outs |
| Meta | Scorecard URL, Notes |

Column policy (decided 2026-06-28): **mirror the Notion columns exactly first**
(clean 1:1 migration), then **extend** with the richer fields Play-Cricket
exposes that Notion lacks (balls, SR, economy, wides/no-balls, etc.). Empty
disciplines render as **blank** cells, never zeros or "DNB".

### Tab 2 — "Summary" (career stats) — DEFERRED
Not in the initial build. Aadi wants the per-game Log first; the computed
career-stats tab (batting/bowling/fielding aggregates via `SUM`/`AVERAGEIF`/
`COUNTIF`/`MAXIFS` formulas over the Log) is a later add-on. Logged in memory
so it isn't lost. The Log is designed now so those formulas drop in cleanly
later (e.g. a Not-Out column exists so a future batting average is correct).

## 7. Triggers / UX (the /cricket skill)

A skill at `~/.claude/skills/cricket/` with two modes:

- **Paste-link**: "log this: <scorecard URL>" → scrape that one game, dedup,
  append, confirm the row. Fast, no full crawl.
- **On-demand sync**: "update my cricket sheet" → discover all BNHCC matches,
  diff against MatchIDs already in the sheet, scrape + append only the new ones,
  report what was added.

No scheduled/cron mode (per the interview). Idempotent either way.

## 8. Dedup / idempotency
- MatchID column is the unique key.
- Before appending, read existing MatchIDs; skip any already present.
- Re-running a sync or re-pasting a URL never double-writes.

## 9. Edge cases & failure modes
- DNB / didn't bowl / didn't field → explicit blanks, not zeros (a 0 average
  is wrong; a blank is "didn't bat").
- Not-out innings → excluded from batting-average denominator (the NO column
  drives the formula).
- Match in progress / no scorecard yet → skip, report "not finalised".
- Two-innings games (rare in club cricket) → sum both innings into the row, or
  flag for manual review; decide when we first hit one.
- Name collision (another Kalwani) → match on player ID link in the scorecard,
  not just surname text, where the DOM exposes it.
- Session expired mid-run → re-login once, retry; if still failing, stop and
  report (BaianaBot-style: leave the browser/error visible).
- Play-Cricket HTML changes → parser is isolated in one module so a fix is
  localised; the skill surfaces a clear "parse failed on field X" message.

## 10. Notion → Sheets migration (one-time)
1. Read the Notion cricket database via the Notion MCP (needs auth).
2. Map each Notion property to the locked Log columns (§6 reconciled).
3. Backfill MatchID where a Notion row matches a Play-Cricket scorecard; leave
   blank where the historic row predates Play-Cricket data (still kept).
4. Write all historic rows into the Log tab via the sheets proxy.
5. Spot-check 3-4 rows against Notion + against the live scorecards.
6. Notion DB left untouched as a backup until Aadi confirms parity.

## 11. Build phases (ordered, each independently shippable)
- **P0** — Read Notion DB; lock the Log column list (mirror Notion, then
  extend); build the empty Sheet with the Log tab only. Summary tab deferred.
- **P1** — Scraper login + session reuse (`--login`), verified against the
  real account.
- **P2** — Single-scorecard parser → correct dict for one known game
  (validate against a scorecard Aadi eyeballs).
- **P3** — Sheet writer + dedup; wire P2 → append one row end to end.
- **P4** — Match discovery (all-time BNHCC) + full sync; backfill every game.
- **P5** — Migrate historic Notion rows; reconcile + spot-check.
- **P6** — Wrap as the /cricket skill (paste-link + on-demand modes).

Each phase leaves one runnable check behind (a known scorecard → expected dict,
a known MatchID → no duplicate, etc.).

## 12. Reuse leverage (don't rebuild)
- **BaianaBot** (`~/Documents/BaianaBot/`): Playwright login, cookie-session
  persistence, `--login` refresh flag, "leave browser open on failure" debug
  pattern. Copy-adapt.
- **sheet-edit skill + $CLAUDE_SHEETS_URL proxy**: writing/reading the Sheet is
  already solved; no new Google API code.
- **Notion MCP**: one-time read for the migration.

## 13. Risks / open questions
- Exact Notion columns (resolved at P0).
- Play-Cricket's logged-in DOM for the player match list (resolved by the P1
  recon).
- Whether Aadi wants the Summary tab at all, or only the per-game Log.
- Whether "Team" should be a clean enum (Sunday XI, Sat 1st XI...) for the
  Summary tab's per-team splits.
```
