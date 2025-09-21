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
    end = start_of_today + datetime.timedelta(days=365 * 10)  # 10 years for testing

    try:
        ev = events(ics_url, start=start_of_today, end=end)
    except Exception as e:
        return jsonify({"error": f"Failed to parse calendar: {str(e)}"}), 400
        
    events_list = []

    # For each event, find its next occurrence using the calendar timeline
    for event in ev:
        try:
            # The icalevents library converts everything to UTC, but we need to handle timezone properly
            # Get the original start and end times (they're already in UTC from icalevents)
            start_utc = event.start
            end_utc = event.end
            
            # Get the system's local timezone
            local_tz = datetime.datetime.now().astimezone().tzinfo
            
            # Convert UTC times to local timezone for display
            start_local = start_utc.astimezone(local_tz)
            end_local = end_utc.astimezone(local_tz)
                    
            events_list.append({
                "name": event.summary,
                "start": start_local.isoformat(),
                "end": end_local.isoformat(),
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
        except Exception as e:
            print(f"Error processing event: {e}")
            # Skip this event and continue with the next one
            continue
    
    # Sort the events by start time
    events_list.sort(key=lambda x: x['start'])

    # Limit the number of events if a limit is provided
    if limit is not None:
        events_list = events_list[:limit]

    return jsonify({"events": events_list})


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8076)
