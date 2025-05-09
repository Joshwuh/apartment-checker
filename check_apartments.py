import requests
from twilio.rest import Client
from datetime import datetime
import smtplib
from email.message import EmailMessage
import os
from zoneinfo import ZoneInfo
import base64
import json
import gspread
from google.oauth2 import service_account
from google.auth.transport.requests import Request

# Decode and authorize Google Sheets API
creds_json = base64.b64decode(os.environ['GOOGLE_CREDS_B64']).decode('utf-8')
creds_dict = json.loads(creds_json)
# creds = service_account.Credentials.from_service_account_info(creds_dict)
scoped_creds = service_account.Credentials.from_service_account_info(
    creds_dict,
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)
gc = gspread.authorize(scoped_creds)

spreadsheet_name = 'Apartment Checker Logs - The Seasons'
sheet_name = 'Sheet1'
worksheet = gc.open(spreadsheet_name).worksheet(sheet_name)

# Load secrets from environment variables
account_sid = os.environ['ACCOUNT_SID']
auth_token = os.environ['AUTH_TOKEN']
twilio_number = os.environ['TWILIO_NUMBER']
your_number = os.environ['YOUR_NUMBER']
email_from = os.environ['EMAIL_FROM']
email_to = os.environ['EMAIL_TO'].split(',')
email_password = os.environ['EMAIL_PASSWORD']

floorplans_to_watch = ['Sedona', 'Stockbridge', 'Telluride', 'Washington']
url = 'https://doorway-api.knockrentals.com/v1/property/2017805/units'

def send_sms(message):
    client = Client(account_sid, auth_token)
    client.messages.create(
        body=message,
        from_=twilio_number,
        to=your_number
    )

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
    print(f"🕒 Script started at {now.strftime('%Y-%m-%d %I:%M %p')}")

    response = requests.get(url)
    data = response.json()

    layouts = data['units_data']['layouts']
    units = data['units_data']['units']

    print(f"Layouts found: {len(layouts)}")
    print(f"Units found: {len(units)}")

    layout_lookup = {layout['id']: layout['name'] for layout in layouts}
    available_layout_ids = {
        unit.get('layoutId')
        for unit in units
        if unit.get('status') == 'available'
    }
    available_names = {
        layout_lookup[layout_id]
        for layout_id in available_layout_ids
        if layout_id in layout_lookup
    }

    available_matches = []
    for target in floorplans_to_watch:
        matches = [
            name for name in available_names
            if target.lower() in name.lower()
        ]
        available_matches.extend(matches)

    timestamp = now.strftime("%Y-%m-%d %I:%M %p")
    log_line = f"### 🕒 {timestamp}\n"

    if available_matches:
        message = f"✅ {timestamp} — These floorplans are NOW AVAILABLE:\n" + \
                  "\n".join(f"• {name}" for name in available_matches)
        print(message)
        send_sms(message)
        send_email("Apartment Alert", message)
        log_line += "✅ **Available Floorplans:**\n" + "".join(f"- {match}\n" for match in available_matches)
        sheet_status = "Available: " + ", ".join(available_matches)
    else:
        log_line += "🚫 *No matching floorplans available.*\n"
        sheet_status = "No matching floorplans"

    log_line += "\n---\n\n"

    with open("run-history.md", "a") as log_file:
        log_file.write(log_line)

    worksheet.append_row([timestamp, sheet_status])

check_units()
