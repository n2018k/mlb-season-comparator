import requests
import pandas as pd
from datetime import datetime

# -------------------------------------------------------------------
# TEAM ID LOOKUP
# MLB Stats API uses numeric IDs not abbreviations.
# This maps the abbreviations you'll pick in the UI to their API IDs.
# -------------------------------------------------------------------
TEAM_IDS = {
    "ARI": 109, "ATL": 144, "BAL": 110, "BOS": 111, "CHC": 112,
    "CWS": 145, "CIN": 113, "CLE": 114, "COL": 115, "DET": 116,
    "HOU": 117, "KC":  118, "LAA": 108, "LAD": 119, "MIA": 146,
    "MIL": 158, "MIN": 142, "NYM": 121, "NYY": 147, "OAK": 133,
    "PHI": 143, "PIT": 134, "SD":  135, "SF":  137, "SEA": 136,
    "STL": 138, "TB":  139, "TEX": 140, "TOR": 141, "WSH": 120,
}

BASE_URL = "https://statsapi.mlb.com/api/v1"


def get_team_id(team_abbr: str) -> int:
    """Convert team abbreviation like OAK to the MLB API numeric ID."""
    team_id = TEAM_IDS.get(team_abbr.upper())
    if not team_id:
        raise ValueError(f"Unknown team abbreviation: {team_abbr}")
    return team_id


def fetch_game_schedule(team_abbr: str, season: int) -> tuple[list, bool]:
    """
    Pull the full regular season schedule for a team.
    Returns:
        - list of completed game dicts in chronological order
        - bool: True if the season is still in progress
    
    For completed seasons this is the full 162 game schedule.
    For 2026 (current season) this only returns games marked Final.
    """
    team_id = get_team_id(team_abbr)
    url = (
        f"{BASE_URL}/schedule"
        f"?sportId=1"
        f"&teamId={team_id}"
        f"&season={season}"
        f"&gameType=R"
        f"&fields=dates,date,games,gamePk,status,abstractGameState"
    )
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()

    completed_games = []
    total_scheduled = 0

    for date_block in data.get("dates", []):
        for game in date_block.get("games", []):
            total_scheduled += 1
            if game["status"]["abstractGameState"] == "Final":
                completed_games.append({
                    "gamePk": game["gamePk"],
                    "date": date_block["date"]
                })

    completed_games.sort(key=lambda x: x["date"])

    # Season is in progress if there are scheduled games not yet Final
    season_in_progress = len(completed_games) < total_scheduled

    return completed_games, season_in_progress


def fetch_boxscore(game_pk: int, team_abbr: str) -> dict:
    """
    Pull the boxscore for a single game.
    Extracts: result (W/L), runs scored, runs allowed,
    starting pitcher, bullpen pitchers, and batting lineup with stats.
    """
    team_id = get_team_id(team_abbr)
    url = f"{BASE_URL}/game/{game_pk}/boxscore"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()

    # Figure out if our team is home or away in this game
    teams = data["teams"]
    if teams["home"]["team"]["id"] == team_id:
        our_side = teams["home"]
        opp_side = teams["away"]
    else:
        our_side = teams["away"]
        opp_side = teams["home"]

    our_runs = our_side["teamStats"]["batting"]["runs"]
    opp_runs = opp_side["teamStats"]["batting"]["runs"]
    result = "W" if our_runs > opp_runs else "L"

    # --- Pitching ---
    pitchers = our_side["pitchers"]          # list of pitcher IDs in order used
    pitcher_stats = our_side["players"]      # dict of all player stats keyed by "ID{id}"

    starter_id = pitchers[0] if pitchers else None
    bullpen_ids = pitchers[1:] if len(pitchers) > 1 else []

    def extract_pitcher(player_id):
        key = f"ID{player_id}"
        p = pitcher_stats.get(key, {})
        stats = p.get("stats", {}).get("pitching", {})
        return {
            "id": player_id,
            "name": p.get("person", {}).get("fullName", "Unknown"),
            "ip": stats.get("inningsPitched", "0.0"),
            "er": stats.get("earnedRuns", 0),
            "k": stats.get("strikeOuts", 0),
            "bb": stats.get("baseOnBalls", 0),
            "hits": stats.get("hits", 0),
        }

    starter = extract_pitcher(starter_id) if starter_id else {}
    bullpen = [extract_pitcher(pid) for pid in bullpen_ids]

    # --- Batting ---
    batters = our_side["batters"]
    batter_stats = our_side["players"]

    lineup = []
    for b_id in batters:
        key = f"ID{b_id}"
        p = batter_stats.get(key, {})
        stats = p.get("stats", {}).get("batting", {})
        at_bats = stats.get("atBats", 0)
        hits = stats.get("hits", 0)
        lineup.append({
            "id": b_id,
            "name": p.get("person", {}).get("fullName", "Unknown"),
            "ab": at_bats,
            "hits": hits,
            "hr": stats.get("homeRuns", 0),
            "rbi": stats.get("rbi", 0),
            "bb": stats.get("baseOnBalls", 0),
            "k": stats.get("strikeOuts", 0),
            "avg": round(hits / at_bats, 3) if at_bats > 0 else 0.0,
        })

    return {
        "game_pk": game_pk,
        "result": result,
        "runs_scored": our_runs,
        "runs_allowed": opp_runs,
        "starter": starter,
        "bullpen": bullpen,
        "lineup": lineup,
    }

def fetch_season_data(team_abbr: str, season: int, first_n_games: int) -> dict:
    """
    Master function. Given a team, season, and game count,
    returns everything we need for that cohort.
    
    Now also returns:
        - games_available: how many completed games actually exist
        - season_in_progress: whether the season is still being played
        - games_requested: what the user asked for
    So the UI can warn when N exceeds available games.
    """
    print(f"Fetching schedule for {team_abbr} {season}...")
    schedule, season_in_progress = fetch_game_schedule(team_abbr, season)

    games_available = len(schedule)
    games_to_fetch  = schedule[:first_n_games]
    actual_n        = len(games_to_fetch)

    if actual_n < first_n_games:
        print(
            f"  Warning: requested {first_n_games} games but only "
            f"{games_available} completed games available for {season}."
        )

    games = []
    for i, g in enumerate(games_to_fetch):
        print(f"  Fetching game {i+1}/{actual_n}: {g['date']}")
        try:
            boxscore = fetch_boxscore(g["gamePk"], team_abbr)
            boxscore["date"] = g["date"]
            boxscore["game_number"] = i + 1
            games.append(boxscore)
        except Exception as e:
            print(f"  Warning: could not fetch game {g['gamePk']}: {e}")
            continue

    return {
        "team":               team_abbr,
        "season":             season,
        "first_n_games":      actual_n,        # what we actually got
        "games_requested":    first_n_games,   # what was asked for
        "games_available":    games_available, # total completed this season
        "season_in_progress": season_in_progress,
        "games":              games,
    }

