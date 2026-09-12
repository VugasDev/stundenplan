from __future__ import annotations

import datetime

from app.extensions import db
from app.models import SchoolClass, Lesson
from app.lessons import normalize
from app.webuntis_client import fetch_class_lessons
from app.schedule import may_fetch_automatically
from app.zeit import local_today, local_now, STANDARD_ZONE


def purge_outside_window(school_class, today: datetime.date, window_days: int) -> int:
    """Loescht Stunden ausserhalb des Abruffensters.

    Es gibt bewusst kein Archiv: gespeichert ist nur, was noch bevorsteht.
    """
    ende = today + datetime.timedelta(days=window_days)
    return (db.session.query(Lesson)
            .filter(Lesson.class_id == school_class.id,
                    db.or_(Lesson.date < today, Lesson.date > ende))
            .delete(synchronize_session=False))


def fetch_class(school_class, cipher, today=None, window_days=21,
                fetcher=fetch_class_lessons, zone=STANDARD_ZONE) -> bool:
    """Holt den Plan einer Klasse. Rueckgabe: ob abgerufen wurde."""
    if not school_class.has_source:
        return False

    today = today or local_today(zone)
    end = today + datetime.timedelta(days=window_days)

    # Ausserhalb des Fensters wird bei jedem Abruf geloescht — unabhaengig
    # davon, ob der Login gleich danach gelingt. Eigener Commit, damit ein
    # Fehlschlag weiter unten diese Loeschung nicht per Rollback rueckgaengig
    # macht (Spec: "bei jedem Abruf", nicht nur bei erfolgreichem).
    purge_outside_window(school_class, today, window_days)
    db.session.commit()

    try:
        credentials = {
            "server_url": school_class.server_url,
            "school": school_class.school,
            "username": school_class.username,
            "password": cipher.decrypt(school_class.password_encrypted),
        }
        raw = fetcher(credentials, school_class.untis_class_id, today, end)
        normalized = normalize(raw)

        (db.session.query(Lesson)
         .filter(Lesson.class_id == school_class.id,
                 Lesson.date >= today, Lesson.date <= end)
         .delete(synchronize_session=False))
        for n in normalized:
            db.session.add(Lesson(
                class_id=school_class.id, date=n.date,
                start_time=n.start_time, end_time=n.end_time,
                subject=n.subject, room=n.room, teacher=n.teacher,
                status=n.status, note=n.note,
            ))
        school_class.last_fetch_status = "ok"
    except Exception as exc:  # Fehler je Klasse isolieren
        db.session.rollback()
        msg = str(exc).strip()
        school_class.last_fetch_status = (
            f"{type(exc).__name__}: {msg}" if msg else type(exc).__name__)[:255]
    finally:
        # Im finally, damit auch ein Fehlschlag den Zeitstempel setzt — sonst
        # wuerde eine dauerhaft fehlschlagende Klasse bei jedem Automatiklauf
        # erneut versucht. Ortszeit, nicht UTC: may_fetch_automatically vergleicht
        # gegen local_now() und braucht dieselbe Skala, sonst waere der Vergleich
        # um die Zeitzonenverschiebung falsch. Konfigurierte Zone durchreichen,
        # sonst wuerde hier immer Europe/Berlin verwendet.
        school_class.last_fetch_at = local_now(zone)
        db.session.commit()
    return True


def run_all(cipher, now=None, today=None, window_days=21,
            fetcher=fetch_class_lessons, zone=STANDARD_ZONE) -> int:
    """Automatiklauf: holt nur faellige Klassen und nur tagsueber."""
    now = now or local_now(zone)
    geholt = 0
    for school_class in db.session.query(SchoolClass).all():
        if not school_class.has_source:
            continue
        if not may_fetch_automatically(school_class.last_fetch_at, now):
            continue
        if fetch_class(school_class, cipher, today=today,
                       window_days=window_days, fetcher=fetcher, zone=zone):
            geholt += 1
    return geholt


def main() -> None:
    from app import create_app
    app = create_app()
    with app.app_context():
        zone = app.config["TIMEZONE"]
        run_all(app.extensions["cipher"],
                now=local_now(zone), today=local_today(zone),
                window_days=app.config["FETCH_WINDOW_DAYS"], zone=zone)


if __name__ == "__main__":
    main()
