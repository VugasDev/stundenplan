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


# --- Laufzeiten der Bildungsgaenge -------------------------------------------
# Bewusst eine gepflegte Liste und keine Regel: Gemessen am 2026-09-12 sagt die
# Buchstabenzahl des Kuerzels nichts ueber die Laufzeit. Die eine Schule fuehrt
# zwei- und dreibuchstabige Kuerzel, die andere zusaetzlich einbuchstabige, und
# in derselben Dreibuchstaben-Gruppe stehen Fachschulklassen (FIT, FET, FMT,
# vier Jahre) neben Kuerzeln wie BFA/BFB und AVV/AVT, die deutlich kuerzer
# laufen. Ein Kuerzel, das hier fehlt, wird nie stillgelegt.
STANDARD_LAUFZEITEN = {
    "FI": 3,    # Fachinformatiker, Berufsschule
    "FIT": 4,   # Fachschule Informationstechnik
    "FET": 4,   # Fachschule Elektrotechnik
    "FMT": 4,   # Fachschule Maschinenbautechnik
}


def course_ended(name: str, today: datetime.date,
                 laufzeiten: dict[str, int] | None = None) -> bool | None:
    """Ist der Bildungsgang dieser Klasse abgelaufen?

    True oder False, wenn sich das aus dem Namen und einer hinterlegten Laufzeit
    ergibt — sonst None. None heisst: keine Aussage, die Klasse laeuft weiter.
    """
    laufzeiten = laufzeiten if laufzeiten is not None else STANDARD_LAUFZEITEN
    teile = parse_class_name(name)
    if teile is None:
        return None
    jahre = laufzeiten.get(teile.kuerzel)
    if jahre is None:
        return None
    letztes_schuljahr = resolve_intake_year(teile.jahresziffer, today) + jahre - 1
    # Das Schuljahr laeuft bis zum Beginn des naechsten.
    return school_year(today) > letztes_schuljahr


# --- Niemand liest die Klasse mehr -------------------------------------------

SCHONFRIST_TAGE = 7


def abandoned(school_class, today: datetime.date) -> bool:
    """Ist die letzte Mitgliedschaft lange genug fort?

    Der Zeitstempel wird gesetzt, wenn die letzte Mitgliedschaft endet, und beim
    naechsten Beitritt wieder geleert — ein Wiedereintritt hebt die Frist damit auf.
    """
    weg_seit = getattr(school_class, "members_left_at", None)
    if weg_seit is None:
        return False
    if isinstance(weg_seit, datetime.datetime):
        weg_seit = weg_seit.date()
    return (today - weg_seit).days >= SCHONFRIST_TAGE


def dormant_reason(school_class, today: datetime.date,
                   laufzeiten: dict[str, int] | None = None) -> str | None:
    """Warum diese Klasse nicht mehr abgerufen wird — oder None, wenn sie laeuft.

    Die beiden Gruende sind unabhaengig voneinander; "verlassen" wiegt schwerer,
    weil er ohne jede Namensdeutung auskommt.
    """
    if abandoned(school_class, today):
        return "verlassen"
    if course_ended(school_class.name, today, laufzeiten) is True:
        return "beendet"
    return None
