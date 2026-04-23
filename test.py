from store import initialize_db, get_season_data
from analysis import compare_seasons
import json

initialize_db()

# Fetch two seasons — will use cache for 2024
data_2024 = get_season_data("OAK", 2024, 8)
data_2025 = get_season_data("OAK", 2025, 8)

result = compare_seasons([data_2024, data_2025])

print("\n=== TEAM COMPARISON ===")
for row in result["team_comparison"]:
    stat = row["stat"]
    val_2024 = row["2024"]
    val_2025 = row["2025"]
    delta = row.get("2025_delta", {})
    direction = "↑" if delta.get("direction") == "up" else "↓" if delta.get("direction") == "down" else "→"
    good = "✓" if delta.get("good") else "✗" if delta.get("good") is False else " "
    print(f"  {stat:<18} 2024: {val_2024:<8} 2025: {val_2025:<8} {direction} {delta.get('delta', 0):<8} {good}")

print("\n=== ROSTER DIFF ===")
diff = result["roster_diff"]
print(f"  New players ({len(diff['new_players'])}):")
for p in diff["new_players"][:5]:
    print(f"    + {p['name']}")
print(f"  Departed ({len(diff['departed'])}):")
for p in diff["departed"][:5]:
    print(f"    - {p['name']}")
print(f"  Returning ({len(diff['returning'])}) players in both seasons")

print("\n=== TOP STARTERS 2024 ===")
for p in result["pitcher_stats"][0]["starters"][:3]:
    print(f"  {p['name']:<25} ERA: {p['era']:<6} WHIP: {p['whip']:<6} K/9: {p['k9']}")

print("\n=== TOP STARTERS 2025 ===")
for p in result["pitcher_stats"][1]["starters"][:3]:
    print(f"  {p['name']:<25} ERA: {p['era']:<6} WHIP: {p['whip']:<6} K/9: {p['k9']}")
