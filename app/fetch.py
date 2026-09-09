from __future__ import annotations

import datetime

from app.extensions import db
from app.models import WebUntisAccount, Lesson, utcnow
from app.lessons import normalize
from app.zeit import local_today
from app.webuntis_client import fetch_raw_lessons


def fetch_account(account, cipher, today=None, window_days=21, fetcher=fetch_raw_lessons) -> None:
    today = today or local_today()
    end = today + datetime.timedelta(days=window_days)
    try:
        credentials = {
            "server_url": account.server_url,
            "school": account.school,
            "username": account.username,
            "password": cipher.decrypt(account.password_encrypted),
        }
        raw = fetcher(credentials, today, end)
        normalized = normalize(raw)

        (db.session.query(Lesson)
         .filter(Lesson.account_id == account.id,
                 Lesson.date >= today, Lesson.date <= end)
         .delete(synchronize_session=False))
        for n in normalized:
            db.session.add(Lesson(
                account_id=account.id, date=n.date,
                start_time=n.start_time, end_time=n.end_time,
                subject=n.subject, room=n.room, teacher=n.teacher,
                status=n.status, note=n.note,
            ))
        account.last_fetch_status = "ok"
    except Exception as exc:  # Fehler pro Account isolieren, Status festhalten
        db.session.rollback()
        msg = str(exc).strip()
        account.last_fetch_status = (f"{type(exc).__name__}: {msg}" if msg else type(exc).__name__)[:255]
    finally:
        account.last_fetch_at = utcnow()
        db.session.commit()


def run_all(cipher, today=None, window_days=21, fetcher=fetch_raw_lessons) -> None:
    for account in db.session.query(WebUntisAccount).all():
        fetch_account(account, cipher, today=today, window_days=window_days, fetcher=fetcher)


def main() -> None:
    from app import create_app
    app = create_app()
    with app.app_context():
        run_all(app.extensions["cipher"],
                today=local_today(app.config["TIMEZONE"]),
                window_days=app.config["FETCH_WINDOW_DAYS"])


if __name__ == "__main__":
    main()
