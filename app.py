import streamlit as st
import pandas as pd
from store import initialize_db, get_season_data
from analysis import compare_seasons
from glossary import GLOSSARY

st.set_page_config(
    page_title="MLB Season Comparator",
    layout="wide",
    initial_sidebar_state="expanded"
)

initialize_db()

def glossary_label(key: str) -> str:
    return GLOSSARY.get(key, "")

def format_delta(delta_dict: dict) -> str:
    if not delta_dict:
        return ""
    d         = delta_dict.get("delta", 0)
    good      = delta_dict.get("good")
    direction = delta_dict.get("direction", "flat")
    if direction == "flat":
        return "—"
    prefix    = "+" if d > 0 else ""
    value_str = f"{prefix}{d}"
    if good is True:
        return f"🟢 {value_str}"
    elif good is False:
        return f"🔴 {value_str}"
    return value_str

def make_delta_col(rows: list, col: str, baseline_season: str, higher_is_better: bool) -> list:
    baseline_val = None
    for row in rows:
        if row["Season"] == baseline_season:
            baseline_val = row.get(col)
            break
    deltas = []
    for row in rows:
        val = row.get(col)
        if row["Season"] == baseline_season or val is None or baseline_val is None:
            deltas.append("—")
            continue
        try:
            diff   = round(float(val) - float(baseline_val), 3)
            prefix = "+" if diff > 0 else ""
            if diff == 0:
                deltas.append("—")
            elif (higher_is_better and diff > 0) or (not higher_is_better and diff < 0):
                deltas.append(f"🟢 {prefix}{diff}")
            else:
                deltas.append(f"🔴 {prefix}{diff}")
        except:
            deltas.append("—")
    return deltas


# -------------------------------------------------------------------
# SESSION STATE INIT
# Everything the app needs to persist across rerenders lives here.
# -------------------------------------------------------------------
if "result" not in st.session_state:
    st.session_state.result        = None
if "season_labels" not in st.session_state:
    st.session_state.season_labels = []
if "player_index" not in st.session_state:
    st.session_state.player_index  = {}
if "player_display_names" not in st.session_state:
    st.session_state.player_display_names = {}
if "sorted_labels" not in st.session_state:
    st.session_state.sorted_labels = []
if "warnings" not in st.session_state:
    st.session_state.warnings      = []
if "n_games_used" not in st.session_state:
    st.session_state.n_games_used  = None
if "team_used" not in st.session_state:
    st.session_state.team_used     = None


# -------------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------------
st.sidebar.title("MLB Season Comparator")
st.sidebar.markdown("---")

ALL_TEAMS = [
    "ARI","ATL","BAL","BOS","CHC","CWS","CIN","CLE","COL","DET",
    "HOU","KC","LAA","LAD","MIA","MIL","MIN","NYM","NYY","OAK",
    "PHI","PIT","SD","SF","SEA","STL","TB","TEX","TOR","WSH"
]

team = st.sidebar.selectbox(
    "Select Team", ALL_TEAMS, index=ALL_TEAMS.index("OAK")
)

st.sidebar.markdown("**Seasons to Compare** (2 to 5)")
available_seasons = list(range(2015, 2027))
selected_seasons  = st.sidebar.multiselect(
    "Seasons", available_seasons, default=[2024, 2025]
)

if len(selected_seasons) < 2:
    st.sidebar.error("Select at least 2 seasons.")
elif len(selected_seasons) > 5:
    st.sidebar.error("Maximum 5 seasons.")

n_games = st.sidebar.number_input(
    "Games to compare",
    min_value=1, max_value=162, value=20, step=1,
    help="Compare only the first N games of each season."
)

compare_btn = st.sidebar.button(
    "Compare", type="primary", use_container_width=True
)

st.sidebar.markdown("---")
st.sidebar.markdown("**What the colors mean**")
st.sidebar.markdown("🟢 Improvement from baseline")
st.sidebar.markdown("🔴 Decline from baseline")
st.sidebar.markdown("Baseline = earliest selected season")


