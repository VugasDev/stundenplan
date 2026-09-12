"""Wann darf abgerufen werden?

Der Sinn dieser Regeln ist Ruecksicht auf den WebUntis-Server der Schule: ein
Abruf je Klasse statt einer je Person, und auch der nur so oft wie noetig.
"""
from __future__ import annotations

import datetime

AUTO_INTERVAL_MINUTES = 90      # automatischer Abruf
MANUAL_COOLDOWN_MINUTES = 15    # Sperrfrist fuer "Jetzt aktualisieren"
ACTIVE_FROM = datetime.time(6, 0)
ACTIVE_UNTIL = datetime.time(22, 0)


def _minutes_since(last_fetch_at, now) -> float | None:
    if last_fetch_at is None:
        return None
    minutes = (now - last_fetch_at).total_seconds() / 60
    # Zeitumstellung oder Systemzeitsprung koennen den letzten Abruf in die Zukunft
    # verschieben. Wir klemmen negative Werte auf 0, um sichere Sperrfristen zu
    # gewaehrleisten und negative Alter auszuschliessen.
    return max(0, minutes)


def may_fetch_automatically(last_fetch_at, now: datetime.datetime) -> bool:
    """Nur tagsueber und nur, wenn das Intervall abgelaufen ist."""
    if not (ACTIVE_FROM <= now.time() < ACTIVE_UNTIL):
        return False
    vergangen = _minutes_since(last_fetch_at, now)
    return vergangen is None or vergangen >= AUTO_INTERVAL_MINUTES


def may_fetch_manually(last_fetch_at, now: datetime.datetime) -> bool:
    """Auf Knopfdruck — unabhaengig von der Uhrzeit, aber mit Sperrfrist."""
    vergangen = _minutes_since(last_fetch_at, now)
    return vergangen is None or vergangen >= MANUAL_COOLDOWN_MINUTES


def cooldown_remaining(last_fetch_at, now: datetime.datetime) -> int:
    """Volle Minuten bis zum naechsten erlaubten manuellen Abruf."""
    vergangen = _minutes_since(last_fetch_at, now)
    if vergangen is None:
        return 0
    rest = MANUAL_COOLDOWN_MINUTES - vergangen
    return max(0, int(rest))


def age_in_minutes(last_fetch_at, now: datetime.datetime) -> int | None:
    """Wie alt ist der zwischengespeicherte Stand?"""
    vergangen = _minutes_since(last_fetch_at, now)
    return None if vergangen is None else int(vergangen)
