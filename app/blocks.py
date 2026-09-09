"""Aufbereitung der Unterrichtseinheiten fuer die Anzeige.

Die Funktionen hier arbeiten auf allem, was die Attribute einer `Lesson` traegt,
und kennen weder Flask noch die Datenbank.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass
class Block:
    """Eine zusammenhaengende Unterrichtseinheit, ggf. aus mehreren Stunden."""
    account_id: int
    date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    subject: str
    room: str
    teacher: str
    status: str
    units: int


def _identity(lesson):
    """Alles, was gleich sein muss, damit zwei Stunden ein Block werden."""
    return (lesson.account_id, lesson.date, lesson.subject, lesson.room,
            lesson.teacher, lesson.status)


def merge_lessons(lessons) -> list[Block]:
    """Fasst unmittelbar aneinander grenzende Stunden zu Bloecken zusammen.

    Zusammengefasst wird nur, was lueckenlos anschliesst — eine Pause von auch
    nur fuenf Minuten trennt zwei Bloecke.
    """
    ordered = sorted(lessons, key=lambda l: (l.date, l.start_time, l.account_id))
    blocks: list[Block] = []
    for lesson in ordered:
        last = blocks[-1] if blocks else None
        if (last is not None
                and _identity(lesson) == (last.account_id, last.date, last.subject,
                                          last.room, last.teacher, last.status)
                and last.end_time == lesson.start_time):
            last.end_time = lesson.end_time
            last.units += 1
            continue
        blocks.append(Block(
            account_id=lesson.account_id, date=lesson.date,
            start_time=lesson.start_time, end_time=lesson.end_time,
            subject=lesson.subject, room=lesson.room, teacher=lesson.teacher,
            status=lesson.status, units=1,
        ))
    return blocks


# --- Zeitachse ---------------------------------------------------------------

PX_PER_MIN = 1.1          # Hoehe einer Unterrichtsminute
GAP_HEIGHT = 56.0         # feste Hoehe einer gestauchten Luecke
GAP_MIN_MINUTES = 45      # ab dieser Laenge wird eine Luecke gestaucht


def _minutes(t: datetime.time) -> int:
    return t.hour * 60 + t.minute


def _as_time(minutes: int) -> datetime.time:
    return datetime.time(minutes // 60, minutes % 60)


def _format_gap(minutes: int) -> str:
    stunden, rest = divmod(minutes, 60)
    if stunden and rest:
        return f"{stunden} Std {rest} min frei"
    if stunden:
        return f"{stunden} Std frei"
    return f"{rest} min frei"


@dataclass
class Segment:
    """Ein Abschnitt der Achse — entweder massstabsgetreu oder gestaucht."""
    start: datetime.time
    end: datetime.time
    kind: str          # "scaled" oder "gap"
    top: float
    height: float

    @property
    def minutes(self) -> int:
        return _minutes(self.end) - _minutes(self.start)

    @property
    def label(self) -> str:
        return _format_gap(self.minutes) if self.kind == "gap" else ""


@dataclass
class Axis:
    """Bildet Uhrzeiten auf Pixel ab; lange Freizeiten sind gestaucht."""
    segments: list[Segment]
    height: float
    ticks: list[tuple[datetime.time, float]]

    def y(self, t: datetime.time) -> float:
        minute = _minutes(t)
        for seg in self.segments:
            start, end = _minutes(seg.start), _minutes(seg.end)
            if start <= minute <= end:
                if seg.kind == "gap":
                    # Innerhalb einer gestauchten Luecke anteilig, damit ein
                    # Zeitpunkt darin nie hinter dem Segment landet.
                    anteil = (minute - start) / (end - start) if end > start else 0
                    return seg.top + anteil * seg.height
                return seg.top + (minute - start) * PX_PER_MIN
        return self.height if self.segments else 0.0

    def span(self, start: datetime.time, end: datetime.time) -> float:
        return self.y(end) - self.y(start)


def _busy_intervals(blocks) -> list[tuple[int, int]]:
    """Belegte Zeitfenster ueber alle Tage hinweg, zusammengefasst."""
    spans = sorted((_minutes(b.start_time), _minutes(b.end_time)) for b in blocks)
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


def build_axis(blocks) -> Axis:
    """Baut die gemeinsame Achse fuer alle uebergebenen Bloecke.

    Zeitraeume, in denen an *keinem* Tag Unterricht liegt und die laenger als
    `GAP_MIN_MINUTES` sind, werden auf eine feste Hoehe gestaucht. Alles andere
    bleibt massstabsgetreu, damit Bloecke ihre Dauer zeigen.
    """
    if not blocks:
        return Axis(segments=[], height=0.0, ticks=[])

    busy = _busy_intervals(blocks)
    segments: list[Segment] = []
    top = 0.0
    for index, (start, end) in enumerate(busy):
        if index > 0:
            luecke_start, luecke_ende = busy[index - 1][1], start
            dauer = luecke_ende - luecke_start
            gestaucht = dauer >= GAP_MIN_MINUTES
            hoehe = GAP_HEIGHT if gestaucht else dauer * PX_PER_MIN
            segments.append(Segment(_as_time(luecke_start), _as_time(luecke_ende),
                                    "gap" if gestaucht else "scaled", top, hoehe))
            top += hoehe
        hoehe = (end - start) * PX_PER_MIN
        segments.append(Segment(_as_time(start), _as_time(end), "scaled", top, hoehe))
        top += hoehe

    axis = Axis(segments=segments, height=top, ticks=[])
    for seg in segments:
        if seg.kind == "gap":
            continue  # in gestauchten Luecken steht die Dauer, keine Uhrzeit
        erste_stunde = (_minutes(seg.start) + 59) // 60 * 60
        for minute in range(erste_stunde, _minutes(seg.end) + 1, 60):
            zeit = _as_time(minute)
            axis.ticks.append((zeit, axis.y(zeit)))
    return axis


# --- Agenda ------------------------------------------------------------------

@dataclass
class AgendaView:
    """Was jetzt gerade laeuft und was heute noch kommt.

    Bewusst auf den laufenden Tag begrenzt — was uebermorgen ansteht, gehoert in
    die Wochenansicht. Vom naechsten Unterrichtstag steht nur der erste Block
    als Ausblick darin.
    """
    current: Block | None
    upcoming: list[Block]
    next_day: Block | None
    feierabend: bool = False


def agenda_view(blocks, now: datetime.datetime) -> AgendaView:
    heute, uhrzeit = now.date(), now.time()

    current = None
    upcoming = []
    for block in sorted((b for b in blocks if b.date == heute),
                        key=lambda b: b.start_time):
        if block.start_time <= uhrzeit < block.end_time:
            current = block
        elif block.start_time > uhrzeit:
            upcoming.append(block)

    next_day = None
    if current is None and not upcoming:
        spaeter = sorted((b for b in blocks if b.date > heute),
                         key=lambda b: (b.date, b.start_time))
        next_day = spaeter[0] if spaeter else None

    return AgendaView(current=current, upcoming=upcoming, next_day=next_day,
                      feierabend=bool(current) and not upcoming)


# --- Deutsche Datumsangaben --------------------------------------------------
# Bewusst ohne locale.setlocale: das wirkt prozessweit und haengt davon ab, ob
# die Locale im Container ueberhaupt erzeugt wurde.

WOCHENTAGE_KURZ = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
WOCHENTAGE_LANG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
                   "Samstag", "Sonntag"]


def wochentag_kurz(d: datetime.date) -> str:
    return WOCHENTAGE_KURZ[d.weekday()]


def wochentag_lang(d: datetime.date) -> str:
    return WOCHENTAGE_LANG[d.weekday()]
