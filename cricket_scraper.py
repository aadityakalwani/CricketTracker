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


def main() -> int:
    ap = argparse.ArgumentParser(description="Cricket Tracker scraper (Phase 1: login/session)")
    ap.add_argument("--login", action="store_true", help="sign in by hand once")
    ap.add_argument("--check", action="store_true", help="report whether the saved session is logged in")
    args = ap.parse_args()
    if args.login:
        run_login()
        return 0
    if args.check:
        return run_check()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
