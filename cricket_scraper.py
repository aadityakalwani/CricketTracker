#!/usr/bin/env python3
"""Cricket Tracker scraper — Play-Cricket (BNHCC), logged in as Aadi.

Phase 1: login + session reuse only. Parsing/discovery come later (see PLAN.md).

Session model (copied from BaianaBot's real pattern, not a cookie JSON):
a persistent Chrome profile holds the logged-in session. `--login` opens a
visible Chrome so you sign in by hand once; everything else reuses that profile
headless. No Play-Cricket password is stored anywhere.

Usage:
  python cricket_scraper.py --login    # sign in by hand, once (or when session dies)
  python cricket_scraper.py --check    # headless: is the saved session still logged in?
"""

import argparse
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = str(Path(__file__).resolve().parent / ".pc-profile")
SIGNIN_URL = "https://bnhcc.play-cricket.com/users/sign_in"
# A page that renders fully only when logged in. The club home is enough to tell
# logged-in from logged-out by whether a sign-in affordance is present.
HOME_URL = "https://bnhcc.play-cricket.com/"

# Chrome launch args that stop Play-Cricket flagging automation (BaianaBot set).
_LAUNCH = dict(
    user_data_dir=PROFILE_DIR,
    channel="chrome",
    args=[
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
    ],
    ignore_default_args=["--enable-automation", "--no-sandbox"],
)


def run_login() -> None:
    """Open a visible Chrome at the sign-in page; you log in, then close the window."""
    print(f"[login] Opening Chrome (profile: {PROFILE_DIR})")
    print("[login] Sign in to Play-Cricket, then CLOSE the window to save the session.")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(headless=False, **_LAUNCH)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(SIGNIN_URL)
        try:
            ctx.wait_for_event("close", timeout=0)  # block until user closes window
        except Exception:
            pass
        try:
            ctx.close()
        except Exception:
            pass
    print("[login] Window closed. Session saved to the profile.")


def _looks_logged_out(page) -> bool:
    """True if a sign-in/log-in affordance is visible (i.e. not authenticated).

    ponytail: name-based, not a brittle CSS selector — survives DOM tweaks. If
    Play-Cricket renames the link this returns a false 'logged in'; re-run
    --login if --check ever lies. Tighten with the real selector after recon.
    """
    import re
    for name in ("Sign in", "Log in", "Login", "Sign In"):
        try:
            if page.get_by_role("link", name=re.compile(name, re.I)).first.is_visible(timeout=1500):
                return True
        except Exception:
            continue
    return False


def run_check() -> int:
    """Headless: load the site with the saved session and report login state."""
    if not Path(PROFILE_DIR).exists():
        print("[check] No profile yet. Run:  python cricket_scraper.py --login")
        return 1
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(headless=True, **_LAUNCH)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(HOME_URL, wait_until="domcontentloaded")
        shot = str(Path(__file__).resolve().parent / "debug-session.png")
        page.screenshot(path=shot, full_page=False)
        logged_out = _looks_logged_out(page)
        title = page.title()
        ctx.close()
    print(f"[check] title: {title!r}")
    print(f"[check] screenshot: {shot}")
    if logged_out:
        print("[check] LOGGED OUT (sign-in link visible). Run --login.")
        return 1
    print("[check] looks LOGGED IN.")
    return 0


RESULT_URL = "https://bnhcc.play-cricket.com/website/results/{}"
PLAYER_ID = "5464998"
DISCOVERY_PAGES = [
    f"https://bnhcc.play-cricket.com/player_stats/batting/{PLAYER_ID}",
    f"https://bnhcc.play-cricket.com/player_stats/bowling/{PLAYER_ID}",
    "https://bnhcc.play-cricket.com/",  # homepage results widget = newest games
]


RV_ORG = "130000"  # BNHCC's ResultsVault org id (constant for the club)
RV_MATCH = "https://api.resultsvault.co.uk/rv/{org}/matches/{rvid}/?apiid=1003&strmflg=3"


