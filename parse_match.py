"""Pure parsing of a ResultsVault match JSON into one flat sheet row for Aadi.

No I/O, no Playwright — just dict in, dict out, so it's trivially testable.
The match JSON comes from the public ResultsVault API that the Play-Cricket
scorecard widget calls (see cricket_scraper.harvest_match_json).

Aadi's stable identity across all matches is his Play-Cricket id (external_id).
"""

import re
from datetime import datetime, timedelta, timezone

AADI_EXTERNAL_ID = "5464998"

# ResultsVault dismissal_id -> label. Stored as free text in the Sheet (not bound
# to Notion's enum). 0 = did not bat (handled as blank), others are how-out.
DISMISSAL = {
    1: "Not Out", 2: "Caught", 3: "LBW", 4: "Bowled",
    5: "Stumped", 6: "Run Out", 7: "Hit Wicket",
}
BLANK = ""


def _to_num(v):
    return v if isinstance(v, (int, float)) else None


def parse_date1(s):
    """'/Date(1782649800000+0100)/' -> 'YYYY-MM-DD' (in the match's local offset)."""
    m = re.search(r"/Date\((\d+)([+-]\d{4})?\)/", s or "")
    if not m:
        return BLANK
    ms = int(m.group(1))
    off = m.group(2) or "+0000"
    sign = 1 if off[0] == "+" else -1
    delta = timedelta(hours=int(off[1:3]), minutes=int(off[3:5])) * sign
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc) + delta
    return dt.strftime("%Y-%m-%d")


def _overs_to_balls(overs):
    """Cricket overs (7 or 1.2 = 1 over 2 balls) -> total legal balls."""
    if overs is None:
        return 0
    whole = int(overs)
    balls = round((float(overs) - whole) * 10)
    return whole * 6 + balls


def _economy(runs, overs):
    balls = _overs_to_balls(overs)
    if not balls or runs is None:
        return BLANK
    return round(runs / (balls / 6), 2)


def _strike_rate(runs, balls):
    if not balls or runs is None:
        return BLANK
    return round(runs / balls * 100, 2)


SURNAME = "Kalwani"


def _in_teammembers(team):
    for tm in team.get("TeamMembers", []):
        nm = (tm.get("player_name") or "") + (tm.get("player_name2") or "") + (tm.get("player_name3") or "")
        if SURNAME in nm:
            return tm.get("player_id")
    return None


def _find_me(match, ext_id):
    """Return (batting_perf, bowling_perf, rv_player_id, my_team, opp_team).

    Finds the player by external_id in PlayerPerfs (gives bat/bowl lines), and
    ALSO by surname in TeamMembers (so field-only / DNB games where he has no
    perf are still recognised as his, with context + catches).
    """
    teams = match.get("MatchTeams", [])
    bat = bowl = rv_id = mine = None
    for team in teams:
        for inn in team.get("Innings", []):
            for pp in inn.get("PlayerPerfs", []):
                if str(pp.get("external_id")) != str(ext_id):
                    continue
                rv_id = pp.get("player_id", rv_id)
                if "overs" in pp or "wickets" in pp:  # bowling perf (opp innings)
                    bowl = pp
                else:                                  # batting perf (own innings)
                    bat = pp
    # my team: by rv_id in TeamMembers, else by surname
    for team in teams:
        tms = team.get("TeamMembers", [])
        if (rv_id and any(tm.get("player_id") == rv_id for tm in tms)):
            mine = team
            break
    if mine is None:
        for team in teams:
            tm_id = _in_teammembers(team)
            if tm_id is not None:
                mine = team
                rv_id = rv_id or tm_id
                break
    opp = next((t for t in teams if t is not mine), None)
    return bat, bowl, rv_id, mine, opp


def _count_catches(opp_team, rv_player_id):
    """Catches by Aadi = opposition batsmen caught by him (dismisser1 == his id)."""
    if not opp_team:
        return BLANK
    n = 0
    for inn in opp_team.get("Innings", []):
        for pp in inn.get("PlayerPerfs", []):
            if pp.get("dismissal_id") == 2 and pp.get("dismisser1_id") == rv_player_id:
                n += 1
    return n


def _clean_team_label(label):
    """'Sunday XI' -> 'Sunday' (drop the trailing 'XI' to match Aadi's shorthand)."""
    return re.sub(r"\s*XI$", "", label or "").strip()


