import pytest
from unittest.mock import patch
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


class TestIndexRoute:
    def test_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_returns_json(self, client):
        resp = client.get("/")
        data = resp.get_json()
        assert "message" in data


class TestEventsRoute:
    def test_missing_url_returns_400(self, client):
        resp = client.get("/events")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_valid_url_calls_get_events(self, client):
        mock_events = [{"name": "Test Event", "start": "2028-06-15T10:00:00+02:00"}]
        with patch("app.get_events", return_value=mock_events) as mock_fn:
            resp = client.get("/events?url=http://example.com/cal.ics")
        assert resp.status_code == 200
        assert resp.get_json()["events"] == mock_events
        mock_fn.assert_called_once()

    def test_get_events_exception_returns_400(self, client):
        with patch("app.get_events", side_effect=Exception("connection refused")):
            resp = client.get("/events?url=http://example.com/cal.ics")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_limit_param_passed(self, client):
        with patch("app.get_events", return_value=[]) as mock_fn:
            client.get("/events?url=http://example.com/cal.ics&limit=5")
        _, kwargs = mock_fn.call_args
        assert kwargs["limit"] == 5

    def test_lookback_days_clamped(self, client):
        with patch("app.get_events", return_value=[]) as mock_fn:
            client.get("/events?url=http://example.com/cal.ics&lookback_days=999")
        _, kwargs = mock_fn.call_args
        assert kwargs["lookback_days"] <= 90

    def test_horizon_days_clamped(self, client):
        with patch("app.get_events", return_value=[]) as mock_fn:
            client.get("/events?url=http://example.com/cal.ics&horizon_days=99999")
        _, kwargs = mock_fn.call_args
        assert kwargs["horizon_days"] <= 3660

    def test_auth_params_forwarded(self, client):
        with patch("app.get_events", return_value=[]) as mock_fn:
            client.get("/events?url=http://example.com/cal.ics&username=user&password=pass")
        _, kwargs = mock_fn.call_args
        assert kwargs["username"] == "user"
        assert kwargs["password"] == "pass"

    def test_response_has_events_key(self, client):
        with patch("app.get_events", return_value=[]):
            resp = client.get("/events?url=http://example.com/cal.ics")
        assert "events" in resp.get_json()
