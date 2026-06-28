"""Parser check against a real harvested match (7388878, Aadi's Sunday XI game).

Run: ./.venv/bin/python tests/test_parse_match.py   (or pytest)
"""
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parse_match import parse_match  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "match_7388878.json"


def test_known_match():
    match = json.loads(FIXTURE.read_text())
    row = parse_match(match, scorecard_url="https://bnhcc.play-cricket.com/website/results/7388878")
    # batting
    assert row["Runs"] == 15, row["Runs"]
    assert row["Balls"] == 29, row["Balls"]
    assert row["4s"] == 3 and row["6s"] == 0
    assert row["Strike Rate"] == 51.72, row["Strike Rate"]
    assert row["Batting"] == "Bowled", row["Batting"]
    assert row["Bat Pos"] == 3, row["Bat Pos"]
    # bowling
    assert row["Overs"] == 7 and row["Wickets"] == 2
    assert row["Runs Given"] == 38 and row["Wides"] == 2
    assert row["Economy"] == 5.43, row["Economy"]
    # fielding (no catches in this game)
    assert row["Catches"] == 0, row["Catches"]
    # context
    assert row["MatchID"] == 7388878
    assert row["Team"] == "Sunday", row["Team"]
    assert "Old Leightonians" in row["Opposition"], row["Opposition"]
    assert row["Venue"] == "May's Bounty"
    assert row["Competition"] == "Friendly"
    assert row["Season"] == "2026"
    assert row["Date"].startswith("2026-"), row["Date"]
    assert row["H/A"] in ("H", "A")
    assert "won by" in row["Result"]


if __name__ == "__main__":
    test_known_match()
    print("OK: parse_match matches the real 7388878 scorecard")
