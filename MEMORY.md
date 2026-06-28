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

## Next priorities
1. P4: discover all Aadi's BNHCC scorecard URLs (player 5464998) → bulk sync
   (harvest+parse+append_game each, skipping dupes). Needs DOM recon of how
   Play-Cricket lists a player's matches.
2. Backfill MatchID onto historic rows where a Notion row matches a real
   scorecard (plan §10.3 reconciliation) — deferred.
3. P6: wrap as /cricket skill (paste-link + on-demand sync).
4. Summary/stats tab: native sheet formulas (deferred, Log-only for now).
