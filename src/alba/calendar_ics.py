# SPDX-License-Identifier: GPL-3.0-or-later
"""Calendario da link iCalendar privato di Google Calendar.

Google Calendar -> Impostazioni -> link segreto in formato iCalendar:
un URL lunga durata che non richiede OAuth (per questo va bene con gli
Sprites, dove Google OAuth non è un connettore e un access token scade
dopo ~1h). L'URL è un segreto: sta solo in config/alba.toml, MAI nel repo.

Parser ICS fatto a mano in stdlib (niente dipendenze): serve solo
VEVENT/DTSTART/DTEND/SUMMARY per il giorno corrente. Le righe piegate
(continuazione con spazio iniziale, RFC 5545) vengono ricomposte.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


class CalendarError(RuntimeError):
    """Il calendario non è disponibile o l'ICS non è valido."""


@dataclass
class Event:
    start: datetime  # consapevole del fuso (o mezzanotte locale se all-day)
    end: datetime
    summary: str
    all_day: bool = False

    def format(self) -> str:
        if self.all_day:
            return f"Tutto il giorno: {self.summary}"
        if self.start.date() == self.end.date():
            return f"{self.start:%H:%M}–{self.end:%H:%M} {self.summary}"
        return f"{self.start:%d/%m %H:%M}–{self.end:%d/%m %H:%M} {self.summary}"


def _default_http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"Accept": "text/calendar"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise CalendarError(f"ICS: HTTP {exc.code} (link scaduto o revocato?)") from exc
    except urllib.error.URLError as exc:
        raise CalendarError(f"ICS non raggiungibile: {exc.reason}") from exc


def fetch_ics(url: str, http_get=None) -> str:
    http_get = http_get or _default_http_get
    raw = http_get(url)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _unfold(text: str) -> list[str]:
    """Ricompone le righe piegate (RFC 5545: riga che inizia con spazio)."""
    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw_line[:1] in (" ", "\t") and lines:
            lines[-1] += raw_line[1:]
        else:
            lines.append(raw_line)
    return lines


def _parse_dt(value: str, params: str, default_tz: ZoneInfo) -> tuple[datetime, bool]:
    """Parsa DTSTART/DTEND. Ritorna (datetime, all_day).

    Forme accettate: 20261125 (data), 20261125T090000Z (UTC),
    20261125T090000 (ora locale), con ;TZID=Europe/Rome.
    """
    value = value.strip()
    if len(value) == 8 and value.isdigit():  # VALUE=DATE
        day = date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
        return datetime.combine(day, time(0, 0), tzinfo=default_tz), True
    if len(value) == 16 and value.endswith("Z"):  # UTC
        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(default_tz), False
    if len(value) == 15:  # ora locale, eventuale TZID
        tz = default_tz
        for part in params.split(";"):
            if part.startswith("TZID="):
                try:
                    tz = ZoneInfo(part[5:])
                except Exception:
                    tz = default_tz
        return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=tz), False
    raise CalendarError(f"formato data/ora ICS non supportato: {value!r}")


def parse_ics(text: str, tz_name: str = "Europe/Rome") -> list[Event]:
    """Parsa un testo ICS e ritorna gli eventi (non filtrati per giorno)."""
    tz = ZoneInfo(tz_name)
    events: list[Event] = []
    current: dict[str, str] | None = None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                events.append(_event_from_props(current, tz))
            current = None
            continue
        if current is None or ":" not in line:
            continue
        name_params, value = line.split(":", 1)
        parts = name_params.split(";")
        current.setdefault(parts[0], value)
        if len(parts) > 1:
            current.setdefault(parts[0] + ";params", ";".join(parts[1:]))
    return events


def _event_from_props(props: dict[str, str], tz: ZoneInfo) -> Event:
    if "DTSTART" not in props:
        raise CalendarError("evento ICS senza DTSTART")
    start, all_day = _parse_dt(props["DTSTART"], props.get("DTSTART;params", ""), tz)
    if "DTEND" in props:
        end, _ = _parse_dt(props["DTEND"], props.get("DTEND;params", ""), tz)
    elif all_day:
        end = start + timedelta(days=1)
    else:
        end = start + timedelta(hours=1)
    return Event(
        start=start,
        end=end,
        summary=props.get("SUMMARY", "(senza titolo)").strip(),
        all_day=all_day,
    )


def events_today(events: list[Event], tz_name: str = "Europe/Rome", today: date | None = None) -> list[Event]:
    """Eventi che toccano la giornata `today` (default: oggi) nel fuso dato."""
    tz = ZoneInfo(tz_name)
    today = today or datetime.now(tz).date()
    day_start = datetime.combine(today, time(0, 0), tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    out = [e for e in events if e.start < day_end and e.end > day_start]
    return sorted(out, key=lambda e: (e.start, e.summary))


def fetch_today_events(ics_url: str, tz_name: str = "Europe/Rome", http_get=None) -> list[Event]:
    """Scarica l'ICS e ritorna gli eventi di oggi, ordinati per orario."""
    return events_today(parse_ics(fetch_ics(ics_url, http_get), tz_name), tz_name)
