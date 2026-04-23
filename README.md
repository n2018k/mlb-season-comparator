# ⚾ MLB Season Comparator

Compare an MLB team's performance across multiple seasons — side by side, first N games at a time.

Built with Python and Streamlit. Data fetched from the MLB Stats API and cached locally.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/streamlit-1.45+-red)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- Compare any MLB team across 2 to 5 seasons
- Filter to the first N games of each season for fair comparisons
- **Team Overview** — win%, run differential, team OPS, starter ERA, bullpen ERA
- **Pitching Breakdown** — starters and bullpen stats per season with quality start tracking
- **Batting Breakdown** — full hitting stats per season sorted by at-bats
- **Player Quick Compare** — select any player and see their stats across all selected seasons instantly
- **Roster Changes** — who's new, who departed, who's returning, with role badges
- Delta columns with 🟢/🔴 indicators showing improvement or decline from baseline season
- Hover tooltips on every stat column with plain-English definitions
- Local SQLite cache — seasons load instantly after first fetch

---

## Getting Started

### 1. Clone the repo

git clone https://github.com/YOUR_USERNAME/mlb-season-comparator.git
cd mlb-season-comparator

### 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

### 3. Install Dependencies
pip install -r requirements.txt

### 4. Run the app
streamlit run app.py

### How it works
app.py          — Streamlit UI, all rendering and session state
analysis.py     — stat aggregation and season comparison logic
store.py        — MLB Stats API fetching and SQLite caching
glossary.py     — hover tooltip definitions for every stat

Known Limitations
Roster role detection (starter vs bullpen) is based on game-by-game appearance data, not official roster designations
Players who switched roles mid-season may appear as both starter and bullpen
Current season data updates once per 24 hours due to cache TTL

Changelog
v1.0.0 — April 2026
Initial release
Team comparison across up to 5 seasons
Pitching, batting, roster change tabs
Player Quick Compare with delta tracking
Glossary tooltips on all stat columns
Role badges on roster changes


License
MIT — free to use, modify, and distribute.
