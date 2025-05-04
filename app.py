import requests
from flask import Flask, jsonify
import datetime
import pytz
from ics import Calendar
from arrow import Arrow
import os


app = Flask(__name__)

ics_url = os.environ.get("ics_url")

@app.route('/', methods=['GET'])
def usage():
    return 'Usage:\nGET /events'


@app.route('/events', methods=['GET'])
def calendar_data():
    # Fetch the ICS data with error handling
    try:
        response = requests.get(ics_url)
        response.raise_for_status()
    except requests.RequestException as err:
        return jsonify({"error": f"Could not fetch calendar: {err}"}), 502

    # Parse calendar and get current time in UTC
    cal = Calendar(response.text)

    events = []
    now = datetime.datetime.now(pytz.utc)
    startpoint = Arrow(now.year, now.month, now.day, tzinfo='UTC')

    # For each event, find its next occurrence using the calendar timeline
    for event in cal.timeline.start_after(startpoint):
        events.append({
            "name": event.name,
            "begin": event.begin.datetime.isoformat(),
            "duration": event.duration.total_seconds(),
            "end": event.end.datetime.isoformat(),
            "description": event.description,
            "location": event.location,
            "url": event.url,
            "status": event.status,
            "created": event.created.datetime.isoformat() if event.created else None,
            "last_modified": event.last_modified.datetime.isoformat() if event.last_modified else None,
            "uid": event.uid,
        })
    

    return jsonify({"events": events})


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8076)
