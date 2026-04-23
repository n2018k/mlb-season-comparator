#from fetcher import fetch_season_data
#import json

#data = fetch_season_data("OAK", 2024, 5)
#print(json.dumps(data, indent=2))

from store import initialize_db, get_season_data, list_cached_seasons

# Set up the database (safe to call multiple times, it checks first)
initialize_db()

# First call — will hit the API
print("=== First call ===")
data = get_season_data("OAK", 2024, 5)
print(f"Got {len(data['games'])} games\n")

# Second call — should be instant, reads from cache
print("=== Second call (should say 'Loaded from cache') ===")
data = get_season_data("OAK", 2024, 5)
print(f"Got {len(data['games'])} games\n")

# Third call with more games — should re-fetch
print("=== Third call with more games (should re-fetch) ===")
data = get_season_data("OAK", 2024, 8)
print(f"Got {len(data['games'])} games\n")

# Show what's in the cache
print("=== Cache contents ===")
for row in list_cached_seasons():
    print(row)
