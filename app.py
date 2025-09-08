from flask import Flask, jsonify, request
import pytz
import datetime
import urllib.parse
import re
from icalevents.icalevents import events
import requests
import ssl
import socket

app = Flask(__name__)



@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": "Welcome to the ICS Calendar API!", "usage": "GET /events?url=<ics_url>&limit=<number_of_events, Default: Infinite>"}), 200


def validate_url(url):
    """Validate and normalize the provided URL"""
    if not url:
        return False, "No URL provided"
    
    # Basic URL validation
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme:
            return False, "URL must include a scheme (http:// or https://)"
        if parsed.scheme not in ['http', 'https']:
            return False, f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are supported"
        if not parsed.netloc:
            return False, "URL must include a hostname"
        return True, None
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"


def detect_html_response(url):
    """Check if a URL returns HTML content instead of iCal data"""
    try:
        # Make a small GET request to check content
        response = requests.get(url, timeout=10, stream=True)
        content_type = response.headers.get('content-type', '').lower()
        
        # If content type clearly indicates HTML, return an error
        if 'text/html' in content_type:
            return True, "The server returned an HTML page instead of calendar data. Please check the URL."
        
        # If content type suggests calendar data, it's probably good
        if any(cal_type in content_type for cal_type in ['text/calendar', 'application/calendar', 'text/plain']):
            return False, None
        
        # If content type is ambiguous, check the actual content
        # Read only the first 1024 bytes to check for HTML
        chunk = next(response.iter_content(chunk_size=1024), b'')
        chunk_str = chunk.decode('utf-8', errors='ignore').strip().lower()
        
        # Check for obvious HTML markers
        if chunk_str.startswith('<!doctype html') or chunk_str.startswith('<html') or '<head>' in chunk_str[:200]:
            return True, "The server returned an HTML page instead of calendar data. Please check the URL."
        
        # Check for iCal markers
        if chunk_str.startswith('begin:vcalendar') or 'begin:vevent' in chunk_str:
            return False, None
                
        return False, None
        
    except requests.exceptions.Timeout:
        return False, "Request timed out while checking URL"
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to the server"
    except Exception as e:
        return False, f"Error checking URL: {str(e)}"


@app.route('/events', methods=['GET'])
def calendar_data():
    
    ics_url = request.args.get('url', type=str)
    limit = request.args.get('limit', default=None, type=int)

    if not ics_url:
        return jsonify({"error": "No URL provided"}), 400

    # Validate the URL
    is_valid, error_msg = validate_url(ics_url)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    # Calculate the start and end date
    now_utc = datetime.datetime.now(pytz.utc)
    start_of_today = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start_of_today + datetime.timedelta(days=365)

    # Fetch and parse iCal events with comprehensive error handling
    try:
        ev = events(ics_url, start=now_utc, end=end)
    except requests.exceptions.ConnectionError as e:
        print(f"ConnectionError: Could not connect to {ics_url} - {str(e)}")
        return jsonify({
            "error": "Could not connect to the server. Please check the URL and try again.",
            "details": str(e)
        }), 503
    except requests.exceptions.Timeout as e:
        print(f"Timeout: Request to {ics_url} timed out - {str(e)}")
        return jsonify({
            "error": "Request timed out. The server took too long to respond.",
            "details": str(e)
        }), 504
    except requests.exceptions.HTTPError as e:
        print(f"HTTPError: HTTP error {e.response.status_code} for {ics_url} - {str(e)}")
        return jsonify({
            "error": f"HTTP error occurred: {e.response.status_code}",
            "details": str(e)
        }), 502
    except requests.exceptions.RequestException as e:
        print(f"RequestException: Network error for {ics_url} - {str(e)}")
        return jsonify({
            "error": "Network error occurred while fetching calendar data.",
            "details": str(e)
        }), 502
    except ssl.SSLError as e:
        print(f"SSLError: SSL certificate error for {ics_url} - {str(e)}")
        return jsonify({
            "error": "SSL certificate error. The server's certificate may be invalid.",
            "details": str(e)
        }), 502
    except socket.gaierror as e:
        print(f"DNS Error: Failed to resolve hostname for {ics_url} - {str(e)}")
        return jsonify({
            "error": "DNS resolution failed. Please check the hostname in the URL.",
            "details": str(e)
        }), 502
    except ValueError as e:
        error_str = str(e).lower()
        if 'calendar' in error_str or 'ical' in error_str or 'parsing' in error_str:
            print(f"ValueError: Invalid calendar data format for {ics_url} - {str(e)}")
            return jsonify({
                "error": "Invalid calendar data format. The server may have returned HTML or corrupted data.",
                "details": str(e)
            }), 400
        else:
            print(f"ValueError: Invalid calendar data for {ics_url} - {str(e)}")
            return jsonify({
                "error": "Invalid calendar data.",
                "details": str(e)
            }), 400
    except Exception as e:
        # Catch-all for any other exceptions
        error_str = str(e).lower()
        if 'host' in error_str and 'resolve' in error_str:
            print(f"Exception: Could not resolve hostname for {ics_url} - {str(e)}")
            return jsonify({
                "error": "Could not resolve hostname. Please check the URL.",
                "details": str(e)
            }), 502
        elif 'not supported url scheme' in error_str:
            print(f"Exception: Unsupported URL scheme for {ics_url} - {str(e)}")
            return jsonify({
                "error": "Unsupported URL scheme. Only http and https are supported.",
                "details": str(e)
            }), 400
        elif 'no host specified' in error_str:
            print(f"Exception: Invalid URL format for {ics_url} - {str(e)}")
            return jsonify({
                "error": "Invalid URL format. Please provide a complete URL with hostname.",
                "details": str(e)
            }), 400
        else:
            print(f"Exception: Unexpected error for {ics_url} - {str(e)}")
            return jsonify({
                "error": "An unexpected error occurred while processing the calendar data.",
                "details": str(e)
            }), 500

    events_list = []

    # Process events with error handling
    try:
        for event in ev:
            try:
                # Preserve original timezone information instead of converting to UTC
                start = event.start
                end = event.end
                
                # Ensure we have timezone-aware datetimes
                if start.tzinfo is None:
                    # If no timezone info, assume local timezone
                    start = pytz.utc.localize(start)
                if end.tzinfo is None:
                    # If no timezone info, assume local timezone  
                    end = pytz.utc.localize(end)
                    
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
            except Exception as e:
                # Log the error but continue processing other events
                print(f"Warning: Skipped malformed event: {e}")
                continue
        
        # Sort the events by start time
        events_list.sort(key=lambda x: x['start'])

        # Limit the number of events if a limit is provided
        if limit is not None:
            events_list = events_list[:limit]

        return jsonify({"events": events_list})
        
    except Exception as e:
        print(f"Exception: Error processing calendar events for {ics_url} - {str(e)}")
        return jsonify({
            "error": "Error processing calendar events.",
            "details": str(e)
        }), 500


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8076)
