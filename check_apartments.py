import requests
from twilio.rest import Client
from datetime import datetime
import smtplib
from email.message import EmailMessage
import os
from zoneinfo import ZoneInfo
import base64
import json
from google.oauth2 import service_account
import gspread

# Load and authorize Google credentials
creds_json = base64.b64decode(os.environ['GOOGLE_CREDS_B64']).decode('utf-8')
creds_dict = json.loads(creds_json)
creds = service_account.Credentials.from_service_account_info(
    creds_dict,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
)
gc = gspread.authorize(creds)
worksheet = gc.open_by_key('1I9wy0INtMmbH6-bjT94WV-GJR47HVBhLDvHmLhNN7rE').worksheet('Sheet1')

# Twilio and Email config
account_sid = os.environ['ACCOUNT_SID']
auth_token = os.environ['AUTH_TOKEN']
twilio_number = os.environ['TWILIO_NUMBER']
your_number = os.environ['YOUR_NUMBER']
email_from = os.environ['EMAIL_FROM']
email_to = os.environ['EMAIL_TO'].split(',')
email_password = os.environ['EMAIL_PASSWORD']

# Floorplans and Knock API
floorplans_to_watch = ['Sedona', 'Stockbridge', 'Telluride', 'Washington']
url = 'https://doorway-api.knockrentals.com/v1/property/2017805/units'
LAST_AVAILABLE_FILE = "last_available.json"

def load_last_available():
    if os.path.exists(LAST_AVAILABLE_FILE):
        with open(LAST_AVAILABLE_FILE, 'r') as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    return set(data.get("available", []))
                elif isinstance(data, list):
                    return set(data)
            except json.JSONDecodeError:
                return set()
    return set()

def save_current_available(current):
    save_data = {
        "cleared_at": datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d %I:%M %p'),
        "available": list(current)
    }
    with open(LAST_AVAILABLE_FILE, 'w') as f:
        json.dump(save_data, f, indent=2)

def send_sms(message):
    client = Client(account_sid, auth_token)
    client.messages.create(body=message, from_=twilio_number, to=your_number)

def send_email(subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = email_from
    msg['To'] = email_to
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(email_from, email_password)
        smtp.send_message(msg)

def check_units():
    now = datetime.now(ZoneInfo('America/New_York'))
    timestamp = now.strftime("%Y-%m-%d %I:%M %p")

    response = requests.get(url)
    data = response.json()
    layouts = data['units_data']['layouts']
    units = data['units_data']['units']

    layout_lookup = {layout['id']: layout['name'] for layout in layouts}
    available_layout_ids = {
        unit.get('layoutId') for unit in units if unit.get('status') != 'contact us'
    }
    available_names = {
        layout_lookup[layout_id] for layout_id in available_layout_ids if layout_id in layout_lookup
    }

    available_matches = []
    for target in floorplans_to_watch:
        matches = [name for name in available_names if target.lower() in name.lower()]
        available_matches.extend(matches)

    current_set = set(available_matches)
    last_set = load_last_available()


    if current_set != last_set:
        save_current_available(current_set)

        if current_set:
            message = f"✅ {timestamp} — These floorplans are NOW AVAILABLE:\n" + \
                      "\n".join(f"• {name}" for name in current_set)
            print(message)
            send_sms(message)
            send_email("Apartment Alert", message)
            status_msg = "Available: " + ", ".join(current_set)
        else:
            print(f"{timestamp} — 🚫 All floorplans now unavailable.")
            status_msg = "No matching floorplans"
    else:
        print(f"{timestamp} — No change in availability.")
        status_msg = "No change"

    worksheet.append_row([timestamp, status_msg])

check_units()
