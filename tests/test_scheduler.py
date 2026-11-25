# SPDX-License-Identifier: GPL-3.0-or-later
"""Test scheduler 07:17 (offline, inclusi casi limite)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from alba.serve import next_run, seconds_until_next_run

TZ = "Europe/Rome"


def _dt(y, m, d, h, minute):
    return datetime(y, m, d, h, minute, tzinfo=ZoneInfo(TZ))


def test_next_run_before_0717_is_today():
    now = _dt(2026, 11, 25, 6, 0)
    assert next_run(now, 7, 17, TZ) == _dt(2026, 11, 25, 7, 17)


def test_next_run_after_0717_is_tomorrow():
    now = _dt(2026, 11, 25, 8, 0)
    assert next_run(now, 7, 17, TZ) == _dt(2026, 11, 26, 7, 17)


def test_next_run_exactly_at_0717_is_tomorrow():
    now = _dt(2026, 11, 25, 7, 17)
    assert next_run(now, 7, 17, TZ) == _dt(2026, 11, 26, 7, 17)


def test_next_run_late_night_is_tomorrow_morning():
    now = _dt(2026, 11, 25, 23, 30)
    assert next_run(now, 7, 17, TZ) == _dt(2026, 11, 26, 7, 17)


def test_next_run_across_dst_start():
    # 29 mar 2026: ora legale, 02:00 -> 03:00. Alle 07:17 del 29 mar
    # il prossimo run è quello stesso giorno.
    now = _dt(2026, 3, 29, 6, 0)
    target = next_run(now, 7, 17, TZ)
    assert (target.day, target.hour, target.minute) == (29, 7, 17)


def test_next_run_across_dst_end():
    # 25 ott 2026: ora solare, 03:00 -> 02:00 (ora ripetuta).
    now = _dt(2026, 10, 25, 8, 0)
    target = next_run(now, 7, 17, TZ)
    assert (target.day, target.hour, target.minute) == (26, 7, 17)


def test_seconds_until_next_run_positive_and_bounded():
    now = _dt(2026, 11, 25, 6, 0)
    secs = seconds_until_next_run(now, 7, 17, TZ)
    assert 0 < secs <= 24 * 3600
    assert secs == 77 * 60  # 06:00 -> 07:17