def _harvest_on_page(page, url: str) -> dict:
    """Return a match's ResultsVault JSON, regardless of scorecard-widget flavour.

    Every results page (friendly or league) fires a `/rv/mappings/...` call that
    (a) carries the `x-ias-api-request` auth header and (b) returns the RV match id
    in `object_id1`. We capture both, then fetch the /matches/ endpoint directly in
    the page (so the auth header + cookies apply). No tab-clicking, no widget race.
    """
    cap = {}

    def on_req(r):
        if "/rv/mappings/" in r.url:
            cap["hdr"] = r.headers.get("x-ias-api-request")

    def on_resp(r):
        if "/rv/mappings/" in r.url and r.status == 200:
            try:
                cap["map"] = r.json()
            except Exception:
                pass

    page.on("request", on_req)
    page.on("response", on_resp)
    try:
        page.goto(url, wait_until="domcontentloaded")
        # Two widget flavours: league pages fire the mapping on load; older
        # friendly pages only fire it once the Scorecard tab is activated. Click
        # best-effort to cover the latter; harmless where the tab is absent.
        for sel in ("#iasScorecardtab-tab", "a[href='#iasScorecardtab']", "text=Scorecard"):
            try:
                page.click(sel, timeout=2000)
                break
            except Exception:
                continue
        for _ in range(24):  # poll up to ~12s for the mapping call
            if cap.get("hdr") and cap.get("map"):
                break
            page.wait_for_timeout(500)
        if not (cap.get("hdr") and cap.get("map")):
            raise RuntimeError(f"mapping not captured for {url}")
        rvid = cap["map"].get("object_id1")
        if not rvid:
            raise RuntimeError(f"no RV match id in mapping for {url}")
        res = page.evaluate(
            """async ([u, h]) => {
                const r = await fetch(u, {headers: {'x-ias-api-request': h, 'accept': 'application/json'}});
                return {status: r.status, text: await r.text()};
            }""",
            [RV_MATCH.format(org=RV_ORG, rvid=rvid), cap["hdr"]],
        )
        if res["status"] != 200:
            raise RuntimeError(f"matches fetch HTTP {res['status']} for {url}")
        return json.loads(res["text"])
    finally:
        page.remove_listener("request", on_req)
        page.remove_listener("response", on_resp)


def _harvest_fresh(ctx, url: str, retries: int = 1) -> dict:
    """Harvest on a brand-new page (avoids stale widget-JS state that makes a
    reused page intermittently miss the mapping call), retrying once."""
    last = None
    for _ in range(retries + 1):
        page = ctx.new_page()
        try:
            return _harvest_on_page(page, url)
        except Exception as e:
            last = e
        finally:
            page.close()
    raise last


def harvest_match_json(url: str) -> dict:
    """Standalone (own browser) harvest of one match's JSON."""
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(headless=True, **_LAUNCH)
        try:
            return _harvest_fresh(ctx, url)
        finally:
            ctx.close()


def discover_ids(page) -> set:
    """Collect candidate scorecard ids from the player_stats pages + homepage."""
    import re
    ids = set()
    for url in DISCOVERY_PAGES:
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            ids |= set(re.findall(r"/website/results/(\d+)", page.content()))
        except Exception as e:
            print(f"[discover] {url} failed: {e}")
    return ids


def run_game(url: str) -> int:
    """Scrape + parse one scorecard, print the flat row dict."""
    import json
    from parse_match import parse_match
    row = parse_match(harvest_match_json(url), scorecard_url=url)
    print(json.dumps(row, indent=2, ensure_ascii=False))
    return 0


