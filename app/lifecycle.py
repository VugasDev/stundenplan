"""Wann ist eine Klasse zu Ende?

Zwei unabhaengige Wege, eine Klasse stillzulegen — stillgelegt heisst: sie wird
nicht mehr abgerufen. Die Loeschfristen raeumen ihren Plan danach von selbst ab,
weil nichts mehr nachkommt.

1. Niemand liest sie mehr. Ist die letzte Mitgliedschaft eine Woche fort, endet
   der Abruf. Das ist der Hauptweg: Wenn ein Bildungsgang endet, treten die
   Leute aus oder hoeren auf, die App zu nutzen.
2. Der Bildungsgang ist abgelaufen, laesst sich am Klassennamen ablesen und die
   Laufzeit des Kuerzels ist bekannt. Das faengt nur den Fall, dass jemand
   Mitglied bleibt, obwohl seine Klasse Geschichte ist.

Der zweite Weg ist absichtlich zurueckhaltend. Eine Messung der echten
Klassenlisten (2026-09-12) zeigte: Von 167 Klassen der einen Schule folgen 28
dem Namensschema nicht, und die Buchstabenzahl des Kuerzels sagt nichts ueber
die Laufzeit — die andere Schule fuehrt sogar einbuchstabige Kuerzel. Geraten
wird deshalb nicht: Was sich nicht sicher lesen laesst oder dessen Laufzeit
nicht hinterlegt ist, laeuft weiter.
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass

# Kuerzel, Ziffer des Einschulungsjahres, Parallelklasse — z.B. FI42, FIT61, B62.
_NAME = re.compile(r"^([A-Za-z]{1,4})(\d)(\d+)$")

# Die Jahresziffer ist nur eine Stelle und damit mehrdeutig. Aufgeloest wird sie
# in diesem Fenster um das laufende Schuljahr; darin gibt es je Ziffer genau ein
# Jahr. Neun Jahre zurueck deckt auch die laengsten Bildungsgaenge ab.
JAHRE_ZURUECK = 9
JAHRE_VORAUS = 1

# Ab welchem Monat ein neues Schuljahr zaehlt.
SCHULJAHR_BEGINNT = 8


@dataclass(frozen=True)
class ClassName:
    kuerzel: str
    jahresziffer: int
    parallel: str


def parse_class_name(name: str) -> ClassName | None:
    """Zerlegt einen Klassennamen — oder gibt None, wenn er dem Schema nicht folgt."""
    treffer = _NAME.match((name or "").strip())
    if treffer is None:
        return None
    kuerzel, ziffer, parallel = treffer.groups()
    return ClassName(kuerzel=kuerzel.upper(), jahresziffer=int(ziffer), parallel=parallel)


def school_year(today: datetime.date) -> int:
    """Das Jahr, in dem das laufende Schuljahr begonnen hat."""
    return today.year if today.month >= SCHULJAHR_BEGINNT else today.year - 1


def resolve_intake_year(jahresziffer: int, today: datetime.date) -> int:
    """Loest die einstellige Jahresangabe zu einem vollen Jahr auf.

    Bei Mehrdeutigkeit wird bewusst das **spaetere** Jahr gewaehlt, denn die
    beiden Fehlerarten sind nicht gleich schwer: Eine laufende Klasse zu frueh
    stillzulegen nimmt ihren Mitgliedern mitten im Schuljahr den Plan weg; eine
    langst beendete weiter abzurufen kostet nur einen unnoetigen Abruf.
    """
    obergrenze = school_year(today) + JAHRE_VORAUS
    # Das groesste Jahr bis zur Obergrenze, das auf diese Ziffer endet.
    jahr = obergrenze - ((obergrenze - jahresziffer) % 10)
    return jahr