# -------------------------------------------------------------------
# PLAYER INDEX BUILDER
# -------------------------------------------------------------------
def build_player_index(result: dict, season_labels: list) -> dict:
    index = {}

    for i, sl in enumerate(season_labels):
        for role in ["starters", "bullpen"]:
            for p in result["pitcher_stats"][i][role]:
                pid = str(p["id"])
                if pid not in index:
                    index[pid] = {"name": p["name"], "role": "pitcher", "seasons": {}}
                else:
                    if index[pid]["role"] == "batter":
                        index[pid]["role"] = "both"
                role_type = "starter" if role == "starters" else "bullpen"  # <-- fix
                index[pid]["seasons"][sl] = {
                    "type":  role_type,
                    "G":     p["games"],
                    "IP":    p["ip"],
                    "ERA":   p["era"],
                    "WHIP":  p["whip"],
                    "K/9":   p["k9"],
                    "BB/9":  p["bb9"],
                    "QS":    p.get("qs", None),
                    "QS%":   p.get("qs_pct", None),
                }

        for b in result["batter_stats"][i]:
            bid = str(b["id"])
            batter_entry = {
                "type": "batter",
                "AB":   b["ab"],
                "H":    b["hits"],
                "HR":   b["hr"],
                "RBI":  b["rbi"],
                "BB":   b["bb"],
                "K":    b["k"],
                "AVG":  b["avg"],
                "OBP":  b["obp"],
            }
            if bid not in index:
                index[bid] = {"name": b["name"], "role": "batter", "seasons": {}}
                index[bid]["seasons"][sl] = batter_entry
            else:
                if index[bid]["role"] == "pitcher":
                    index[bid]["role"] = "both"
                existing = index[bid]["seasons"].get(sl)
                # Don't overwrite pitcher stats with 0-AB batter entry
                if existing is None:
                    index[bid]["seasons"][sl] = batter_entry
                elif existing.get("type") == "batter":
                    index[bid]["seasons"][sl] = batter_entry

    return index


def build_display_names(player_index: dict) -> tuple[dict, list]:
    """
    Returns:
      player_display_names: { label_string → pid_string }
      sorted_labels: sorted list of label strings with sentinel first
    """
    SENTINEL = "— Select a player —"
    mapping  = {SENTINEL: None}

    for pid, pdata in player_index.items():
        label = f"{pdata['name']} [{pdata['role']}]"
        if label in mapping:
            label = f"{pdata['name']} [{pdata['role']}] (#{pid})"
        mapping[label] = pid

    sorted_labels = [SENTINEL] + sorted(
        [k for k in mapping if k != SENTINEL],
        key=lambda x: x.lower()
    )
    return mapping, sorted_labels


# -------------------------------------------------------------------
# COMPARE BUTTON HANDLER
# Only runs when button is clicked. Stores everything in session_state
# so subsequent interactions (like picking a player) don't lose data.
# -------------------------------------------------------------------
if compare_btn:
    if len(selected_seasons) < 2 or len(selected_seasons) > 5:
        st.error("Please select between 2 and 5 seasons.")
        st.stop()

    selected_seasons_sorted = sorted(selected_seasons)
    warnings     = []
    seasons_data = []

    progress = st.sidebar.progress(0)
    for i, season in enumerate(selected_seasons_sorted):
        data = get_season_data(team, season, n_games)
        seasons_data.append(data)

        actual    = data["first_n_games"]
        requested = data.get("games_requested", n_games)
        available = data.get("games_available", actual)
        in_prog   = data.get("season_in_progress", False)

        if actual < requested:
            warnings.append(
                f"**{season}:** Requested {requested} games but only "
                f"**{available} completed** so far. Showing {actual} games."
            )
        elif in_prog:
            warnings.append(
                f"**{season}:** Season in progress. "
                f"{available} games completed. Cache refreshes every 24h."
            )
        progress.progress((i + 1) / len(selected_seasons_sorted))

    progress.empty()

    result        = compare_seasons(seasons_data)
    player_index  = build_player_index(result, result["seasons"])
    display_names, sorted_labels = build_display_names(player_index)

    # Store everything that needs to survive rerenders
    st.session_state.result               = result
    st.session_state.season_labels        = result["seasons"]
    st.session_state.player_index         = player_index
    st.session_state.player_display_names = display_names
    st.session_state.sorted_labels        = sorted_labels
    st.session_state.warnings             = warnings
    st.session_state.n_games_used         = n_games
    st.session_state.team_used            = team
    # Reset player selection when recomparing
    st.session_state.selected_player_label = "— Select a player —"


