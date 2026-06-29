# CricketTracker — MEMORY

Project: scrape BNHCC Play-Cricket (logged in as Aadi) → Google Sheet Log tab,
replacing the manual Notion cricket DB. Full design in PLAN.md.

## Decisions log

### 2026-06-29 — Pre-build review + second interview
**Verified** the plan's reuse leverage (§12) before writing code:
- BaianaBot exists (`~/Documents/BaianaBot/bot.py`, own `.venv` w/ playwright). ✅
- sheet-edit skill present, `$CLAUDE_SHEETS_URL` set, append/dedup interface confirmed. ✅
- Notion MCP deferred — needs auth. ⚠️ (now the build blocker, see order below)
- Toolchain: Python 3.14, Node 26; playwright only in BaianaBot's venv → CricketTracker needs its own venv.

**Issue found + fixed:** PLAN §5.1 misdescribed BaianaBot. BaianaBot does NOT
use a cookie JSON or a `.env` password — it uses a **persistent Chrome profile**
(`launch_persistent_context(user_data_dir=...)`) + **manual `--login`** (human
logs in once in a visible browser). Account password stored nowhere.
Decision: copy that real pattern. Rejected the `.env` password approach (more
code, plaintext password on disk). PLAN §5.1 corrected.

**Interview answers (locked):**
1. Session = persistent profile + manual `--login`, no stored password.
2. Build order = SEQUENTIAL, **Notion migration first, then scraper**
   (P0 → P5 → P1-P4 → P6). Not parallel. Rejected scraper-first.
3. v1 scope = **Log tab only**; Summary/career-stats tab deferred (again).
4. Destination = **create a fresh** Google Sheet, Log tab only.

### 2026-06-29 (session 2) — Notion verified, P0 schema locked, repo + P1 built
- **Notion MCP authorised + verified** (workspace "Kalwo", Aadi). DB found:
  **"🏏 Cricket Log"**, page id `5a3fba1c-d21a-4762-9402-398e568f83d6`,
  data source `collection://f564e1a6-6724-4024-98c2-bf55447bc997`.
- **GATE FOUND:** `notion-query-data-sources` (SQL *and* view mode) requires a
  Notion Business plan + Notion AI. Aadi is not on it → **cannot bulk-read rows
  via MCP.** `fetch` gives schema only; `search` is ranked/capped, not exhaustive.
  **Migration decision:** Aadi exports the DB to CSV (Notion → ··· → Export →
  "Markdown & CSV"), drops the .csv in the repo, Claude reads it (xlsx skill) and
  pushes to the Sheet. One-time, no upgrade. Rejected MCP enumeration (gated).
- **P0 column list LOCKED** (mirror Notion exactly, in view order, then extend).
  Notion columns: Date | completed/accurate? | Team | Opposition | Batting
  (multi: Not Out, R.Not Out, Run Out, Bowled, Caught, C&B, LBW, Caught Behind)
  | Runs | Balls | 4s | 6s | Strike Rate | Notes/Memory Trigger/Game Review
  (title) | Overs | Maidens | Runs Given | Wickets | Wides | No-Balls | Economy
  | Catches | Drops | Video? (url).
  Team options: U15A, 4th, 5th, Midweek, U15B, Sunday, U15A Pairs, U17,
  Gordon's, Rotherfield Park, Development Team, Old Basing 3s, Holybourne CC, U19.
  NOTE: Notion has NO MatchID/venue/result/competition/toss/bat-pos — those are
  the Play-Cricket "extend" columns (plan §6) added after the mirror.
- **Repo PUBLIC:** github.com/aadityakalwani/CricketTracker (main). Started
  private, made public 2026-06-29 after a clean sensitive-info scan (no creds,
  no private notes). `.venv` + `.pc-profile/` (live session) gitignored.
- **Commits must NOT credit Claude** (no co-author/session trailers) — Aadi
  wants no trace of AI usage on this public repo. History was rewritten to strip
  them. Overrides the global CLAUDE.md footer rule.
- **P1 written + smoke-tested:** `cricket_scraper.py` — `--login` (visible Chrome,
  manual sign-in, persistent profile) + `--check` (headless session probe +
  debug screenshot). Imports/`--help` verified. NOT yet run against the real
  account (needs Aadi to do `--login`).

## Blockers / next steps
- **Migration data:** Aadi to export Cricket Log → CSV and drop it in the repo.
  Until then the migration (P5) waits, but scraper code can proceed.
- **P1 acceptance:** Aadi runs `./.venv/bin/python cricket_scraper.py --login`,
  signs in, then `--check` should report "looks LOGGED IN". The --check
  name-based selector is a guess (no DOM recon yet) — tighten after first run.
- **Sheet not created yet** — create fresh Google Sheet + Log tab when migrating.

### 2026-06-29 (session 3) — P2 DONE, big architecture win
- **Notion export received:** Desktop zip → `..._all.csv` = **90 games** (extracted
  to /tmp/ctexport; original zip on Desktop). This is the migration source.
- **Login verified:** Aadi ran `--login`; headless session reuse works (loaded
  authenticated pages fine).
- **ARCHITECTURE CHANGE — ResultsVault JSON, not HTML scraping.** The scorecard
  tab is an ECB widget that fetches `api.resultsvault.co.uk/rv/<org>/matches/
  <rvid>/?apiid=1003`. Auth = `x-ias-api-request` header the widget makes. We
  harvest the widget's own JSON response (no token cracking). Supersedes plan
  §3/§5.3 HTML approach. JSON has batting/bowling/fielding + full context.
