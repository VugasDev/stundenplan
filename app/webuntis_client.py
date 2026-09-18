from __future__ import annotations

import datetime
from collections import namedtuple

import webuntis

from app.lessons import RawLesson

UntisClass = namedtuple("UntisClass", "id name")


def default_session(credentials: dict):
    return webuntis.Session(
        username=credentials["username"],
        password=credentials["password"],
        server=credentials["server_url"],
        school=credentials["school"],
        useragent="stundenplan-app",
    )


def _namen(periode, attribut: str) -> str:
    """Namen einer Elementliste der Periode — oder leer, wenn sie fehlt.

    Abgesichert wird bewusst schon der *Attributzugriff*, nicht erst das
    Iterieren: `subjects`, `rooms` und `teachers` sind bei webuntis Properties,
    die die hinterlegten IDs nachschlagen. Traegt WebUntis bei einer Vertretung
    mit entferntem Lehrer die ID 0 ein (Rohdaten: 'te': [{'id': 0, 'orgid': …}]),
    findet die Bibliothek dazu keinen Datensatz und wirft beim Lesen des
    Attributs IndexError.

    Ohne diese Absicherung riss eine einzige solche Stunde den gesamten Abruf
    der Klasse mit — und ausgerechnet Vertretungen sind die Stunden, die man
    sehen will. Lieber die einzelne Angabe weglassen als den ganzen Plan.
    """
    try:
        elemente = getattr(periode, attribut)
        return ", ".join(e.name for e in elemente) if elemente else ""
    except Exception:
        return ""


def fetch_classes(credentials: dict, session_factory=default_session) -> list[UntisClass]:
    """Klassen der Schule — nur Namen und IDs, keine Plaene."""
    session = session_factory(credentials)
    session.login()
    try:
        return [UntisClass(id=k.id, name=k.name) for k in session.klassen()]
    finally:
        session.logout()


def fetch_class_lessons(credentials: dict, untis_class_id: int,
                        start: datetime.date, end: datetime.date,
                        session_factory=default_session) -> list[RawLesson]:
    """Stundenplan einer Klasse.

    WebUntis erlaubt das nur fuer die eigene Klasse des Kontos; fuer fremde
    Klassen antwortet der Server mit "no right for timetable".
    """
    session = session_factory(credentials)
    session.login()
    try:
        periods = session.timetable(start=start, end=end, klasse=untis_class_id)
        return [
            RawLesson(
                start=p.start, end=p.end,
                subject=_namen(p, "subjects"),
                room=_namen(p, "rooms"),
                teacher=_namen(p, "teachers"),
                code=p.code,
            )
            for p in periods
        ]
    finally:
        session.logout()