# -------------------------------------------------------------------
# MAIN DISPLAY
# Only renders if we have a result in session state.
# -------------------------------------------------------------------
st.title("MLB Season Comparator")

if st.session_state.result is None:
    st.info("Select a team, seasons, and number of games in the sidebar, then click **Compare**.")
    st.stop()

# Unpack from session state
result        = st.session_state.result
season_labels = st.session_state.season_labels
player_index  = st.session_state.player_index
display_names = st.session_state.player_display_names
sorted_labels = st.session_state.sorted_labels
n_games_used  = st.session_state.n_games_used
team_used     = st.session_state.team_used
baseline      = season_labels[0]
later_seasons = season_labels[1:]

for w in st.session_state.warnings:
    st.warning(w)

st.markdown(
    f"### {team_used} — First **{n_games_used}** games | "
    f"Baseline: **{baseline}** | "
    f"Comparing: **{', '.join(later_seasons)}**"
)
st.markdown("---")


# -------------------------------------------------------------------
# PLAYER QUICK COMPARE
# -------------------------------------------------------------------
st.subheader("🔍 Player Quick Compare")
st.caption(
    "Select any player who appeared in your selected games. "
    "See their stats across all selected seasons in one view."
)

selected_label = st.selectbox(
    "Search player",
    options=sorted_labels,
    index=0,
    key="selected_player_label"   # ties to session_state automatically
)

selected_pid = display_names.get(selected_label)  # None if sentinel

if selected_pid is not None:
    player = player_index.get(selected_pid)
    st.write(f"DEBUG seasons keys: {list(player['seasons'].keys())} | season_labels: {season_labels}")

    if player is None:
        st.error(f"Player lookup failed for id={selected_pid}. This is a bug — report it.")
    else:
        st.markdown(f"#### {player['name']}")
        role = player["role"]

        # ── PITCHING ────────────────────────────────────────────────
        if role in ("pitcher", "both"):
            st.markdown("**Pitching Stats**")
            pitch_rows = []
            for sl in season_labels:
                s = player["seasons"].get(sl)
                if s and s.get("type") in ("starter", "bullpen"):
                    pitch_rows.append({
                        "Season": sl,
                        "Role":   s["type"].capitalize(),
                        "G":      s.get("G"),
                        "IP":     s.get("IP"),
                        "ERA":    s.get("ERA"),
                        "WHIP":   s.get("WHIP"),
                        "K/9":    s.get("K/9"),
                        "BB/9":   s.get("BB/9"),
                        "QS":     s.get("QS"),
                        "QS%":    s.get("QS%"),
                    })
                else:
                    pitch_rows.append({
                        "Season": sl, "Role": "Not on roster",
                        "G": None, "IP": None, "ERA": None,
                        "WHIP": None, "K/9": None, "BB/9": None,
                        "QS": None, "QS%": None,
                    })

            df_p = pd.DataFrame(pitch_rows)
            df_p["ERA Δ"]  = make_delta_col(pitch_rows, "ERA",  season_labels[0], False)
            df_p["WHIP Δ"] = make_delta_col(pitch_rows, "WHIP", season_labels[0], False)
            df_p["K/9 Δ"]  = make_delta_col(pitch_rows, "K/9",  season_labels[0], True)
            df_p["BB/9 Δ"] = make_delta_col(pitch_rows, "BB/9", season_labels[0], False)

            st.dataframe(
                df_p, width="stretch", hide_index=True,
                column_config={
                    "ERA":  st.column_config.NumberColumn("ERA",  format="%.2f", help=glossary_label("ERA")),
                    "WHIP": st.column_config.NumberColumn("WHIP", format="%.3f", help=glossary_label("WHIP")),
                    "K/9":  st.column_config.NumberColumn("K/9",  format="%.2f", help=glossary_label("K9")),
                    "BB/9": st.column_config.NumberColumn("BB/9", format="%.2f", help=glossary_label("BB9")),
                    "QS%":  st.column_config.NumberColumn("QS%",  format="%.3f", help=glossary_label("QS_PCT")),
                }
            )

        # ── BATTING ─────────────────────────────────────────────────
        if role in ("batter", "both"):
            bat_rows = []
            for sl in season_labels:
                s = player["seasons"].get(sl)
                if s and s.get("type") == "batter" and (s.get("AB") or 0) > 0:
                    bat_rows.append({
                        "Season": sl,
                        "AB":  s.get("AB"), "H":   s.get("H"),
                        "HR":  s.get("HR"), "RBI": s.get("RBI"),
                        "BB":  s.get("BB"), "K":   s.get("K"),
                        "AVG": s.get("AVG"), "OBP": s.get("OBP"),
                    })
                else:
                    bat_rows.append({
                        "Season": sl,
                        "AB": None, "H": None, "HR": None, "RBI": None,
                        "BB": None, "K": None, "AVG": None, "OBP": None,
                    })

            has_real_batting = any(r["AB"] is not None for r in bat_rows)
            if has_real_batting:
                st.markdown("**Batting Stats**")
                df_b = pd.DataFrame(bat_rows)
                df_b["AVG Δ"] = make_delta_col(bat_rows, "AVG", season_labels[0], True)
                df_b["OBP Δ"] = make_delta_col(bat_rows, "OBP", season_labels[0], True)
                df_b["HR Δ"]  = make_delta_col(bat_rows, "HR",  season_labels[0], True)
                st.dataframe(
                    df_b, width="stretch", hide_index=True,
                    column_config={
                        "AVG": st.column_config.NumberColumn("AVG", format="%.3f", help=glossary_label("AVG")),
                        "OBP": st.column_config.NumberColumn("OBP", format="%.3f", help=glossary_label("OBP")),
                    }
                )

        missing = [sl for sl in season_labels if sl not in player["seasons"]]
        if missing:
            st.caption(
                f"⚠️ {player['name']} not in first {n_games_used} games of: {', '.join(missing)}"
            )

