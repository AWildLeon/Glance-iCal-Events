from flask import Flask, jsonify, request
from service import get_events, clamp_int

app = Flask(__name__)



@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": "Welcome to the ICS Calendar API!", "usage": "GET /events?url=<ics_url>&limit=<number_of_events, Default: Infinite>"}), 200


@app.route('/events', methods=['GET'])
def calendar_data():

    ics_url = request.args.get('url', type=str)
    limit = request.args.get('limit', default=None, type=int)
    lookback_days = request.args.get('lookback_days', default=14, type=int)
    horizon_days = request.args.get('horizon_days', default=3650, type=int)

    if not ics_url:
        return jsonify({"error": "No URL provided"}), 400

    # Clamp values to avoid abuse / extreme ranges
    lookback_days = clamp_int(lookback_days, 0, 90, 14)
    horizon_days = clamp_int(horizon_days, 1, 3660, 3650)

    try:
        events_out = get_events(
            ics_url,
            lookback_days=lookback_days,
            horizon_days=horizon_days,
            limit=limit,
            include_ended=False
        )
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve events: {str(e)}"}), 400

    return jsonify({"events": events_out})


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8076)
