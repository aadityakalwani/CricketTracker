"""Google Sheet read/write for Cricket Tracker, via Aadi's deployed proxy.

Uses the already-deployed Apps Script web app in $CLAUDE_SHEETS_URL (the same one
the sheet-edit skill uses). It works on any sheet Aadi owns by ID, so there is
nothing to deploy or redeploy per project. No new Google API code.
"""

import json
import os
import urllib.request

from parse_match import COLUMNS

PROXY = os.environ["CLAUDE_SHEETS_URL"]
TAB = "Log"


def call(body):
    """POST a proxy action; the proxy 302-redirects to the JSON result (urllib
    follows it as a GET, which is exactly what we want)."""
    req = urllib.request.Request(
        PROXY, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        txt = r.read().decode()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return txt


def _col_letter(idx0):
    """0-based column index -> A1 letter(s)."""
    s = ""
    n = idx0 + 1
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def list_tabs(sid):
    return call({"action": "list_tabs", "sheetId": sid})


def rename_tab(sid, old, new):
    return call({"action": "rename_tab", "sheetId": sid, "old_name": old, "new_name": new})


def write_values(sid, rng, values, tab=TAB):
    return call({"action": "write", "sheetId": sid, "tab": tab, "range": rng, "values": values})


def read_range(sid, rng, tab=TAB):
    return call({"action": "read", "sheetId": sid, "tab": tab, "range": rng})


def _values(res):
    """Unwrap the proxy's {'ok':True,'result':{'values':[...]}} read response."""
    if isinstance(res, dict):
        return (res.get("result") or {}).get("values") or res.get("values") or []
    return res or []


def ensure_header(sid, tab=TAB):
    last = _col_letter(len(COLUMNS) - 1)
    write_values(sid, f"A1:{last}1", [COLUMNS], tab=tab)


def _row_list(row):
    """Dict -> list in COLUMNS order (missing keys -> blank)."""
    return [row.get(c, "") for c in COLUMNS]


def existing_match_ids(sid, tab=TAB):
    """Set of non-empty MatchID values already in the sheet (for dedup)."""
    col = _col_letter(COLUMNS.index("MatchID"))
    vals = _values(read_range(sid, f"{col}2:{col}", tab=tab))
    out = set()
    for r in (vals or []):
        v = (r[0] if isinstance(r, list) and r else r)
        if v not in (None, ""):
            out.add(str(v))
    return out


def _date_only(v):
    """'2025-09-27T00:00:00.000Z' or '2025-09-27' -> '2025-09-27'."""
    return str(v or "")[:10]


def cutoff_date(sid, tab=TAB):
    """Latest Date among rows with a BLANK MatchID (the migrated historic rows).

    A full-history sync would re-add these (they have no MatchID to dedup on), so
    the sync only appends games dated after this. Returns '' if none.
    """
    a = _values(read_range(sid, "A2:A", tab=tab))   # Date
    v = _values(read_range(sid, f"{_col_letter(COLUMNS.index('MatchID'))}2:"
                                f"{_col_letter(COLUMNS.index('MatchID'))}", tab=tab))
    best = ""
    for i, drow in enumerate(a):
        d = _date_only(drow[0] if isinstance(drow, list) and drow else drow)
        mid = ""
        if i < len(v):
            cell = v[i]
            mid = (cell[0] if isinstance(cell, list) and cell else cell) or ""
        if d and not mid:
            best = max(best, d)
    return best


def append_game(sid, row, tab=TAB, known=None):
    """Append one parsed row, skipping if its MatchID is already present.

    Returns True if written, False if skipped as a duplicate. `known` lets a
    bulk sync pass the id set once instead of re-reading per row.
    """
    mid = str(row.get("MatchID", "")).strip()
    if known is None:
        known = existing_match_ids(sid, tab=tab)
    if mid and mid in known:
        return False
    call({"action": "append", "sheetId": sid, "tab": tab, "row": _row_list(row)})
    if mid:
        known.add(mid)
    return True
