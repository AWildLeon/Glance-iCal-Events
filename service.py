import datetime
import pytz
import re
from typing import List, Dict, Any, Optional
from icalevents.icalevents import events as ical_fetch
from dateutil import parser as date_parser
from icalevents.icalparser import Event as ICalEvent


class ParsedEvent(Dict[str, Any]):
    pass


def clamp_int(value: Optional[int], minimum: int, maximum: int, default: int) -> int:
    if value is None:
        return default
    try:
        v = int(value)
    except Exception:
        return default
    if v < minimum:
        v = minimum
    if v > maximum:
        v = maximum
    return v


def _fallback_parse(ics_text: str) -> List[ParsedEvent]:
    """Very small, defensive parser for VEVENT blocks when icalevents chokes.
    Only extracts DTSTART/DTEND/SUMMARY/UID/DESCRIPTION/LOCATION/STATUS.
    """
    vevents = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ics_text, flags=re.DOTALL | re.IGNORECASE)
    results: List[ParsedEvent] = []
    for block in vevents:
        m = re.search(r"^DTSTART(?:;([^:]+))?:(.+)$", block, flags=re.MULTILINE)
        if not m:
            continue
        params = m.group(1) or ''
        dtstart_raw = m.group(2).strip()
        m2 = re.search(r"^DTEND(?:;([^:]+))?:(.+)$", block, flags=re.MULTILINE)
        dtend_raw = m2.group(2).strip() if m2 else None

        def _grab(name: str):
            mm = re.search(rf"^{name}:(.+)$", block, flags=re.MULTILINE)
            return mm.group(1).strip() if mm else None

        summary = _grab('SUMMARY')
        uid = _grab('UID')
        description = _grab('DESCRIPTION')
        location = _grab('LOCATION')
        status = _grab('STATUS')

        tzname = None
        if 'TZID=' in params:
            mtz = re.search(r"TZID=([^;]+)", params)
            if mtz:
                tzname = mtz.group(1)

        def _parse_dt(raw: str):
            if raw.endswith('Z'):
                return date_parser.isoparse(raw)
            if re.match(r"^\d{8}$", raw):  # date only
                d = datetime.datetime.strptime(raw, '%Y%m%d').date()
                return datetime.datetime(d.year, d.month, d.day)
            return date_parser.parse(raw)

        try:
            start_dt = _parse_dt(dtstart_raw)
            end_dt = _parse_dt(dtend_raw) if dtend_raw else start_dt
        except Exception:
            continue

        if start_dt.tzinfo is None:
            if tzname:
                try:
                    start_dt = pytz.timezone(tzname).localize(start_dt)
                except Exception:
                    start_dt = start_dt.replace(tzinfo=pytz.utc)
            else:
                start_dt = start_dt.replace(tzinfo=pytz.utc)
        if end_dt.tzinfo is None:
            if tzname:
                try:
                    end_dt = pytz.timezone(tzname).localize(end_dt)
                except Exception:
                    end_dt = end_dt.replace(tzinfo=pytz.utc)
            else:
                end_dt = end_dt.replace(tzinfo=pytz.utc)

        all_day = False
        # Recognize VALUE=DATE by having parsed start at midnight and original raw date format length of 8
        if re.match(r"^\d{8}$", dtstart_raw):
            all_day = True

        results.append(ParsedEvent({
            'summary': summary,
            'uid': uid,
            'start': start_dt,
            'end': end_dt,
            'description': description,
            'location': location,
            'status': status,
            'all_day': all_day,
            'source': 'fallback'
        }))
    return results


def fetch_raw_events(url: str, start: datetime.datetime, end: datetime.datetime) -> List[ParsedEvent]:
    """Fetch events via icalevents first; on failure, fallback to lightweight parser."""
    try:
        lib_events: List[ICalEvent] = ical_fetch(url, start=start, end=end, strict=False)
        parsed: List[ParsedEvent] = []
        for ev in lib_events:
            st = ev.start
            en = ev.end or ev.start
            parsed.append(ParsedEvent({
                'summary': ev.summary,
                'uid': ev.uid,
                'start': st,
                'end': en,
                'description': ev.description,
                'location': ev.location,
                'status': ev.status,
                'all_day': ev.all_day,
                'created': ev.created,
                'last_modified': ev.last_modified,
                'url': ev.url,
                'recurrence_id': ev.recurrence_id,
                'source': 'icalevents'
            }))
        return parsed
    except Exception:
        # fallback
        from urllib.request import urlopen
        with urlopen(url, timeout=15) as resp:
            text = resp.read().decode('utf-8', errors='ignore')
        return _fallback_parse(text)


def enrich_and_filter(raw_events: List[ParsedEvent], now_local: datetime.datetime, local_tz, include_ended=False) -> List[ParsedEvent]:
    enriched: List[ParsedEvent] = []
    for e in raw_events:
        start_local = e['start'].astimezone(local_tz)
        end_local = e['end'].astimezone(local_tz)

        # Normalize all-day events: treat end as exclusive if date-style (advance by a day if start==end)
        if e.get('all_day') and start_local.date() == end_local.date():
            # Make end the next midnight to express full-day span
            end_local = (start_local + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        if not include_ended and end_local <= now_local:
            continue

        ongoing = start_local <= now_local < end_local
        seconds_until_start = (start_local - now_local).total_seconds()
        seconds_until_end = (end_local - now_local).total_seconds()
        duration_seconds = (end_local - start_local).total_seconds()
        days_remaining = None
        if e.get('all_day'):
            days_remaining = max(0, (end_local.date() - now_local.date()).days - (0 if ongoing else 1))

        enriched.append(ParsedEvent({
            'name': e.get('summary'),
            'uid': e.get('uid'),
            'start_dt': start_local,
            'end_dt': end_local,
            'start': start_local.isoformat(),
            'end': end_local.isoformat(),
            'all_day': e.get('all_day'),
            'secondsUntilStart': seconds_until_start,
            'secondsUntilEnd': seconds_until_end,
            'durationSeconds': duration_seconds,
            'daysRemaining': days_remaining,
            'ongoing': ongoing,
            'url': e.get('url'),
            'description': e.get('description'),
            'location': e.get('location'),
            'status': e.get('status'),
            'created': e.get('created').isoformat() if e.get('created') else None,
            'last_modified': e.get('last_modified').isoformat() if e.get('last_modified') else None,
            'recurrence_id': e.get('recurrence_id'),
            'source': e.get('source')
        }))
    return enriched


def sort_and_limit(enriched: List[ParsedEvent], limit: Optional[int]) -> List[ParsedEvent]:
    enriched.sort(key=lambda ev: (not ev['ongoing'], ev['start_dt']))
    if limit is not None:
        return enriched[:limit]
    return enriched


def get_events(url: str, lookback_days: int, horizon_days: int, limit: Optional[int], include_ended=False) -> List[ParsedEvent]:
    now_utc = datetime.datetime.now(pytz.utc)
    start = now_utc - datetime.timedelta(days=lookback_days)
    end = now_utc + datetime.timedelta(days=horizon_days)
    local_tz = datetime.datetime.now().astimezone().tzinfo
    now_local = now_utc.astimezone(local_tz)
    raw = fetch_raw_events(url, start, end)
    enriched = enrich_and_filter(raw, now_local, local_tz, include_ended=include_ended)
    final = sort_and_limit(enriched, limit)
    # Remove internal dt objects
    for ev in final:
        ev.pop('start_dt', None)
        ev.pop('end_dt', None)
    return final
