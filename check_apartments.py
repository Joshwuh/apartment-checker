import requests
from twilio.rest import Client
from datetime import datetime
import smtplib
from email.message import EmailMessage
import os

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
    print(f"🕒 Script started at {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print(f"Layouts found: {len(layouts)}")
    print(f"Units found: {len(units)}")

    response = requests.get(url)
    data = response.json()

    layouts = data['units_data']['layouts']
    units = data['units_data']['units']

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

    if available_matches:
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        message = f"✅ {timestamp} — These floorplans are NOW AVAILABLE:\n" + \
                  "\n".join(f"• {name}" for name in available_matches)

        print(message)
        send_sms(message)
        send_email("Apartment Alert", message)

check_units()
