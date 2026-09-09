"""Ortszeit der Schule — unabhaengig davon, worauf die Serveruhr steht.

Der LXC laeuft auf UTC. Wuerde die App datetime.now() nehmen, laege die
Agenda im Sommer zwei Stunden zurueck und zeigte, was laengst vorbei ist.
"""
from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

STANDARD_ZONE = "Europe/Berlin"


def local_now(zone: str = STANDARD_ZONE) -> datetime.datetime:
    """Aktuelle Ortszeit als naives datetime.

    Naiv, weil die Uhrzeiten in der Datenbank ebenfalls naiv sind und sonst
    nicht vergleichbar waeren.
    """
    return datetime.datetime.now(ZoneInfo(zone)).replace(tzinfo=None)


def local_today(zone: str = STANDARD_ZONE) -> datetime.date:
    return local_now(zone).date()
