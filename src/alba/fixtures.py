# SPDX-License-Identifier: GPL-3.0-or-later
"""Dati fittizi per `alba briefing --dry-run` e per i test.

Niente rete, niente credenziali: il dry-run stampa un briefing italiano
leggibile usando solo questi dati.
"""

from __future__ import annotations

SAMPLE_WEATHER_JSON = {
    "daily": {
        "time": ["2026-11-25"],
        "temperature_2m_max": [19.0],
        "temperature_2m_min": [15.0],
        "precipitation_probability_max": [10],
        "weathercode": [2],
        "wind_gusts_10m_max": [43.0],
    }
}

SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Alba fixture//EN
BEGIN:VEVENT
UID:lezione-1@alba
DTSTART;TZID=Europe/Rome:20261125T080000
DTEND;TZID=Europe/Rome:20261125T090000
SUMMARY:Lezione di matematica
END:VEVENT
BEGIN:VEVENT
UID:palestra-1@alba
DTSTART;TZID=Europe/Rome:20261125T170000
DTEND;TZID=Europe/Rome:20261125T183000
SUMMARY:Palestra — gambe
END:VEVENT
BEGIN:VEVENT
UID:vecchio-1@alba
DTSTART;TZID=Europe/Rome:20261124T100000
DTEND;TZID=Europe/Rome:20261124T110000
SUMMARY:Evento di ieri (non deve comparire)
END:VEVENT
END:VCALENDAR
"""

SAMPLE_COMMITS = [
    {
        "sha": "abc1234def5678",
        "commit": {
            "message": "feat(pkg): package manager v1\n\nCorpo del commit",
            "author": {"name": "Giuliano", "date": "2026-11-24T19:30:00Z"},
        },
    },
    {
        "sha": "def5678abc1234",
        "commit": {
            "message": "docs: README aggiornato",
            "author": {"name": "Giuliano", "date": "2026-11-24T18:00:00Z"},
        },
    },
]

SAMPLE_LLM_REPLY = {
    "choices": [
        {"message": {"content": "Agrigento: parzialmente nuvoloso, min 15° / max 19°.\n08:00–09:00 Lezione di matematica\n17:00–18:30 Palestra — gambe\nGG: 2 commit — Giuliano: feat(pkg): package manager v1"}}
    ]
}
