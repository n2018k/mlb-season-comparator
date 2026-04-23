import pandas as pd
from collections import defaultdict


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def safe_divide(numerator, denominator, decimals=3):
    """Division that returns 0.0 instead of crashing on zero denominator."""
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, decimals)


def delta_label(value, baseline, higher_is_better=True, decimals=3):
    """
    Returns a dict with the raw delta and a direction tag.
    direction: 'up', 'down', 'flat'
    good:      True if the change is a positive development, False if negative.

    higher_is_better=True  → ERA is NOT this. OPS IS this.
    higher_is_better=False → ERA, WHIP, BB9 are like this (lower = better).
    """
    diff = round(value - baseline, decimals)
    if diff == 0:
        return {"delta": 0, "direction": "flat", "good": None}

    direction = "up" if diff > 0 else "down"
    if higher_is_better:
        good = diff > 0
    else:
        good = diff < 0

    return {"delta": diff, "direction": direction, "good": good}


# -------------------------------------------------------------------
# TEAM SUMMARY STATS
# Aggregates game-level data into season-level numbers.
# -------------------------------------------------------------------

def compute_team_stats(season_data: dict) -> dict:
    """
    Given raw season data for one cohort (N games),
    compute aggregated team-level stats.
    Returns a flat dict of metrics.
    """
    games = season_data["games"]
    if not games:
        return {}

    wins = sum(1 for g in games if g["result"] == "W")
    losses = sum(1 for g in games if g["result"] == "L")
    total_games = wins + losses

    runs_scored   = sum(g["runs_scored"] for g in games)
    runs_allowed  = sum(g["runs_allowed"] for g in games)
    run_diff      = runs_scored - runs_allowed

    # --- Starter pitching aggregation ---
    starter_er = 0
    starter_ip_total = 0.0
    starter_k  = 0
    starter_bb = 0
    starter_hits = 0
    qs_count   = 0

    for g in games:
        s = g.get("starter", {})
        if not s:
            continue
        ip = parse_ip(s.get("ip", "0.0"))
        er = s.get("er", 0)
        starter_ip_total += ip
        starter_er       += er
        starter_k        += s.get("k", 0)
        starter_bb       += s.get("bb", 0)
        starter_hits     += s.get("hits", 0)
        # Quality start: 6+ IP and 3 or fewer ER
        if ip >= 6.0 and er <= 3:
            qs_count += 1

    starter_era  = safe_divide(starter_er * 9, starter_ip_total, 2)
    starter_whip = safe_divide(starter_hits + starter_bb, starter_ip_total, 3)
    starter_k9   = safe_divide(starter_k * 9, starter_ip_total, 2)
    starter_bb9  = safe_divide(starter_bb * 9, starter_ip_total, 2)
    qs_pct       = safe_divide(qs_count, total_games, 3)

    # --- Bullpen aggregation ---
    bp_er   = 0
    bp_ip   = 0.0
    bp_k    = 0
    bp_bb   = 0
    bp_hits = 0

    for g in games:
        for p in g.get("bullpen", []):
            ip = parse_ip(p.get("ip", "0.0"))
            bp_ip   += ip
            bp_er   += p.get("er", 0)
            bp_k    += p.get("k", 0)
            bp_bb   += p.get("bb", 0)
            bp_hits += p.get("hits", 0)

    bullpen_era  = safe_divide(bp_er * 9, bp_ip, 2)
    bullpen_whip = safe_divide(bp_hits + bp_bb, bp_ip, 3)

    # --- Batting aggregation ---
    total_ab   = 0
    total_hits = 0
    total_bb   = 0
    total_hr   = 0
    total_tb   = 0  # total bases for SLG

    seen_batters = {}  # dedupe batters across games for OBP calculation

    for g in games:
        for b in g.get("lineup", []):
            ab   = b.get("ab", 0)
            hits = b.get("hits", 0)
            bb   = b.get("bb", 0)
            hr   = b.get("hr", 0)
            # Approximate total bases: singles=1, assume hits breakdown not in API
            # We use a rough proxy: HR*4 + (hits-HR)*1.5 average for mixed hits
            tb = hr * 4 + max(0, hits - hr) * 1.5
            total_ab   += ab
            total_hits += hits
            total_bb   += bb
            total_hr   += hr
            total_tb   += tb

    team_avg = safe_divide(total_hits, total_ab, 3)
    # OBP = (H + BB) / (AB + BB) simplified (no HBP from basic API)
    team_obp = safe_divide(total_hits + total_bb, total_ab + total_bb, 3)
    team_slg = safe_divide(total_tb, total_ab, 3)
    team_ops = round(team_obp + team_slg, 3)

    return {
        "wins":         wins,
        "losses":       losses,
        "win_pct":      safe_divide(wins, total_games, 3),
        "runs_scored":  runs_scored,
        "runs_allowed": runs_allowed,
        "run_diff":     run_diff,
        "starter_era":  starter_era,
        "starter_whip": starter_whip,
        "starter_k9":   starter_k9,
        "starter_bb9":  starter_bb9,
        "qs_pct":       qs_pct,
        "bullpen_era":  bullpen_era,
        "bullpen_whip": bullpen_whip,
        "team_avg":     team_avg,
        "team_obp":     team_obp,
        "team_slg":     team_slg,
        "team_ops":     team_ops,
        "total_hr":     total_hr,
    }


