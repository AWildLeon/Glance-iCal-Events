from flask import Flask, jsonify, request
import pytz
import datetime
from icalevents.icalevents import events

app = Flask(__name__)



@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": "Welcome to the ICS Calendar API!", "usage": "GET /events?url=<ics_url>&limit=<number_of_events, Default: Infinite>"}), 200


@app.route('/events', methods=['GET'])
def calendar_data():

    ics_url = request.args.get('url', type=str)
    limit = request.args.get('limit', default=None, type=int)

    if not ics_url:
        return jsonify({"error": "No URL provided"}), 400

    # Calculate the start and end date
    now_utc = datetime.datetime.now(pytz.utc)
    start_of_today = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start_of_today + datetime.timedelta(days=365)

    ev = events(ics_url, start=now_utc, end=end)
    events_list = []

    # # For each event, find its next occurrence using the calendar timeline
    for event in ev:

        start = event.start.astimezone(pytz.utc)
        end = event.end.astimezone(pytz.utc)
        events_list.append({
            "name": event.summary,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "all_day": event.all_day,
            "secondsUntilStart": event.time_left().total_seconds(),
            "url": event.url,
            "description": event.description,
            "location": event.location,
            "status": event.status,
            "created": event.created,
            "last_modified": event.last_modified,
            "uid": event.uid,
            "recurrence_id": event.recurrence_id,
        })
    
    # Sort the events by start time
    events_list.sort(key=lambda x: x['start'])

    # Limit the number of events if a limit is provided
    if limit is not None:
        events_list = events_list[:limit]

    return jsonify({"events": events_list})


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8076)