st.markdown("---")


# -------------------------------------------------------------------
# TABS
# -------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Team Overview",
    "⚾ Pitching",
    "🏏 Batting",
    "👥 Roster Changes"
])


# ===================================================================
# TAB 1 — TEAM OVERVIEW
# ===================================================================
with tab1:
    st.subheader("Team Stats Comparison")
    st.caption(f"First {n_games_used} games of each season.")

    rows = []
    for row in result["team_comparison"]:
        display_row = {"Stat": row["stat"]}
        for sl in season_labels:
            display_row[sl] = row[sl]
        for sl in later_seasons:
            display_row[f"{sl} vs {baseline}"] = format_delta(row.get(f"{sl}_delta", {}))
        rows.append(display_row)

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.markdown("---")
    st.subheader("Headline Numbers")
    cols = st.columns(len(season_labels))
    for i, sl in enumerate(season_labels):
        def get_val(stat_key, sl=sl):
            for r in result["team_comparison"]:
                if r["stat_key"] == stat_key:
                    return r[sl]
            return "N/A"
        with cols[i]:
            st.markdown(f"**{sl}**")
            st.metric("Win%",        get_val("win_pct"),     help=glossary_label("WIN_PCT"))
            st.metric("Run Diff",    get_val("run_diff"),    help=glossary_label("RUN_DIFF"))
            st.metric("Team OPS",    get_val("team_ops"),    help=glossary_label("OPS"))
            st.metric("Starter ERA", get_val("starter_era"), help=glossary_label("ERA"))
            st.metric("Bullpen ERA", get_val("bullpen_era"), help=glossary_label("BULLPEN_ERA"))


