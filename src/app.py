import logging
from urllib.parse import unquote
from flask import Flask, jsonify, request
from service import get_events, clamp_int

app = Flask(__name__)
logger = logging.getLogger(__name__)



@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "message": "Welcome to the ICS Calendar API!",
        "usage": "GET /events?url=<ics_url>&limit=<number_of_events, Default: Infinite>",
        "note": "Use 'encoded_url' instead of 'url' if your ICS URL is already percent-encoded."
    }), 200


@app.route('/events', methods=['GET'])
def calendar_data():

    raw_url = request.args.get('url', type=str)
    encoded_url = request.args.get('encoded_url', type=str)
    limit = request.args.get('limit', default=None, type=int)
    lookback_days = request.args.get('lookback_days', default=14, type=int)
    horizon_days = request.args.get('horizon_days', default=3650, type=int)
    auth_user = request.args.get('username', type=str)
    auth_pass = request.args.get('password', type=str)

    if raw_url and encoded_url:
        return jsonify({"error": "Provide only one of 'url' or 'encoded_url', not both"}), 400

    if encoded_url:
        ics_url = unquote(encoded_url)
    else:
        ics_url = raw_url

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
            include_ended=False,
            username=auth_user,
            password=auth_pass
        )
    except Exception:
        logger.exception("Failed to retrieve events")
        return jsonify({"error": "Failed to retrieve events"}), 400

    return jsonify({"events": events_out})


if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=8076)
