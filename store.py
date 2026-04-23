import sqlite3
import json
import os
from fetcher import fetch_season_data

DB_PATH = "mlb_data.db"


def get_connection():
    """Open a connection to the local SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn


def initialize_db():
    """
    Create tables if they don't exist yet.
    Also adds season_in_progress column if upgrading from old schema.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS season_cache (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            team                TEXT NOT NULL,
            season              INTEGER NOT NULL,
            games_count         INTEGER NOT NULL,
            games_available     INTEGER NOT NULL DEFAULT 0,
            season_in_progress  INTEGER NOT NULL DEFAULT 0,
            fetched_at          TEXT NOT NULL,
            data_json           TEXT NOT NULL,
            UNIQUE(team, season)
        )
    """)

    # Handle upgrade from old schema that didn't have these columns
    for col, definition in [
        ("games_available",    "INTEGER NOT NULL DEFAULT 0"),
        ("season_in_progress", "INTEGER NOT NULL DEFAULT 0"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE season_cache ADD COLUMN {col} {definition}")
        except Exception:
            pass  # Column already exists, that's fine

    conn.commit()
    conn.close()
    print("Database initialized.")

def get_cached_season(team: str, season: int) -> dict | None:
    """
    Returns cached record including new metadata fields.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT data_json, games_count, games_available, 
                  season_in_progress, fetched_at 
           FROM season_cache WHERE team = ? AND season = ?""",
        (team.upper(), season)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "data":               json.loads(row["data_json"]),
            "games_count":        row["games_count"],
            "games_available":    row["games_available"],
            "season_in_progress": row["season_in_progress"],
            "fetched_at":         row["fetched_at"],
        }
    return None

def save_season(team: str, season: int, data: dict):
    """
    Save fetched season data to the database.
    Stores new metadata fields so the UI can show warnings.
    """
    from datetime import datetime
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO season_cache 
            (team, season, games_count, games_available, season_in_progress, fetched_at, data_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(team, season) DO UPDATE SET
            games_count         = excluded.games_count,
            games_available     = excluded.games_available,
            season_in_progress  = excluded.season_in_progress,
            fetched_at          = excluded.fetched_at,
            data_json           = excluded.data_json
    """, (
        team.upper(),
        season,
        data["first_n_games"],
        data.get("games_available", data["first_n_games"]),
        1 if data.get("season_in_progress", False) else 0,
        datetime.now().isoformat(),
        json.dumps(data)
    ))

    conn.commit()
    conn.close()
    print(f"Saved {team} {season} ({data['first_n_games']} games) to cache.")


def get_season_data(team: str, season: int, first_n_games: int) -> dict:
    """
    Smart fetch with cache. Now also handles in-progress season staleness.
    
    Four scenarios:
    1. Not cached → fetch from API, save.
    2. Cached, in-progress season, cache older than 24 hours → re-fetch.
       Live seasons change daily so we can't serve stale cache forever.
    3. Cached but fewer games than requested → re-fetch with larger N.
    4. Cached and sufficient → slice to first_n_games and return.
    """
    from datetime import datetime, timedelta

    cached = get_cached_season(team, season)

    if cached is None:
        print(f"No cache found for {team} {season}. Fetching from API...")
        data = fetch_season_data(team, season, first_n_games)
        save_season(team, season, data)
        return data

    cached_count      = cached["games_count"]
    in_progress       = bool(cached.get("season_in_progress", 0))
    fetched_at_str    = cached.get("fetched_at", "")

    # Check staleness for in-progress seasons
    if in_progress and fetched_at_str:
        try:
            fetched_at = datetime.fromisoformat(fetched_at_str)
            age        = datetime.now() - fetched_at
            if age > timedelta(hours=24):
                print(f"Cache for {team} {season} is {int(age.total_seconds()/3600)}h old. Re-fetching live season...")
                data = fetch_season_data(team, season, first_n_games)
                save_season(team, season, data)
                return data
        except Exception:
            pass  # If date parsing fails, fall through to normal logic

    if cached_count < first_n_games:
        print(f"Cache has {cached_count} games but {first_n_games} requested. Re-fetching...")
        data = fetch_season_data(team, season, first_n_games)
        save_season(team, season, data)
        return data

    print(f"Loaded {team} {season} from cache ({cached_count} games stored, returning first {first_n_games}).")
    full_data = cached["data"]
    sliced    = dict(full_data)
    sliced["games"]         = full_data["games"][:first_n_games]
    sliced["first_n_games"] = first_n_games
    return sliced

def list_cached_seasons() -> list:
    """
    Returns a list of what's already in the cache.
    Useful for showing the user what data they have locally
    without making any API calls.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT team, season, games_count, fetched_at FROM season_cache ORDER BY team, season"
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