def parse_ip(ip_str: str) -> float:
    """
    Convert innings pitched string like '6.2' to a float.
    MLB uses .1 to mean 1/3 of an inning and .2 to mean 2/3.
    So 6.2 IP = 6 + 2/3 = 6.667 actual innings.
    """
    try:
        parts = str(ip_str).split(".")
        full_innings = int(parts[0])
        partial = int(parts[1]) if len(parts) > 1 else 0
        return full_innings + partial / 3.0
    except:
        return 0.0


# -------------------------------------------------------------------
# PITCHER BREAKDOWN
# Individual pitcher stats across their appearances in first N games.
# -------------------------------------------------------------------
def compute_pitcher_stats(season_data: dict) -> dict:
    starters = defaultdict(lambda: {"name": "", "games": 0, "ip": 0.0, "er": 0, "k": 0, "bb": 0, "hits": 0, "qs": 0})
    bullpen  = defaultdict(lambda: {"name": "", "games": 0, "ip": 0.0, "er": 0, "k": 0, "bb": 0, "hits": 0})

    for g in season_data["games"]:
        s = g.get("starter", {})
        if s and s.get("id"):
            pid = int(s["id"])          # <-- force int
            ip  = parse_ip(s.get("ip", "0.0"))
            er  = s.get("er", 0)
            starters[pid]["name"]   = s.get("name", "Unknown")
            starters[pid]["games"] += 1
            starters[pid]["ip"]    += ip
            starters[pid]["er"]    += er
            starters[pid]["k"]     += s.get("k", 0)
            starters[pid]["bb"]    += s.get("bb", 0)
            starters[pid]["hits"]  += s.get("hits", 0)
            if ip >= 6.0 and er <= 3:
                starters[pid]["qs"] += 1

        for p in g.get("bullpen", []):
            pid = p.get("id")
            if not pid:
                continue
            pid = int(pid)              # <-- force int
            ip  = parse_ip(p.get("ip", "0.0"))
            bullpen[pid]["name"]   = p.get("name", "Unknown")
            bullpen[pid]["games"] += 1
            bullpen[pid]["ip"]    += ip
            bullpen[pid]["er"]    += p.get("er", 0)
            bullpen[pid]["k"]     += p.get("k", 0)
            bullpen[pid]["bb"]    += p.get("bb", 0)
            bullpen[pid]["hits"]  += p.get("hits", 0)

    def finalize(pitcher_dict, role):
        result = []
        for pid, p in pitcher_dict.items():
            ip   = p["ip"]
            era  = safe_divide(p["er"] * 9, ip, 2)
            whip = safe_divide((p["hits"] + p["bb"]), ip, 3)
            k9   = safe_divide(p["k"] * 9, ip, 2)
            bb9  = safe_divide(p["bb"] * 9, ip, 2)
            row  = {
                "id":    int(pid),      # <-- force int
                "name":  p["name"],
                "role":  role,
                "games": p["games"],
                "ip":    round(ip, 1),
                "era":   era,
                "whip":  whip,
                "k9":    k9,
                "bb9":   bb9,
            }
            if role == "starter":
                row["qs"]     = p["qs"]
                row["qs_pct"] = safe_divide(p["qs"], p["games"], 3)
            result.append(row)
        result.sort(key=lambda x: x["ip"], reverse=True)
        return result

    return {
        "starters": finalize(starters, "starter"),
        "bullpen":  finalize(bullpen,  "bullpen"),
    }



