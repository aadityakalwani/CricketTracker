"""Build the 'Summary' tab: career stats as native Google Sheets formulas over
the Log tab. No Apps Script, recalculates live as Log changes.

Usage: python build_summary.py <sheetId>

Log column letters used: E=Batting(how out) F=Runs G=Balls H=4s I=6s
L=Overs M=Maidens N=RunsConceded O=Wickets P=Wides Q=NoBalls S=Catches
T=Drops W=Season C=Team A=Date.
"""

import sys
sys.path.insert(0, ".")
import sheet

SID = sys.argv[1]
TAB = "Summary"

# label, formula  (formulas reference the Log tab; B34 holds total bowling balls)
BLOCK = [
    ["🏏 CAREER SUMMARY", ""],
    ["", ""],
    ["BATTING", ""],
    ["Games", "=COUNTA(Log!A2:A)"],
    ["Innings", "=COUNT(Log!F2:F)"],
    ["Not Outs", '=COUNTIF(Log!E2:E,"Not Out")+COUNTIF(Log!E2:E,"R.Not Out")'],
    ["Runs", "=SUM(Log!F2:F)"],
    ["Average", '=IFERROR(ROUND(B7/(B5-B6),2),"-")'],
    ["High Score", "=MAX(Log!F2:F)"],
    ["Balls", "=SUM(Log!G2:G)"],
    ["Strike Rate", '=IFERROR(ROUND(B7/B10*100,2),"-")'],
    ["Fours", "=SUM(Log!H2:H)"],
    ["Sixes", "=SUM(Log!I2:I)"],
    ["Fifties", '=COUNTIFS(Log!F2:F,">=50",Log!F2:F,"<100")'],
    ["Hundreds", '=COUNTIF(Log!F2:F,">=100")'],
    ["Ducks", '=COUNTIFS(Log!F2:F,0,Log!E2:E,"<>Not Out",Log!E2:E,"<>R.Not Out")'],
    ["", ""],
    ["BOWLING", ""],
    ["Overs", '=IFERROR(INT(B34/6)&"."&MOD(B34,6),0)'],
    ["Wickets", "=SUM(Log!O2:O)"],
    ["Runs Conceded", "=SUM(Log!N2:N)"],
    ["Maidens", "=SUM(Log!M2:M)"],
    ["Average", '=IFERROR(ROUND(B21/B20,2),"-")'],
    ["Economy", '=IFERROR(ROUND(B21/(B34/6),2),"-")'],
    ["Strike Rate", '=IFERROR(ROUND(B34/B20,1),"-")'],
    ["Best Bowling", '=IFERROR(MAX(Log!O2:O)&"/"&MINIFS(Log!N2:N,Log!O2:O,MAX(Log!O2:O)),"-")'],
    ["Wides", "=SUM(Log!P2:P)"],
    ["No-Balls", "=SUM(Log!Q2:Q)"],
    ["", ""],
    ["FIELDING", ""],
    ["Catches", "=SUM(Log!S2:S)"],
    ["Drops", "=SUM(Log!T2:T)"],
    ["", ""],
    ["(bowling balls, calc)", "=SUMPRODUCT(IFERROR(INT(Log!L2:L)*6+ROUND(MOD(Log!L2:L,1)*10,0),0))"],
]

SEASON_Q = ('=QUERY(Log!A2:AE,"select year(A), count(A), sum(F), sum(O), sum(S) '
            "where A is not null group by year(A) order by year(A) "
            "label year(A) 'Season', count(A) 'Games', sum(F) 'Runs', sum(O) 'Wkts', sum(S) 'Catches'\",0)")
TEAM_Q = ('=QUERY(Log!A2:AE,"select C, count(A), sum(F), sum(O), sum(S) '
          "where A is not null group by C order by C "
          "label C 'Team', count(A) 'Games', sum(F) 'Runs', sum(O) 'Wkts', sum(S) 'Catches'\",0)")


def main():
    tabs = [t["name"] for t in sheet.list_tabs(SID)["result"]]
    if TAB not in tabs:
        sheet.call({"action": "create_tab", "sheetId": SID, "name": TAB})
    else:
        sheet.call({"action": "clear", "sheetId": SID, "tab": TAB, "range": "A1:Z200"})
    sheet.write_values(SID, f"A1:B{len(BLOCK)}", BLOCK, tab=TAB)
    sheet.write_values(SID, "D3", [["BY SEASON"]], tab=TAB)
    sheet.write_values(SID, "D4", [[SEASON_Q]], tab=TAB)
    sheet.write_values(SID, "J3", [["BY TEAM"]], tab=TAB)
    sheet.write_values(SID, "J4", [[TEAM_Q]], tab=TAB)
    print("Summary tab built.")


if __name__ == "__main__":
    main()
