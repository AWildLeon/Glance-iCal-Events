import os
import requests
from flask import Flask, jsonify
import datetime
import pytz

app = Flask(__name__)

# Your saved credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
REDIRECT_URI = "http://localhost:8075"

# Get access token from refresh token
def get_access_token():
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }
    
    response = requests.post(token_url, data=data)
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        return None

# Fetch Google Calendar events
def get_calendar_events():
    access_token = get_access_token()
    if not access_token:
        return []

    calendar_url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    current_time = datetime.datetime.now(pytz.utc)
    time_min = current_time.isoformat()
    time_max = (current_time + datetime.timedelta(days=30)).isoformat()

    params = {
        "timeMin": time_min,
        "timeMax": time_max,
        "singleEvents": True,
        "orderBy": "startTime",
    }

    response = requests.get(calendar_url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get('items', [])
    else:
        return []

@app.route('/data')
def calendar_data():
    events = get_calendar_events()
    return jsonify({"events": events})

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8075)
