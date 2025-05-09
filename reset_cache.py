import json
from datetime import datetime
from zoneinfo import ZoneInfo

# Prepare reset data with timestamp
reset_data = {
    "cleared_at": datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d %I:%M %p'),
    "available": []
}

# Overwrite the cache file
with open("last_available.json", "w") as f:
    json.dump(reset_data, f, indent=2)

# Output for Render logs
print("✅ Cache reset at:", reset_data["cleared_at"])
