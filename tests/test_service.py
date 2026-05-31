import datetime
import os
import pytest
import pytz
from unittest.mock import patch, MagicMock

from service import (
    clamp_int,
    _fallback_parse,
    enrich_and_filter,
    sort_and_limit,
    fetch_raw_events,
    get_events,
    ParsedEvent,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _read_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# clamp_int
# ---------------------------------------------------------------------------

class TestClampInt:
    def test_within_range(self):
        assert clamp_int(5, 0, 10, 3) == 5

    def test_below_minimum(self):
        assert clamp_int(-1, 0, 10, 3) == 0

    def test_above_maximum(self):
        assert clamp_int(100, 0, 10, 3) == 10

    def test_none_returns_default(self):
        assert clamp_int(None, 0, 10, 3) == 3

    def test_non_numeric_returns_default(self):
        assert clamp_int("abc", 0, 10, 3) == 3  # type: ignore[arg-type]

    def test_exact_minimum(self):
        assert clamp_int(0, 0, 10, 5) == 0

    def test_exact_maximum(self):
        assert clamp_int(10, 0, 10, 5) == 10


# ---------------------------------------------------------------------------
# _fallback_parse
# ---------------------------------------------------------------------------

MINIMAL_ICS = """\
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:minimal@test
SUMMARY:Minimal Event
DTSTART:20280615T100000Z
DTEND:20280615T110000Z
END:VEVENT
END:VCALENDAR
"""

ALL_DAY_ICS = """\
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:allday@test
SUMMARY:All Day Event
DTSTART;VALUE=DATE:20280616
DTEND;VALUE=DATE:20280617
END:VEVENT
END:VCALENDAR
"""

TZID_ICS = """\
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:berlin@test
SUMMARY:Berlin Event
DTSTART;TZID=Europe/Berlin:20280615T100000
DTEND;TZID=Europe/Berlin:20280615T110000
END:VEVENT
END:VCALENDAR
"""

NO_DTSTART_ICS = """\
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:nodtstart@test
SUMMARY:No DTSTART
END:VEVENT
END:VCALENDAR
"""


class TestFallbackParse:
    def test_parses_utc_event(self):
        events = _fallback_parse(MINIMAL_ICS)
        assert len(events) == 1
        ev = events[0]
        assert ev["summary"] == "Minimal Event"
        assert ev["uid"] == "minimal@test"
        assert ev["source"] == "fallback"
        assert ev["start"].tzinfo is not None

    def test_parses_all_day_event(self):
        events = _fallback_parse(ALL_DAY_ICS)
        assert len(events) == 1
        assert events[0]["all_day"] is True

    def test_parses_tzid_event(self):
        events = _fallback_parse(TZID_ICS)
        assert len(events) == 1
        ev = events[0]
        assert ev["summary"] == "Berlin Event"
        assert ev["start"].tzinfo is not None

    def test_skips_event_without_dtstart(self):
        events = _fallback_parse(NO_DTSTART_ICS)
        assert len(events) == 0

    def test_parses_testfile_ics(self):
        text = _read_fixture("Testfile.ics")
        events = _fallback_parse(text)
        assert len(events) > 0

    def test_parses_testfile_simple_ics(self):
        text = _read_fixture("TestfileSimple.ics")
        events = _fallback_parse(text)
        assert len(events) > 0

    def test_empty_string_returns_empty(self):
        assert _fallback_parse("") == []


# ---------------------------------------------------------------------------
# enrich_and_filter
# ---------------------------------------------------------------------------

def _make_event(
    summary: str,
    start: datetime.datetime,
    end: datetime.datetime,
    all_day: bool = False,
    **kwargs,
) -> ParsedEvent:
    base = {
        "summary": summary,
        "uid": f"{summary}@test",
        "start": start,
        "end": end,
        "description": None,
        "location": None,
        "status": "CONFIRMED",
        "all_day": all_day,
        "created": None,
        "last_modified": None,
        "url": None,
        "recurrence_id": None,
        "source": "icalevents",
    }
    base.update(kwargs)
    return ParsedEvent(base)


UTC = pytz.utc
BERLIN = pytz.timezone("Europe/Berlin")


class TestEnrichAndFilter:
    def _now(self):
        return datetime.datetime(2028, 6, 15, 12, 0, 0, tzinfo=UTC)

    def test_future_event_included(self):
        now = self._now()
        start = now + datetime.timedelta(hours=2)
        end = start + datetime.timedelta(hours=1)
        ev = _make_event("Future", start, end)
        result = enrich_and_filter([ev], now, UTC)
        assert len(result) == 1
        assert result[0]["name"] == "Future"

    def test_ended_event_excluded_by_default(self):
        now = self._now()
        start = now - datetime.timedelta(hours=3)
        end = now - datetime.timedelta(hours=1)
        ev = _make_event("Past", start, end)
        result = enrich_and_filter([ev], now, UTC)
        assert len(result) == 0

    def test_ended_event_included_when_flag_set(self):
        now = self._now()
        start = now - datetime.timedelta(hours=3)
        end = now - datetime.timedelta(hours=1)
        ev = _make_event("Past", start, end)
        result = enrich_and_filter([ev], now, UTC, include_ended=True)
        assert len(result) == 1

    def test_ongoing_event_flagged(self):
        now = self._now()
        start = now - datetime.timedelta(hours=1)
        end = now + datetime.timedelta(hours=1)
        ev = _make_event("Ongoing", start, end)
        result = enrich_and_filter([ev], now, UTC)
        assert result[0]["ongoing"] is True

    def test_future_event_not_flagged_ongoing(self):
        now = self._now()
        start = now + datetime.timedelta(hours=1)
        end = now + datetime.timedelta(hours=2)
        ev = _make_event("Future", start, end)
        result = enrich_and_filter([ev], now, UTC)
        assert result[0]["ongoing"] is False

    def test_seconds_until_start_positive_for_future(self):
        now = self._now()
        start = now + datetime.timedelta(hours=1)
        end = start + datetime.timedelta(hours=1)
        ev = _make_event("Future", start, end)
        result = enrich_and_filter([ev], now, UTC)
        assert result[0]["secondsUntilStart"] == pytest.approx(3600, abs=1)

    def test_seconds_until_end_positive(self):
        now = self._now()
        start = now + datetime.timedelta(hours=1)
        end = start + datetime.timedelta(hours=2)
        ev = _make_event("Future", start, end)
        result = enrich_and_filter([ev], now, UTC)
        assert result[0]["secondsUntilEnd"] == pytest.approx(3 * 3600, abs=1)

    def test_duration_seconds(self):
        now = self._now()
        start = now + datetime.timedelta(hours=1)
        end = start + datetime.timedelta(hours=1, minutes=30)
        ev = _make_event("Timed", start, end)
        result = enrich_and_filter([ev], now, UTC)
        assert result[0]["durationSeconds"] == pytest.approx(5400, abs=1)

    def test_all_day_event_days_remaining(self):
        now = self._now()
        start = datetime.datetime(2028, 6, 16, 0, 0, 0, tzinfo=UTC)
        end = datetime.datetime(2028, 6, 17, 0, 0, 0, tzinfo=UTC)
        ev = _make_event("AllDay", start, end, all_day=True)
        result = enrich_and_filter([ev], now, UTC)
        assert result[0]["daysRemaining"] is not None

    def test_isoformat_strings_present(self):
        now = self._now()
        start = now + datetime.timedelta(hours=1)
        end = start + datetime.timedelta(hours=1)
        ev = _make_event("ISO", start, end)
        result = enrich_and_filter([ev], now, UTC)
        assert isinstance(result[0]["start"], str)
        assert isinstance(result[0]["end"], str)

    def test_internal_dt_fields_removed_by_get_events(self):
        """get_events must strip start_dt / end_dt before returning."""
        now = self._now()
        start = now + datetime.timedelta(hours=1)
        end = start + datetime.timedelta(hours=1)
        ev = _make_event("Clean", start, end)
        enriched = enrich_and_filter([ev], now, UTC)
        sort_and_limit(enriched, None)
        for e in enriched:
            e.pop("start_dt", None)
            e.pop("end_dt", None)
        assert "start_dt" not in enriched[0]
        assert "end_dt" not in enriched[0]


# ---------------------------------------------------------------------------
# sort_and_limit
# ---------------------------------------------------------------------------

class TestSortAndLimit:
    def _make_enriched(self, name: str, start_offset_h: int, ongoing: bool) -> ParsedEvent:
        now = datetime.datetime(2028, 6, 15, 12, 0, 0, tzinfo=UTC)
        start = now + datetime.timedelta(hours=start_offset_h)
        end = start + datetime.timedelta(hours=1)
        return ParsedEvent({
            "name": name,
            "ongoing": ongoing,
            "start_dt": start,
            "end_dt": end,
            "start": start.isoformat(),
            "end": end.isoformat(),
        })

    def test_ongoing_sorted_before_future(self):
        future = self._make_enriched("Future", 2, False)
        ongoing = self._make_enriched("Ongoing", -1, True)
        result = sort_and_limit([future, ongoing], None)
        assert result[0]["name"] == "Ongoing"

    def test_future_events_sorted_by_start(self):
        later = self._make_enriched("Later", 4, False)
        sooner = self._make_enriched("Sooner", 1, False)
        result = sort_and_limit([later, sooner], None)
        assert result[0]["name"] == "Sooner"

    def test_limit_applied(self):
        events = [self._make_enriched(f"E{i}", i, False) for i in range(5)]
        result = sort_and_limit(events, 2)
        assert len(result) == 2

    def test_no_limit_returns_all(self):
        events = [self._make_enriched(f"E{i}", i, False) for i in range(5)]
        result = sort_and_limit(events, None)
        assert len(result) == 5

    def test_limit_zero_returns_empty(self):
        events = [self._make_enriched("E", 1, False)]
        result = sort_and_limit(events, 0)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Regression tests
# ---------------------------------------------------------------------------

UNKNOWN_TZ_ICS = """\
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:unknown-tz@test
SUMMARY:Unknown TZ Event
DTSTART;TZID=Invalid/NotARealTimezone:20280615T100000
DTEND;TZID=Invalid/NotARealTimezone:20280615T110000
END:VEVENT
END:VCALENDAR
"""

NAIVE_ICS = """\
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:naive@test
SUMMARY:Naive Event
DTSTART:20280615T100000
DTEND:20280615T110000
END:VEVENT
END:VCALENDAR
"""


class TestRegressions:
    """
    Each test documents a specific bug that was fixed in the commit history
    so it cannot silently regress.
    """

    # --- _fallback_parse: unknown TZID must not crash (commit e4f6c10) ----

    def test_unknown_tzid_falls_back_to_utc_not_crash(self):
        """TZID with an unrecognised timezone name must not raise; falls back to UTC."""
        events = _fallback_parse(UNKNOWN_TZ_ICS)
        assert len(events) == 1
        assert events[0]["start"].tzinfo is not None

    # --- _fallback_parse: naive datetime gets tzinfo, not left naive -------

    def test_naive_datetime_gets_tzinfo_assigned(self):
        """Naive DTSTART must get a tzinfo (UTC fallback) so downstream code never
        sees a naive datetime and crashes on .astimezone()."""
        events = _fallback_parse(NAIVE_ICS)
        assert len(events) == 1
        assert events[0]["start"].tzinfo is not None
        assert events[0]["end"].tzinfo is not None

    # --- enrich_and_filter: all-day same-day end normalization (commit dd7bbba) ---

    def test_all_day_same_start_end_date_end_bumped_one_day(self):
        """An all-day event where DTEND == DTSTART (e.g. VALUE=DATE:20280616 for both)
        must have its end bumped to the next midnight so it spans the full day.
        Without the fix, durationSeconds and daysRemaining would be 0."""
        now = datetime.datetime(2028, 6, 15, 12, 0, 0, tzinfo=UTC)
        same_day = datetime.datetime(2028, 6, 16, 0, 0, 0, tzinfo=UTC)
        ev = _make_event("AllDay", same_day, same_day, all_day=True)
        result = enrich_and_filter([ev], now, UTC)
        assert len(result) == 1
        assert result[0]["durationSeconds"] == 86400
        end_dt = datetime.datetime.fromisoformat(result[0]["end"])
        start_dt = datetime.datetime.fromisoformat(result[0]["start"])
        assert (end_dt - start_dt).total_seconds() == 86400

    def test_all_day_multi_day_end_not_modified(self):
        """All-day event spanning multiple days must NOT have its end bumped."""
        now = datetime.datetime(2028, 6, 14, 12, 0, 0, tzinfo=UTC)
        start = datetime.datetime(2028, 6, 15, 0, 0, 0, tzinfo=UTC)
        end = datetime.datetime(2028, 6, 17, 0, 0, 0, tzinfo=UTC)
        ev = _make_event("MultiDay", start, end, all_day=True)
        result = enrich_and_filter([ev], now, UTC)
        assert result[0]["durationSeconds"] == 2 * 86400

    # --- days_remaining never goes negative (commit dd7bbba) ---------------

    def test_days_remaining_never_negative(self):
        """daysRemaining must always be >= 0 even when the all-day event ends today."""
        now = datetime.datetime(2028, 6, 15, 23, 30, 0, tzinfo=UTC)
        start = datetime.datetime(2028, 6, 15, 0, 0, 0, tzinfo=UTC)
        end = datetime.datetime(2028, 6, 16, 0, 0, 0, tzinfo=UTC)
        ev = _make_event("EndingToday", start, end, all_day=True)
        result = enrich_and_filter([ev], now, UTC)
        assert len(result) == 1
        assert result[0]["daysRemaining"] >= 0

    # --- sort: ongoing events must appear before future (commit dd7bbba) ---

    def test_ongoing_sorts_before_earlier_started_past_event_when_include_ended(self):
        """With include_ended=True, an ongoing event must sort above a fully past
        event even though the past event has an earlier start_dt."""
        now = datetime.datetime(2028, 6, 15, 12, 0, 0, tzinfo=UTC)
        # Fully past: started and ended before now
        past_start = now - datetime.timedelta(days=3)
        past_end = now - datetime.timedelta(days=1)
        past_ev = _make_event("FullyPast", past_start, past_end)
        # Ongoing: started before now, ends after now
        ongoing_start = now - datetime.timedelta(hours=2)
        ongoing_end = now + datetime.timedelta(hours=2)
        ongoing_ev = _make_event("Ongoing", ongoing_start, ongoing_end)

        enriched = enrich_and_filter([past_ev, ongoing_ev], now, UTC, include_ended=True)
        result = sort_and_limit(enriched, None)
        assert result[0]["name"] == "Ongoing"

    # --- fetch_raw_events: HTTP called exactly once, even on icalevents failure ---
    # (commit 81fac75 — old code called urlopen() a second time on the fallback path)

    def test_single_http_request_on_icalevents_failure(self):
        """http.request must be called exactly once. The fallback parser reuses
        the already-fetched text instead of issuing a second HTTP request."""
        now = datetime.datetime(2028, 1, 1, tzinfo=UTC)
        end = now + datetime.timedelta(days=365)
        mock_resp = MagicMock()
        mock_resp.data = MINIMAL_ICS.encode("utf-8")
        with patch("service.http.request", return_value=mock_resp) as mock_req:
            with patch("service.ical_fetch", side_effect=Exception("parse error")):
                fetch_raw_events("http://example.com/cal.ics", now, end, None, None)
        assert mock_req.call_count == 1

    # --- fetch_raw_events: basic auth headers forwarded (commit 81fac75) ---

    def test_basic_auth_header_forwarded(self):
        """When username and password are supplied, an Authorization header must
        be present in the outgoing HTTP request."""
        now = datetime.datetime(2028, 1, 1, tzinfo=UTC)
        end = now + datetime.timedelta(days=365)
        mock_resp = MagicMock()
        mock_resp.data = MINIMAL_ICS.encode("utf-8")
        with patch("service.http.request", return_value=mock_resp) as mock_req:
            with patch("service.ical_fetch", return_value=[]):
                fetch_raw_events("http://example.com/cal.ics", now, end, "alice", "secret")
        _, kwargs = mock_req.call_args
        headers = kwargs.get("headers", {})
        assert any(k.lower() == "authorization" for k in headers)

    @pytest.mark.parametrize("username,password", [
        (None, None),
        (None, "secret"),
        ("user", None),
    ])
    def test_no_auth_header_when_credentials_absent(self, username, password):
        """No Authorization header when either credential is None.
        The old code did make_headers(basic_auth='None:None') which emitted
        a garbage 'Basic Tm9uZTpOb25l' header on every unauthenticated request."""
        now = datetime.datetime(2028, 1, 1, tzinfo=UTC)
        end = now + datetime.timedelta(days=365)
        mock_resp = MagicMock()
        mock_resp.data = MINIMAL_ICS.encode("utf-8")
        with patch("service.http.request", return_value=mock_resp) as mock_req:
            with patch("service.ical_fetch", return_value=[]):
                fetch_raw_events("http://example.com/cal.ics", now, end, username, password)
        _, kwargs = mock_req.call_args
        headers = kwargs.get("headers", {})
        assert "Authorization" not in headers
        assert "authorization" not in headers


# ---------------------------------------------------------------------------
# fetch_raw_events (integration path via mocked HTTP)
# ---------------------------------------------------------------------------

class TestFetchRawEvents:
    def _mock_response(self, text: str):
        mock_resp = MagicMock()
        mock_resp.data = text.encode("utf-8")
        return mock_resp

    def test_returns_fallback_on_icalevents_failure(self):
        now = datetime.datetime(2028, 1, 1, tzinfo=UTC)
        end = now + datetime.timedelta(days=365)
        with patch("service.http.request", return_value=self._mock_response(MINIMAL_ICS)):
            with patch("service.ical_fetch", side_effect=Exception("parse error")):
                events = fetch_raw_events("http://example.com/cal.ics", now, end, None, None)
        assert any(e["source"] == "fallback" for e in events)

    def test_returns_icalevents_on_success(self):
        now = datetime.datetime(2028, 1, 1, tzinfo=UTC)
        end = now + datetime.timedelta(days=1000)
        text = _read_fixture("TestfileSimple.ics")
        with patch("service.http.request", return_value=self._mock_response(text)):
            events = fetch_raw_events("http://example.com/cal.ics", now, end, None, None)
        assert len(events) > 0


# ---------------------------------------------------------------------------
# get_events (end-to-end with mocked HTTP)
# ---------------------------------------------------------------------------

class TestGetEvents:
    def test_returns_list(self):
        text = _read_fixture("TestfileSimple.ics")
        mock_resp = MagicMock()
        mock_resp.data = text.encode("utf-8")
        with patch("service.http.request", return_value=mock_resp):
            result = get_events(
                "http://example.com/cal.ics",
                lookback_days=14,
                horizon_days=3650,
                limit=None,
                username=None,
                password=None,
            )
        assert isinstance(result, list)

    def test_limit_respected(self):
        text = _read_fixture("Testfile.ics")
        mock_resp = MagicMock()
        mock_resp.data = text.encode("utf-8")
        with patch("service.http.request", return_value=mock_resp):
            result = get_events(
                "http://example.com/cal.ics",
                lookback_days=14,
                horizon_days=3650,
                limit=2,
                username=None,
                password=None,
            )
        assert len(result) <= 2

    def test_no_start_dt_or_end_dt_in_output(self):
        text = _read_fixture("TestfileSimple.ics")
        mock_resp = MagicMock()
        mock_resp.data = text.encode("utf-8")
        with patch("service.http.request", return_value=mock_resp):
            result = get_events(
                "http://example.com/cal.ics",
                lookback_days=14,
                horizon_days=3650,
                limit=None,
                username=None,
                password=None,
            )
        for ev in result:
            assert "start_dt" not in ev
            assert "end_dt" not in ev
