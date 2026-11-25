# SPDX-License-Identifier: GPL-3.0-or-later
"""Test parsing ICS fatto a mano (offline)."""

from datetime import date

import pytest

from alba.calendar_ics import (
    CalendarError,
    events_today,
    fetch_today_events,
    parse_ics,
)
from alba.fixtures import SAMPLE_ICS

TODAY = date(2026, 11, 25)


def test_parse_sample_ics_counts_events():
    events = parse_ics(SAMPLE_ICS)
    assert len(events) == 3


def test_events_today_filters_yesterday():
    events = events_today(parse_ics(SAMPLE_ICS), "Europe/Rome", today=TODAY)
    assert len(events) == 2
    assert events[0].summary == "Lezione di matematica"
    assert events[1].summary == "Palestra — gambe"


def test_event_times_and_format():
    events = events_today(parse_ics(SAMPLE_ICS), "Europe/Rome", today=TODAY)
    assert events[0].format() == "08:00–09:00 Lezione di matematica"
    assert events[1].format() == "17:00–18:30 Palestra — gambe"


def test_all_day_event():
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:a@alba
DTSTART;VALUE=DATE:20261125
DTEND;VALUE=DATE:20261126
SUMMARY:Festa
END:VEVENT
END:VCALENDAR
"""
    events = events_today(parse_ics(ics), "Europe/Rome", today=TODAY)
    assert len(events) == 1
    assert events[0].all_day
    assert events[0].format() == "Tutto il giorno: Festa"


def test_utc_event_converted_to_local():
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:u@alba
DTSTART:20261125T070000Z
DTEND:20261125T080000Z
SUMMARY:Call UTC
END:VEVENT
END:VCALENDAR
"""
    events = events_today(parse_ics(ics), "Europe/Rome", today=TODAY)
    assert len(events) == 1
    # 07:00 UTC = 08:00 a Roma (fine novembre: +1)
    assert events[0].start.hour == 8
    assert events[0].format().startswith("08:00")


def test_folded_line_unfolded():
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:f@alba
DTSTART;TZID=Europe/Rome:20261125T090000
DTEND;TZID=Europe/Rome:20261125T100000
SUMMARY:Titolo molto
  lungo piegato
END:VEVENT
END:VCALENDAR
"""
    events = parse_ics(ics)
    assert events[0].summary == "Titolo molto lungo piegato"


def test_missing_dtstart_raises():
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:x@alba
SUMMARY:Senza data
END:VEVENT
END:VCALENDAR
"""
    with pytest.raises(CalendarError):
        parse_ics(ics)


def test_fetch_today_events_uses_http_get():
    events = fetch_today_events(
        "https://example.invalid/cal.ics",
        "Europe/Rome",
        http_get=lambda url: SAMPLE_ICS.encode(),
    )
    assert len(events) == 2
