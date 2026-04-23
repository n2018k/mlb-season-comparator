GLOSSARY = {
    # Pitching
    "ERA": (
        "Earned Run Average — the average number of earned runs a pitcher allows per 9 innings. "
        "Lower is better. Under 3.00 is excellent; above 5.00 is poor."
    ),
    "WHIP": (
        "Walks + Hits per Inning Pitched — measures how many baserunners a pitcher allows per inning. "
        "Lower is better. Under 1.10 is excellent; above 1.40 is poor."
    ),
    "K9": (
        "Strikeouts per 9 innings — how many batters a pitcher strikes out per 9 innings pitched. "
        "Higher is better. Above 9.0 is elite."
    ),
    "BB9": (
        "Walks per 9 innings — how many batters a pitcher walks per 9 innings pitched. "
        "Lower is better. Under 2.5 is good control."
    ),
    "IP": (
        "Innings Pitched — total innings a pitcher has thrown. Recorded in thirds: "
        "20.1 means 20 innings and 1 out, 20.2 means 20 innings and 2 outs."
    ),
    "QS": (
        "Quality Start — a start in which the pitcher goes at least 6 innings "
        "and allows 3 or fewer earned runs."
    ),
    "QS_PCT": (
        "Quality Start Percentage — share of starts that were Quality Starts. "
        "Higher is better. 0.600 or above is considered strong."
    ),
    "STARTER": (
        "Starting Pitcher — takes the mound at the beginning of the game. "
        "Typically pitches 5–7 innings and is responsible for setting the tone of the game. "
        "Tracked separately from relievers because their workload and role differ significantly."
    ),
    "BULLPEN": (
        "Bullpen / Relief Pitcher — enters the game after the starter exits. "
        "Usually pitches 1–3 innings per appearance. Includes middle relievers, setup men, and closers. "
        "Bullpen ERA and WHIP are tracked separately from starters."
    ),
    "BULLPEN_ERA": (
        "Bullpen ERA — Earned Run Average for relief pitchers only, excluding the starting pitcher. "
        "Reflects how well the team's relievers have performed."
    ),

    # Batting
    "AB": (
        "At-Bats — the number of times a batter officially faced the pitcher, "
        "excluding walks, hit-by-pitches, sacrifices, and catcher's interference."
    ),
    "H": (
        "Hits — times the batter reached base safely via a single, double, triple, or home run."
    ),
    "HR": (
        "Home Runs — times the batter hit the ball out of the park for an automatic score. "
        "One of the most valuable offensive events in baseball."
    ),
    "RBI": (
        "Runs Batted In — number of runners (including the batter on a home run) "
        "who scored as a direct result of the batter's plate appearance."
    ),
    "BB": (
        "Walks (Base on Balls) — times the pitcher threw 4 balls before the batter swung, "
        "allowing the batter to reach first base automatically."
    ),
    "K": (
        "Strikeouts — times the batter was retired by accumulating 3 strikes. "
        "High K totals can indicate a batter who makes less contact."
    ),
    "AVG": (
        "Batting Average — hits divided by at-bats. The most traditional measure of hitting. "
        "Above .300 is excellent; below .220 is poor."
    ),
    "OBP": (
        "On-Base Percentage — how often a batter reaches base by any means "
        "(hits, walks, or hit-by-pitch) divided by plate appearances. "
        "Considered more complete than AVG. Above .350 is very good."
    ),
    "OPS": (
        "On-Base Plus Slugging — OBP added to Slugging Percentage. "
        "A quick all-in-one offensive measure. Above .800 is good; above .900 is excellent."
    ),

    # Team
    "WIN_PCT": (
        "Win Percentage — share of games won. Calculated as wins divided by games played."
    ),
    "RUN_DIFF": (
        "Run Differential — total runs scored minus total runs allowed. "
        "A positive number means the team is outscoring opponents. "
        "A strong predictor of true team quality beyond win-loss record."
    ),
}


def glossary_label(key: str) -> str:
    return GLOSSARY.get(key, "")
