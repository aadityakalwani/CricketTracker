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

## Blockers / next-session prerequisites
- **Notion MCP not authorised.** Notion-first order means this blocks the start.
  Aadi to run `/mcp` → authorise claude.ai Notion before next session.
- No git repo yet. First build step: `git init` + `.gitignore` (must exclude the
  Chrome profile dir, `.venv/`, `__pycache__/`, any `.env`).

## Next session priorities
1. (Aadi) Notion auth done.
2. P0: read Notion cricket DB → lock exact Log column list (mirror Notion, then extend).
3. Create fresh Sheet + Log tab; add sheet ID to skill config.
4. P5: port historic Notion rows into Log.
5. Then P1 scraper login/session.
