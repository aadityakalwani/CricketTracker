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


def harvest_match_json(url: str) -> dict:
    """Load a results page logged-in, trigger the scorecard widget, and return the
    ResultsVault match JSON it fetches. The widget supplies the auth header, so we
    just harvest its response — no token reverse-engineering, survives rotation.

    ponytail: full page load per match is slow but rock-solid. If bulk sync gets
    painful, cache the widget's x-ias-api-request header and replay over HTTP.
    """
    captured = {}

    def on_resp(r):
        if "resultsvault.co.uk" in r.url and "/matches/" in r.url and r.status == 200:
            try:
                captured["json"] = r.json()
            except Exception:
                pass

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(headless=True, **_LAUNCH)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.on("response", on_resp)
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.click("#iasScorecardtab-tab", timeout=6000)
        except Exception:
            pass
        for _ in range(20):  # poll up to ~10s for the widget's fetch
            if "json" in captured:
                break
            page.wait_for_timeout(500)
        ctx.close()
    if "json" not in captured:
        raise RuntimeError(f"scorecard JSON not captured for {url} (not finalised? not logged in?)")
    return captured["json"]


def run_game(url: str) -> int:
    """Scrape + parse one scorecard, print the flat row dict."""
    import json
    from parse_match import parse_match
    row = parse_match(harvest_match_json(url), scorecard_url=url)
    print(json.dumps(row, indent=2, ensure_ascii=False))
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
    ap.add_argument("--dump", metavar="URL", help="recon: save a page's HTML + screenshot")
    args = ap.parse_args()
    if args.login:
        run_login()
        return 0
    if args.check:
        return run_check()
    if args.game:
        return run_game(args.game)
    if args.dump:
        return run_dump(args.dump)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