# ===================================================================
# TAB 2 — PITCHING
# ===================================================================
with tab2:
    st.subheader("Pitching Breakdown")
    st.caption("Aggregated across first N games. Sorted by innings pitched.")

    pitch_tabs = st.tabs(
        [f"Starters {sl}" for sl in season_labels] +
        [f"Bullpen {sl}"  for sl in season_labels]
    )

    for i, sl in enumerate(season_labels):
        with pitch_tabs[i]:
            starters = result["pitcher_stats"][i]["starters"]
            if starters:
                df_s = pd.DataFrame(starters).drop(columns=["id", "role"])
                df_s.columns = [c.upper() for c in df_s.columns]
                df_s = df_s.rename(columns={
                    "NAME": "Pitcher", "GAMES": "G",
                    "K9": "K/9", "BB9": "BB/9", "QS_PCT": "QS%"
                })
                st.dataframe(df_s, width="stretch", hide_index=True,
                    column_config={
                        "ERA":  st.column_config.NumberColumn("ERA",  format="%.2f", help=glossary_label("ERA")),
                        "WHIP": st.column_config.NumberColumn("WHIP", format="%.3f", help=glossary_label("WHIP")),
                        "K/9":  st.column_config.NumberColumn("K/9",  format="%.2f", help=glossary_label("K9")),
                        "BB/9": st.column_config.NumberColumn("BB/9", format="%.2f", help=glossary_label("BB9")),
                        "QS%":  st.column_config.NumberColumn("QS%",  format="%.3f", help=glossary_label("QS_PCT")),
                    })
            else:
                st.write("No starter data available.")

    for i, sl in enumerate(season_labels):
        with pitch_tabs[len(season_labels) + i]:
            bullpen = result["pitcher_stats"][i]["bullpen"]
            if bullpen:
                df_b = pd.DataFrame(bullpen).drop(columns=["id", "role"])
                df_b.columns = [c.upper() for c in df_b.columns]
                df_b = df_b.rename(columns={
                    "NAME": "Pitcher", "GAMES": "G",
                    "K9": "K/9", "BB9": "BB/9"
                })
                st.dataframe(df_b, width="stretch", hide_index=True,
                    column_config={
                        "ERA":  st.column_config.NumberColumn("ERA",  format="%.2f", help=glossary_label("ERA")),
                        "WHIP": st.column_config.NumberColumn("WHIP", format="%.3f", help=glossary_label("WHIP")),
                        "K/9":  st.column_config.NumberColumn("K/9",  format="%.2f", help=glossary_label("K9")),
                        "BB/9": st.column_config.NumberColumn("BB/9", format="%.2f", help=glossary_label("BB9")),
                    })
            else:
                st.write("No bullpen data available.")


# ===================================================================
# TAB 3 — BATTING
# ===================================================================
with tab3:
    st.subheader("Batting Breakdown")
    st.caption("Aggregated across first N games. Sorted by at-bats.")

    bat_tabs = st.tabs([f"{sl}" for sl in season_labels])
    for i, sl in enumerate(season_labels):
        with bat_tabs[i]:
            batters = result["batter_stats"][i]
            if batters:
                df_bat = pd.DataFrame(batters).drop(columns=["id"])
                df_bat.columns = [c.upper() for c in df_bat.columns]
                df_bat = df_bat.rename(columns={
                    "NAME": "Batter", "HITS": "H"
                })
                st.dataframe(df_bat, width="stretch", hide_index=True,
                    column_config={
                        "AVG": st.column_config.NumberColumn("AVG", format="%.3f", help=glossary_label("AVG")),
                        "OBP": st.column_config.NumberColumn("OBP", format="%.3f", help=glossary_label("OBP")),
                    })
            else:
                st.write("No batting data available.")


# ===================================================================
# TAB 4 — ROSTER CHANGES
# ===================================================================
with tab4:
    st.subheader("Roster Changes")
    diff = result["roster_diff"]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"### 🟢 New in {', '.join(later_seasons)}")
        st.caption(f"Not on {baseline} roster")
        for p in diff["new_players"]:
            st.write(f"+ {p['name']}")
        if not diff["new_players"]:
            st.write("None")

    with col2:
        st.markdown(f"### 🔴 Departed after {baseline}")
        st.caption(f"On {baseline}, not in later seasons")
        for p in diff["departed"]:
            st.write(f"- {p['name']}")
        if not diff["departed"]:
            st.write("None")

    with col3:
        st.markdown(f"### ⚪ Returning")
        st.caption("Present in all selected seasons")
        for p in diff["returning"]:
            st.write(f"  {p['name']}")
        if not diff["returning"]:
            st.write("None")

    st.markdown("---")
    st.subheader("Full Roster Grid")
    st.caption("✓ = appeared in that season's first N games")
    grid    = diff["roster_grid"]
    df_grid = pd.DataFrame(grid).drop(columns=["id"])
    df_grid = df_grid.rename(columns={"name": "Player"})
    for sl in season_labels:
        if sl in df_grid.columns:
            df_grid[sl] = df_grid[sl].map({True: "✓", False: "—"})
    st.dataframe(df_grid, width="stretch", hide_index=True)
