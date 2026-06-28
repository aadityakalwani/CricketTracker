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
- **Repo created PRIVATE:** github.com/aadityakalwani/CricketTracker (main).
  .venv gitignored; `.pc-profile/` (live session) gitignored.
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

## Next session priorities
1. (Aadi) run `--login` to verify the session works; export Notion CSV.
2. P2: single-scorecard parser (needs a real scorecard URL from Aadi to target).
3. Create fresh Sheet + Log tab (headers = locked columns above); migrate CSV.
4. P3 sheet writer + dedup; P4 discovery; P6 /cricket skill.
