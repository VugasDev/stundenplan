import datetime
from cryptography.fernet import Fernet
from app.extensions import db
from app.crypto import CredentialCipher
from app.models import User, WebUntisAccount, Lesson
from app.lessons import RawLesson
from app import fetch


def _make_account(cipher):
    u = User(email="a@b.de")
    u.set_password("x")
    db.session.add(u)
    db.session.commit()
    acc = WebUntisAccount(
        user_id=u.id, label="BK", color="#fff",
        server_url="s", school="sch", username="u",
        password_encrypted=cipher.encrypt("geheim"),
    )
    db.session.add(acc)
    db.session.commit()
    return acc


def test_fetch_account_replaces_window(app):
    cipher = CredentialCipher(Fernet.generate_key())
    acc = _make_account(cipher)
    today = datetime.date(2026, 9, 10)

    # Alt-Stunde im Fenster, die verschwinden muss
    db.session.add(Lesson(account_id=acc.id, date=today, start_time=datetime.time(7, 0),
                          end_time=datetime.time(7, 45), subject="ALT", room="", teacher="",
                          status="normal"))
    db.session.commit()

    d = datetime.datetime(2026, 9, 11, 8, 0)
    raw = [RawLesson(d, d + datetime.timedelta(minutes=45), "NEU", "C1", "GS", None)]

    fetch.fetch_account(acc, cipher, today=today, fetcher=lambda creds, s, e: raw)

    subjects = {l.subject for l in db.session.query(Lesson).all()}
    assert subjects == {"NEU"}
    assert acc.last_fetch_status == "ok"
    assert acc.last_fetch_at is not None


def test_fetch_account_passes_decrypted_password(app):
    cipher = CredentialCipher(Fernet.generate_key())
    acc = _make_account(cipher)
    captured = {}

    def fake_fetch(creds, start, end):
        captured.update(creds)
        return []

    fetch.fetch_account(acc, cipher, today=datetime.date(2026, 9, 10), fetcher=fake_fetch)
    assert captured["password"] == "geheim"
    assert captured["username"] == "u"


def test_fetch_account_records_error(app):
    cipher = CredentialCipher(Fernet.generate_key())
    acc = _make_account(cipher)

    def boom(creds, start, end):
        raise RuntimeError("Passwort abgelehnt")

    fetch.fetch_account(acc, cipher, today=datetime.date(2026, 9, 10), fetcher=boom)
    assert "Passwort abgelehnt" in acc.last_fetch_status


def test_fetch_account_isolates_decrypt_error(app):
    cipher = CredentialCipher(Fernet.generate_key())
    acc = _make_account(cipher)
    acc.password_encrypted = "nicht-entschluesselbar"
    db.session.commit()

    calls = []

    def must_not_be_called(creds, start, end):
        calls.append(creds)
        return []

    fetch.fetch_account(acc, cipher, today=datetime.date(2026, 9, 10), fetcher=must_not_be_called)

    assert calls == []
    assert acc.last_fetch_status is not None
    assert acc.last_fetch_status != "ok"


def test_fetch_account_keeps_lessons_outside_window(app):
    cipher = CredentialCipher(Fernet.generate_key())
    acc = _make_account(cipher)
    today = datetime.date(2026, 9, 10)
    window_days = 21

    before = Lesson(account_id=acc.id, date=today - datetime.timedelta(days=1),
                    start_time=datetime.time(7, 0), end_time=datetime.time(7, 45),
                    subject="VORHER", room="", teacher="", status="normal")
    after = Lesson(account_id=acc.id, date=today + datetime.timedelta(days=window_days + 1),
                   start_time=datetime.time(7, 0), end_time=datetime.time(7, 45),
                   subject="NACHHER", room="", teacher="", status="normal")
    db.session.add_all([before, after])
    db.session.commit()

    d = datetime.datetime(2026, 9, 11, 8, 0)
    raw = [RawLesson(d, d + datetime.timedelta(minutes=45), "IM-FENSTER", "C1", "GS", None)]

    fetch.fetch_account(acc, cipher, today=today, window_days=window_days, fetcher=lambda creds, s, e: raw)

    subjects = {l.subject for l in db.session.query(Lesson).all()}
    assert subjects == {"VORHER", "NACHHER", "IM-FENSTER"}
    assert acc.last_fetch_status == "ok"


def test_run_all_isolates_failures(app):
    cipher = CredentialCipher(Fernet.generate_key())
    acc1 = _make_account(cipher)
    u2 = User(email="c@d.de"); u2.set_password("x"); db.session.add(u2); db.session.commit()
    acc2 = WebUntisAccount(user_id=u2.id, label="X", color="#fff", server_url="s",
                           school="sch", username="u2", password_encrypted=cipher.encrypt("p"))
    db.session.add(acc2); db.session.commit()

    d = datetime.datetime(2026, 9, 11, 8, 0)

    def selective(creds, start, end):
        if creds["username"] == "u2":
            raise RuntimeError("kaputt")
        return [RawLesson(d, d + datetime.timedelta(minutes=45), "OK", "", "", None)]

    fetch.run_all(cipher, today=datetime.date(2026, 9, 10), fetcher=selective)

    assert acc1.last_fetch_status == "ok"
    assert "kaputt" in acc2.last_fetch_status
