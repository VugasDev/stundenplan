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


def _join_names(elements) -> str:
    return ", ".join(e.name for e in elements) if elements else ""


def fetch_raw_lessons(credentials: dict, start: datetime.date, end: datetime.date,
                      session_factory=default_session) -> list[RawLesson]:
    session = session_factory(credentials)
    session.login()
    try:
        periods = session.my_timetable(start=start, end=end)
        return [
            RawLesson(
                start=p.start,
                end=p.end,
                subject=_join_names(p.subjects),
                room=_join_names(p.rooms),
                teacher=_join_names(p.teachers),
                code=p.code,
            )
            for p in periods
        ]
    finally:
        session.logout()


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
                subject=_join_names(p.subjects),
                room=_join_names(p.rooms),
                teacher=_join_names(p.teachers),
                code=p.code,
            )
            for p in periods
        ]
    finally:
        session.logout()
