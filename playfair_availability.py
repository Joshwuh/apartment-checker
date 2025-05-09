
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import requests
from bs4 import BeautifulSoup
import os
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
URL = "https://theplayfaircarmel.com/floorplans/"
FLOORPLANS_TO_TRACK = ["The Brighton", "The Canterbury", "The Capelle", "The Windsor", "The Edinburgh"]
CACHE_FILE = "availability_cache.json"
SHEET_ID = "1I9wy0INtMmbH6-bjT94WV-GJR47HVBhLDvHmLhNN7rE"  # Replace this with your actual Sheet ID
SHEET_TAB = "Playfair Logs"

# --- TIMEZONE ---
TZ = ZoneInfo("America/New_York")
now = datetime.now(TZ)

print("▶️ Starting Playfair availability check...")

# --- STEP 1: Scrape current availability ---
try:
    response = requests.get(URL)
    response.raise_for_status()
except Exception as e:
    print("❌ Failed to fetch floorplans page:", e)
    exit(1)

soup = BeautifulSoup(response.text, "html.parser")
cards = soup.select("a.jd-fp-floorplan-card")

current_state = {}
for card in cards:
    name_tag = card.select_one(".jd-fp-card-info__title")
    if name_tag:
        name = name_tag.text.strip()
        if name in FLOORPLANS_TO_TRACK:
            available_now = card.select_one(".jd-fp-flag p")
            is_available = available_now and "Available Now" in available_now.text
            current_state[name] = is_available

print(f"ℹ️ Scraped floorplans: {list(current_state.items())}")

# --- STEP 2: Load cache ---
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
else:
    cache = {}

# --- STEP 3: Detect changes and prepare log entries ---
logs_to_write = []

for name, is_now_available in current_state.items():
    cached = cache.get(name, {})
    was_available = cached.get("available", False)
    available_since = cached.get("available_since")

    if is_now_available != was_available:
        timestamp = now.strftime("%Y-%m-%d %H:%M")
        available_str = available_since if available_since else ""
        unavailable_str = ""
        duration_str = ""

        print(f"🔄 Change detected for {name}: {'available' if is_now_available else 'unavailable'}")

        if is_now_available:
            # Became available
            cache[name] = {"available": True, "available_since": now.isoformat()}
            logs_to_write.append([name, "available", timestamp, timestamp, "", ""])
        else:
            # Became unavailable
            if available_since:
                then = datetime.fromisoformat(available_since)
                delta = now - then
                days = delta.days
                hours, remainder = divmod(delta.seconds, 3600)
                minutes = remainder // 60
                duration_str = f"{days}d {hours}h {minutes}m"
                unavailable_str = timestamp
            cache[name] = {"available": False, "available_since": None}
            logs_to_write.append([name, "unavailable", timestamp, available_str, unavailable_str, duration_str])

# --- STEP 4: Save updated cache ---
with open(CACHE_FILE, "w") as f:
    json.dump(cache, f, indent=2)

# --- STEP 5: Write to Google Sheets ---
if logs_to_write:
    print("⏳ Authenticating with Google Sheets...")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("creds.json", scopes=scope)
    client = gspread.authorize(creds)

    print("✅ Auth successful, opening sheet...")
    sheet = client.open_by_key(SHEET_ID)
    worksheet = sheet.worksheet(SHEET_TAB)

    print(f"📤 Appending {len(logs_to_write)} row(s) to Playfair Logs...")
    worksheet.append_rows(logs_to_write)
    print("✅ Rows written to Google Sheet.")
else:
    print("✅ No availability changes to log.")