def _how_out(bat):
    if not bat:
        return BLANK
    did = bat.get("dismissal_id")
    if did == 0:
        return BLANK  # did not bat
    label = DISMISSAL.get(did)
    if label == "Caught":
        txt = (bat.get("dismissal_text") or "").lower()
        if re.search(r"\bc ?(and|&) ?b\b|c & b|c and b", txt):
            return "C&B"
    return label or (bat.get("dismissal_text") or BLANK)


def player_in_match(match, ext_id=AADI_EXTERNAL_ID):
    """True if the player appears in this match (perf or squad)."""
    _, _, _, mine, _ = _find_me(match, ext_id)
    return mine is not None


def parse_match(match, ext_id=AADI_EXTERNAL_ID, scorecard_url=BLANK):
    """ResultsVault match dict -> one flat row dict keyed by Sheet columns.

    Mirrors the Notion 'Cricket Log' columns first, then extends with the richer
    Play-Cricket fields. Absent disciplines (DNB / didn't bowl) are blank, not 0.
    """
    bat, bowl, rv_id, mine, opp = _find_me(match, ext_id)

    # batting (blank if did not bat)
    batted = bool(bat) and bat.get("dismissal_id") != 0
    runs = _to_num(bat.get("runs")) if batted else None
    balls = _to_num(bat.get("balls")) if batted else None

    # bowling (blank if did not bowl)
    bowled = bool(bowl)
    b_runs = _to_num(bowl.get("runs")) if bowled else None
    overs = bowl.get("overs") if bowled else None

    opp_name = (opp or {}).get("club_name", BLANK)
    result_text = match.get("leader_text", BLANK)
    margin = BLANK
    mm = re.search(r"won by (.+)$", result_text or "")
    if mm:
        margin = mm.group(1).strip()

    toss = match.get("toss_won_by", "") or ""
    toss_mine = "Won" if (mine and mine.get("club_name", "") and mine["club_name"] in toss) else (
        "Lost" if toss else BLANK)

    row = {
        # --- mirror of Notion columns ---
        "Date": parse_date1(match.get("date1")),
        "completed/accurate?": "Yes",  # sourced from the official scorecard
        "Team": _clean_team_label((mine or {}).get("team_label", "")),
        "Opposition": opp_name,
        "Batting": _how_out(bat),
        "Runs": runs if runs is not None else BLANK,
        "Balls": balls if balls is not None else BLANK,
        "4s": _to_num(bat.get("fours")) if batted else BLANK,
        "6s": _to_num(bat.get("sixes")) if batted else BLANK,
        "Strike Rate": _strike_rate(runs, balls) if batted else BLANK,
        "Notes / Memory Trigger / Game Review": BLANK,  # Aadi's own text, not in API
        "Overs": overs if bowled else BLANK,
        "Maidens": _to_num(bowl.get("maidens")) if bowled else BLANK,
        "Runs Given": b_runs if bowled else BLANK,
        "Wickets": _to_num(bowl.get("wickets")) if bowled else BLANK,
        "Wides": _to_num(bowl.get("wides")) if bowled else BLANK,
        "No-Balls": _to_num(bowl.get("no_balls")) if bowled else BLANK,
        "Economy": _economy(b_runs, overs) if bowled else BLANK,
        "Catches": _count_catches(opp, rv_id),
        "Drops": BLANK,  # not in the API
        "Video?": BLANK,
        # --- Play-Cricket extensions (not in Notion) ---
        "MatchID": match.get("external_match_id", BLANK),
        "Season": match.get("season_name", BLANK),
        "Competition": match.get("grade_name", BLANK),
        "Venue": match.get("venue_name", BLANK),
        "H/A": "H" if (mine and mine.get("is_home")) else "A" if mine else BLANK,
        "Toss": toss_mine,
        "Result": result_text,
        "Margin": margin,
        "Bat Pos": _to_num(bat.get("number")) if batted else BLANK,
        "Opponent Full": (opp or {}).get("club_name", BLANK),
        "Scorecard URL": scorecard_url,
    }
    return row


# Column order for the Sheet (Notion mirror, then extensions).
COLUMNS = [
    "Date", "completed/accurate?", "Team", "Opposition", "Batting", "Runs",
    "Balls", "4s", "6s", "Strike Rate", "Notes / Memory Trigger / Game Review",
    "Overs", "Maidens", "Runs Given", "Wickets", "Wides", "No-Balls", "Economy",
    "Catches", "Drops", "Video?",
    "MatchID", "Season", "Competition", "Venue", "H/A", "Toss", "Result",
    "Margin", "Bat Pos", "Scorecard URL",
]
