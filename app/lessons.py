from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass
class RawLesson:
    start: datetime.datetime
    end: datetime.datetime
    subject: str
    room: str
    teacher: str
    code: str | None = None


@dataclass
class NormalizedLesson:
    date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    subject: str
    room: str
    teacher: str
    status: str
    note: str = ""


_STATUS_MAP = {None: "normal", "": "normal", "cancelled": "cancelled", "irregular": "substitution"}
_SUFFIX_CHARS = "#="


def map_status(code: str | None) -> str:
    return _STATUS_MAP.get(code, "normal")


def clean_subject(name: str) -> str:
    return name.rstrip(_SUFFIX_CHARS)


def normalize(raw: list[RawLesson]) -> list[NormalizedLesson]:
    # Schlüssel = identische Stunde bis auf den Lehrer (Team-Teaching zusammenfassen)
    groups: dict[tuple, dict] = {}
    for r in raw:
        subject = clean_subject(r.subject)
        key = (r.start, r.end, subject, r.room, map_status(r.code))
        bucket = groups.setdefault(key, {"teachers": set()})
        if r.teacher:
            bucket["teachers"].add(r.teacher)

    result: list[NormalizedLesson] = []
    for (start, end, subject, room, status) in groups:
        teachers = ", ".join(sorted(groups[(start, end, subject, room, status)]["teachers"]))
        result.append(NormalizedLesson(
            date=start.date(),
            start_time=start.time(),
            end_time=end.time(),
            subject=subject,
            room=room,
            teacher=teachers,
            status=status,
        ))
    result.sort(key=lambda l: (l.date, l.start_time))
    return result
