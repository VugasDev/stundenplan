from __future__ import annotations

import datetime

import webuntis

from app.lessons import RawLesson


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