def run_sync(extra_ids=None) -> int:
    """Discover Aadi's games, append any not already in the Sheet and newer than
    the latest migrated (blank-MatchID) row. Idempotent; safe to re-run."""
    from parse_match import parse_match, player_in_match
    import sheet

    sid = os.environ.get("CRICKET_SHEET_ID", "1XyMrLZq5XSJ-65acMeqxAL42iFfp1jl0YhNc4GYNTRc")
    known = sheet.existing_match_ids(sid)
    cutoff = sheet.cutoff_date(sid)
    print(f"[sync] sheet has {len(known)} MatchIDs; cutoff (latest un-IDed row) = {cutoff or 'none'}")

    added = []
    skipped = {"dup": 0, "historic": 0, "not_aadi": 0, "no_scorecard": 0, "error": 0}
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(headless=True, **_LAUNCH)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        ids = discover_ids(page)
        ids |= set(str(i) for i in (extra_ids or []))
        print(f"[sync] {len(ids)} candidate scorecards discovered")
        for mid in sorted(ids):
            if mid in known:
                skipped["dup"] += 1
                continue
            try:
                match = _harvest_fresh(ctx, RESULT_URL.format(mid))
            except Exception as e:
                # Pages without a published scorecard widget have no JSON to fetch
                # — a normal skip, not a failure.
                if "mapping not captured" in str(e):
                    skipped["no_scorecard"] += 1
                else:
                    skipped["error"] += 1
                    print(f"[sync] {mid}: harvest failed ({e})")
                continue
            if not player_in_match(match):
                skipped["not_aadi"] += 1
                continue
            row = parse_match(match, scorecard_url=RESULT_URL.format(mid))
            if cutoff and str(row["Date"])[:10] <= cutoff:
                skipped["historic"] += 1
                continue
            if sheet.append_game(sid, row, known=known):
                added.append((row["Date"], row["Team"], row["Opposition"], mid))
                print(f"[sync] + added {row['Date']} {row['Team']} v {row['Opposition']} ({mid})")
        ctx.close()
    print(f"\n[sync] done. added={len(added)} dup={skipped['dup']} "
          f"historic={skipped['historic']} not_aadi={skipped['not_aadi']} "
          f"no_scorecard={skipped['no_scorecard']} error={skipped['error']}")
    return 0


def run_dump(url: str) -> int:
    """Recon: load a page with the saved session, save its HTML + screenshot.

    ponytail: throwaway helper for building the parser against the real DOM.
    Remove once P2 parsing is stable.
    """
    out = Path(__file__).resolve().parent
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(headless=True, **_LAUNCH)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_selector("table", timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(1500)
        html = page.content()
        slug = url.rstrip("/").split("/")[-1] or "page"
        (out / f"debug-{slug}.html").write_text(html, encoding="utf-8")
        page.screenshot(path=str(out / f"debug-{slug}.png"), full_page=True)
        ntables = len(page.query_selector_all("table"))
        title = page.title()
        ctx.close()
    print(f"[dump] title: {title!r}")
    print(f"[dump] saved debug-{slug}.html ({len(html)} bytes), debug-{slug}.png; {ntables} <table>s")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Cricket Tracker scraper (Phase 1: login/session)")
    ap.add_argument("--login", action="store_true", help="sign in by hand once")
    ap.add_argument("--check", action="store_true", help="report whether the saved session is logged in")
    ap.add_argument("--game", metavar="URL", help="scrape + parse one scorecard, print the row")
    ap.add_argument("--sync", action="store_true", help="discover + append new games to the Sheet")
    ap.add_argument("--ids", metavar="A,B,C", help="extra scorecard ids to include in --sync")
    ap.add_argument("--dump", metavar="URL", help="recon: save a page's HTML + screenshot")
    args = ap.parse_args()
    if args.login:
        run_login()
        return 0
    if args.check:
        return run_check()
    if args.game:
        return run_game(args.game)
    if args.sync:
        extra = [s.strip() for s in (args.ids or "").split(",") if s.strip()]
        return run_sync(extra_ids=extra)
    if args.dump:
        return run_dump(args.dump)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