- **P2 COMPLETE + verified live:** `parse_match.py` (pure, tested) +
  `cricket_scraper.py --game URL` (harvest+parse). Test fixture
  `tests/fixtures/match_7388878.json` + `tests/test_parse_match.py` pass.
  Match 7388878 → runs 15(29b), 3x4, bowled, 7-0-38-2, SR/econ computed, plus
  Toss/H-A/Venue/Margin that Notion never had.
- **Sheets approach (Aadi instruction):** NO bound/redeployed Apps Script for this
  project. Use the already-deployed generic `$CLAUDE_SHEETS_URL` proxy (works on
  any sheet by ID, no redeploy) for read/write/append; stats tab = native sheet
  formulas. "DIY in gsheets", nothing to redeploy.

### 2026-06-29 (session 4) — P3 DONE
- **Fresh Sheet created:** "🏏 Cricket Tracker", id
  `1XyMrLZq5XSJ-65acMeqxAL42iFfp1jl0YhNc4GYNTRc`, tab **Log** (header =
  parse_match.COLUMNS). https://docs.google.com/spreadsheets/d/1XyMrLZq5XSJ-65acMeqxAL42iFfp1jl0YhNc4GYNTRc/edit
- **Migration done:** 85 historic Notion games written to Log (dates normalised
  to YYYY-MM-DD → Sheets stores as real dates; extension cols blank; MatchID
  blank for historic rows). Spot-checked (Fleet 42 game OK), runs to 2025-09-27.
- **Sheet writer working + verified live:** `sheet.py` via $CLAUDE_SHEETS_URL
  proxy (no redeploy). `append_game` dedups by MatchID — append #1 True, #2
  False (idempotent). Scraped game 7388878 appended → 86 rows.
- **Aadi instruction:** commit to git incrementally as we go.

### 2026-06-29 (session 5) — P4 harvester + sync working (discovery still partial)
- **Two scorecard widget types** (key gotcha): league result pages fire the
  `/rv/mappings/` call on load; older friendly pages only fire it after the
  Scorecard tab is clicked. Harvester now: capture mapping request header
  (`x-ias-api-request`) + response (`object_id1` = RV match id), then fetch
  `/rv/130000/matches/<rvid>/` directly. Best-effort tab click covers old widget.
  Fresh page per harvest + 1 retry. Verified live on friendly (7388878, 7276686)
  AND league (7276745: Div 6E, 2 catches, won by 83).
- **`--sync` works:** added 7276686 + 7276745 (post-cutoff, deduped by MatchID,
  cutoff=2025-09-26). Sheet now has 88 rows (85 migrated + 3 synced).
- **Known limits:** (a) ~20 of 45 candidate pages have NO published scorecard
  widget (no data-match-id) → `no_scorecard` skip, nothing to fetch. Some are
  recent games Aadi played (e.g. 7238048, he scored 3 per player_stats) → a real
  gap with no JSON source on the club page. (b) Discovery is partial:
  player_stats links are per-SEASON-SUMMARY not per-game, and /Matches is JS/AJAX
  (uncracked). So full all-time/league auto-discovery NOT solved — see
  OPEN_QUESTIONS.md Q1. Paste-link / `--sync --ids` is the reliable add path.

### 2026-06-29 (session 6) — FULL CAREER BACKFILL done
- Aadi gave URLs for all ~84 career games (2021-2026). Decision: scraped
  scorecard data is authoritative; Notion was rough ("barbs"). Backfilled all.
- **backfill.py** (async, one logged-in browser + N tabs; subagents can't help —
  they'd fight the single profile lock). conc=4 reliable; conc=8 caused timeouts.
- **parse_match fix:** detect player via TeamMembers surname too → field-only/DNB
  games (21 of them) now captured with context + catches, not just bat/bowl.
- **reconcile.py:** scraped stats + Notion notes/video/drops merged BY DATE;
  no-scorecard games kept as handwritten rows; Log rewritten sorted by date.
- **Result: Log = 94 games** (52 scorecard-accurate w/ MatchID + 42
  handwritten-only). 70 have notes. 31 games have NO published scorecard
  (kept handwritten). 1 not_aadi (5099973 — harvested but no Kalwani in
  perfs/squad; maybe wrong URL or name variant; left out, kept its Notion row).
- **Known caveat:** notes merge by exact date; where Aadi's handwritten date was
  a day off, a note can sit on the adjacent game. Stats always accurate.

### 2026-06-29 (session 7) — Summary/stats tab DONE
- **build_summary.py** builds a "Summary" tab: native sheet formulas over Log
  (no Apps Script). Batting (innings/NO/runs/avg/HS/SR/4s/6s/50s/100s/ducks),
  Bowling (overs via balls-conversion/wkts/runs/maidens/avg/econ/SR/best/wides/
  nb), Fielding (catches/drops), + by-season (group year(date)) and by-team
  QUERY tables.
- Headline career: 604 runs @16.32 (HS 57, SR 80, 2 fifties); 61 wkts @20.03
  (econ 5.25, best 5/12); 37 catches; across 94 games.
- Fixed: team labels normalised "Under 15B"->"U15B" (parse_match + in-place);
  by-season uses year(Date) so handwritten rows (blank Season col) are included.
- Sheet now: Log (94 games) + Summary. Project essentially complete bar P6.

## Next priorities
1. P4: discover all Aadi's BNHCC scorecard URLs (player 5464998) → bulk sync
   (harvest+parse+append_game each, skipping dupes). Needs DOM recon of how
   Play-Cricket lists a player's matches.
2. Backfill MatchID onto historic rows where a Notion row matches a real
   scorecard (plan §10.3 reconciliation) — deferred.
3. P6: wrap as /cricket skill (paste-link + on-demand sync).
4. Summary/stats tab: native sheet formulas (deferred, Log-only for now).