# -------------------------------------------------------------------
# BATTER BREAKDOWN
# Individual batter stats aggregated across first N games.
# -------------------------------------------------------------------
def compute_batter_stats(season_data: dict) -> list:
    batters = defaultdict(lambda: {"name": "", "ab": 0, "hits": 0, "hr": 0, "rbi": 0, "bb": 0, "k": 0})

    for g in season_data["games"]:
        for b in g.get("lineup", []):
            bid = b.get("id")
            if not bid:
                continue
            bid = int(bid)              # <-- force int
            batters[bid]["name"]  = b.get("name", "Unknown")
            batters[bid]["ab"]   += b.get("ab", 0)
            batters[bid]["hits"] += b.get("hits", 0)
            batters[bid]["hr"]   += b.get("hr", 0)
            batters[bid]["rbi"]  += b.get("rbi", 0)
            batters[bid]["bb"]   += b.get("bb", 0)
            batters[bid]["k"]    += b.get("k", 0)

    result = []
    for bid, b in batters.items():
        ab   = b["ab"]
        hits = b["hits"]
        bb   = b["bb"]
        avg  = safe_divide(hits, ab, 3)
        obp  = safe_divide(hits + bb, ab + bb, 3)
        result.append({
            "id":   int(bid),           # <-- force int
            "name": b["name"],
            "ab":   ab,
            "hits": hits,
            "hr":   b["hr"],
            "rbi":  b["rbi"],
            "bb":   bb,
            "k":    b["k"],
            "avg":  avg,
            "obp":  obp,
        })

    result.sort(key=lambda x: x["ab"], reverse=True)
    return result


# -------------------------------------------------------------------
# ROSTER DIFF
# Who is new, who left, who returned across seasons.
# -------------------------------------------------------------------

def compute_roster_diff(seasons_data: list) -> dict:
    """
    Takes a list of season data dicts (2-5 seasons).
    Returns a roster grid and categorized player lists.

    roster_grid: list of players with a presence flag per season.
    new_players: players in later seasons not in the baseline.
    departed:    players in baseline not in later seasons.
    returning:   players present in all selected seasons.
    """
    season_labels = [str(s["season"]) for s in seasons_data]

    # Build set of player IDs per season (pitchers + batters)
    season_rosters = []
    season_player_names = []

    for sd in seasons_data:
        ids   = {}
        for g in sd["games"]:
            s = g.get("starter", {})
            if s and s.get("id"):
                ids[s["id"]] = s["name"]
            for p in g.get("bullpen", []):
                if p.get("id"):
                    ids[p["id"]] = p["name"]
            for b in g.get("lineup", []):
                if b.get("id"):
                    ids[b["id"]] = b["name"]
        season_rosters.append(set(ids.keys()))
        season_player_names.append(ids)

    # All unique player IDs across all seasons
    all_ids = set()
    for r in season_rosters:
        all_ids.update(r)

    # Build the roster grid
    roster_grid = []
    for pid in all_ids:
        name = "Unknown"
        for nm in season_player_names:
            if pid in nm:
                name = nm[pid]
                break
        row = {"id": pid, "name": name}
        for i, label in enumerate(season_labels):
            row[label] = pid in season_rosters[i]
        roster_grid.append(row)

    roster_grid.sort(key=lambda x: x["name"])

    # Categorize players relative to baseline (first season)
    baseline_roster = season_rosters[0]
    later_rosters   = season_rosters[1:]
    all_later        = set().union(*later_rosters) if later_rosters else set()

    departed  = baseline_roster - all_later
    new_players = all_later - baseline_roster
    returning = baseline_roster & all_later

    def make_player_list(id_set):
        result = []
        for pid in id_set:
            name = "Unknown"
            for nm in season_player_names:
                if pid in nm:
                    name = nm[pid]
                    break
            result.append({"id": pid, "name": name})
        return sorted(result, key=lambda x: x["name"])

    return {
        "seasons":      season_labels,
        "roster_grid":  roster_grid,
        "new_players":  make_player_list(new_players),
        "departed":     make_player_list(departed),
        "returning":    make_player_list(returning),
    }


