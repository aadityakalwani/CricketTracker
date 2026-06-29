"""Async bulk harvest of many scorecards into parsed rows (one logged-in browser,
N concurrent tabs). Writes {MatchID: row} JSON for the reconcile step.

Subagents can't parallelise this: they'd each need the single logged-in Chrome
profile and deadlock on its lock. Concurrent tabs in one browser is the right
parallelism. Usage: python backfill.py <ids_file> <out_json> [concurrency]
"""

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_match import parse_match, player_in_match  # noqa: E402

PROFILE_DIR = str(Path(__file__).resolve().parent / ".pc-profile")
RESULT_URL = "https://bnhcc.play-cricket.com/website/results/{}"
RV_MATCH = "https://api.resultsvault.co.uk/rv/130000/matches/{rvid}/?apiid=1003&strmflg=3"
_ARGS = ["--no-first-run", "--no-default-browser-check", "--disable-blink-features=AutomationControlled"]
_IGNORE = ["--enable-automation", "--no-sandbox"]


async def harvest(ctx, mid, sem, results, status):
    url = RESULT_URL.format(mid)
    async with sem:
        page = await ctx.new_page()
        try:
            try:
                async with page.expect_response(
                    lambda r: "/rv/mappings/" in r.url and r.status == 200, timeout=25000
                ) as ri:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    for sel in ("#iasScorecardtab-tab", "a[href='#iasScorecardtab']", "text=Scorecard"):
                        try:
                            await page.click(sel, timeout=2000)
                            break
                        except Exception:
                            continue
                resp = await ri.value
            except Exception:
                status[mid] = "no_scorecard"
                return
            mapping = await resp.json()
            hdr = resp.request.headers.get("x-ias-api-request")
            rvid = mapping.get("object_id1")
            if not (hdr and rvid):
                status[mid] = "no_scorecard"
                return
            res = await page.evaluate(
                """async ([u, h]) => {
                    const r = await fetch(u, {headers: {'x-ias-api-request': h, 'accept': 'application/json'}});
                    return {status: r.status, text: await r.text()};
                }""",
                [RV_MATCH.format(rvid=rvid), hdr],
            )
            if res["status"] != 200:
                status[mid] = f"http_{res['status']}"
                return
            match = json.loads(res["text"])
            if not player_in_match(match):
                status[mid] = "not_aadi"
                return
            results[str(mid)] = parse_match(match, scorecard_url=url)
            status[mid] = "ok"
            print(f"  ok {mid}: {results[str(mid)]['Date']} {results[str(mid)]['Team']} v {results[str(mid)]['Opposition']}", flush=True)
        except Exception as e:
            status[mid] = f"error: {e}"
        finally:
            await page.close()


async def main():
    ids_file, out_json = sys.argv[1], sys.argv[2]
    conc = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    ids = [l.strip() for l in Path(ids_file).read_text().splitlines() if l.strip()]
    ids = list(dict.fromkeys(ids))  # dedupe, keep order
    print(f"harvesting {len(ids)} games, concurrency {conc}")
    results, status = {}, {}
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            PROFILE_DIR, headless=True, channel="chrome", args=_ARGS, ignore_default_args=_IGNORE
        )
        sem = asyncio.Semaphore(conc)
        await asyncio.gather(*(harvest(ctx, mid, sem, results, status) for mid in ids))
        await ctx.close()
    Path(out_json).write_text(json.dumps(results, indent=1, ensure_ascii=False))
    from collections import Counter
    tally = Counter(v if v in ("ok", "no_scorecard", "not_aadi") else "error" for v in status.values())
    print(f"\nDONE: {dict(tally)} | wrote {len(results)} rows to {out_json}")
    bad = {m: s for m, s in status.items() if s != "ok"}
    if bad:
        print("non-ok:", json.dumps(bad, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