# -------------------------------------------------------------------
# MASTER COMPARISON FUNCTION
# This is what the UI calls. Give it a list of season data dicts
# and it returns everything needed to render all four tabs.
# -------------------------------------------------------------------

def compare_seasons(seasons_data: list) -> dict:
    """
    Master comparison. Takes 2-5 season data dicts.
    Returns a structured comparison dict ready for the UI to render.
    Baseline is always the first (earliest) season in the list.
    """
    if len(seasons_data) < 2:
        raise ValueError("Need at least 2 seasons to compare.")
    if len(seasons_data) > 5:
        raise ValueError("Maximum 5 seasons supported.")

    # Sort by season year ascending so baseline is always earliest
    seasons_data = sorted(seasons_data, key=lambda x: x["season"])

    team_stats   = [compute_team_stats(sd)   for sd in seasons_data]
    pitcher_stats = [compute_pitcher_stats(sd) for sd in seasons_data]
    batter_stats  = [compute_batter_stats(sd)  for sd in seasons_data]
    roster_diff   = compute_roster_diff(seasons_data)

    baseline_team = team_stats[0]
    season_labels = [str(sd["season"]) for sd in seasons_data]

    # Build team stat comparison table with deltas
    TEAM_STAT_META = [
        ("win_pct",      "Win%",         True,  3),
        ("run_diff",     "Run Diff",     True,  0),
        ("runs_scored",  "Runs Scored",  True,  0),
        ("runs_allowed", "Runs Allowed", False, 0),
        ("starter_era",  "Starter ERA",  False, 2),
        ("starter_whip", "Starter WHIP", False, 3),
        ("starter_k9",   "Starter K/9",  True,  2),
        ("starter_bb9",  "Starter BB/9", False, 2),
        ("qs_pct",       "QS%",          True,  3),
        ("bullpen_era",  "Bullpen ERA",  False, 2),
        ("bullpen_whip", "Bullpen WHIP", False, 3),
        ("team_avg",     "Team AVG",     True,  3),
        ("team_obp",     "Team OBP",     True,  3),
        ("team_slg",     "Team SLG",     True,  3),
        ("team_ops",     "Team OPS",     True,  3),
        ("total_hr",     "Total HR",     True,  0),
    ]
    # key, display name, higher_is_better, decimal places

    team_comparison = []
    for key, label, hib, dec in TEAM_STAT_META:
        row = {"stat": label, "stat_key": key}
        for i, season_label in enumerate(season_labels):
            val = team_stats[i].get(key, 0)
            row[season_label] = round(val, dec)
            if i > 0:
                d = delta_label(val, baseline_team.get(key, 0), hib, dec)
                row[f"{season_label}_delta"] = d
        team_comparison.append(row)

    return {
        "seasons":        season_labels,
        "team_comparison": team_comparison,
        "pitcher_stats":  pitcher_stats,
        "batter_stats":   batter_stats,
        "roster_diff":    roster_diff,
        "games_compared": [sd["first_n_games"] for sd in seasons_data],
    }
