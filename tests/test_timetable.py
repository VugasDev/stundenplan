import datetime
from app.extensions import db
from app.models import User, WebUntisAccount, Lesson


def _login_user_with_lessons(app, client):
    u = User(email="a@b.de"); u.set_password("geheim123"); u.confirmed = True
    db.session.add(u); db.session.commit()
    acc = WebUntisAccount(user_id=u.id, label="BK", color="#ff0000", server_url="s",
                          school="sch", username="u", password_encrypted="enc")
    db.session.add(acc); db.session.commit()
    db.session.add(Lesson(account_id=acc.id, date=datetime.date(2026, 9, 10),
                          start_time=datetime.time(8, 0), end_time=datetime.time(8, 45),
                          subject="WB", room="C005", teacher="GS", status="normal"))
    db.session.commit()
    client.post("/login", data={"email": "a@b.de", "password": "geheim123"})
    return u, acc


def test_index_requires_login(client):
    assert client.get("/", follow_redirects=False).status_code in (301, 302)


def test_index_shows_lessons_for_week(app, client):
    _login_user_with_lessons(app, client)
    resp = client.get("/?view=week&week=2026-09-07")  # Woche enthält den 10.09.
    assert resp.status_code == 200
    assert b"WB" in resp.data
    assert b"C005" in resp.data


def test_agenda_view_renders(app, client):
    _login_user_with_lessons(app, client)
    resp = client.get("/?view=agenda&week=2026-09-07")
    assert resp.status_code == 200
    assert b"WB" in resp.data


def test_user_cannot_see_other_users_lessons(app, client):
    _login_user_with_lessons(app, client)
    other = User(email="x@y.de"); other.set_password("x"); other.confirmed = True
    db.session.add(other); db.session.commit()
    oacc = WebUntisAccount(user_id=other.id, label="Geheim", color="#000", server_url="s",
                           school="sch", username="o", password_encrypted="enc")
    db.session.add(oacc); db.session.commit()
    db.session.add(Lesson(account_id=oacc.id, date=datetime.date(2026, 9, 10),
                          start_time=datetime.time(9, 0), end_time=datetime.time(9, 45),
                          subject="FREMD", room="Z9", teacher="XX", status="normal"))
    db.session.commit()
    resp = client.get("/?view=week&week=2026-09-07")
    assert b"FREMD" not in resp.data


def test_refresh_triggers_fetch_for_own_accounts(app, client, monkeypatch):
    u, acc = _login_user_with_lessons(app, client)
    called = []
    import app.timetable.routes as routes
    monkeypatch.setattr(routes, "fetch_account", lambda account, cipher: called.append(account.id))
    resp = client.post("/refresh", follow_redirects=False)
    assert resp.status_code == 302
    assert called == [acc.id]


# --- Ansichten ---------------------------------------------------------------

def _lesson(acc, day, start, end, subject="ITD", room="K204", status="normal"):
    return Lesson(account_id=acc.id, date=datetime.date.fromisoformat(day),
                  start_time=datetime.time.fromisoformat(start),
                  end_time=datetime.time.fromisoformat(end),
                  subject=subject, room=room, teacher="MUE", status=status)


def test_standardansicht_ist_die_agenda(app, client):
    _login_user_with_lessons(app, client)
    resp = client.get("/")
    assert b'data-view="agenda"' in resp.data


def test_doppelstunde_erscheint_als_ein_block(app, client):
    u, acc = _login_user_with_lessons(app, client)
    db.session.add_all([_lesson(acc, "2026-09-16", "07:30", "08:15"),
                        _lesson(acc, "2026-09-16", "08:15", "09:00")])
    db.session.commit()
    resp = client.get("/?view=week&week=2026-09-14")
    # Leerzeichen wichtig: sonst zaehlt 'tt-block-head' mit.
    assert resp.data.count(b'class="tt-block ') == 1
    assert b"07:30" in resp.data and b"09:00" in resp.data


def test_wochenansicht_staucht_die_luecke_zur_abendschule(app, client):
    u, acc = _login_user_with_lessons(app, client)
    db.session.add_all([_lesson(acc, "2026-09-16", "13:00", "14:30", subject="EVP"),
                        _lesson(acc, "2026-09-16", "17:00", "18:30", subject="PK")])
    db.session.commit()
    resp = client.get("/?view=week&week=2026-09-14")
    assert b"tt-gap" in resp.data
    assert "2 Std 30 min frei".encode("utf-8") in resp.data


def test_tagesansicht_zeigt_nur_den_gewaehlten_tag(app, client):
    u, acc = _login_user_with_lessons(app, client)
    db.session.add_all([_lesson(acc, "2026-09-16", "07:30", "09:00", subject="HEUTE"),
                        _lesson(acc, "2026-09-17", "07:30", "09:00", subject="MORGEN")])
    db.session.commit()
    resp = client.get("/?view=day&day=2026-09-16")
    assert resp.status_code == 200
    assert b"HEUTE" in resp.data and b"MORGEN" not in resp.data


def test_entfall_und_vertretung_werden_unterschiedlich_markiert(app, client):
    u, acc = _login_user_with_lessons(app, client)
    db.session.add_all([
        _lesson(acc, "2026-09-16", "07:30", "09:00", subject="AUS", status="cancelled"),
        _lesson(acc, "2026-09-16", "09:25", "10:55", subject="VER", status="substitution"),
    ])
    db.session.commit()
    resp = client.get("/?view=week&week=2026-09-14")
    assert b"tt-cancelled" in resp.data
    assert b"tt-substitution" in resp.data


def test_block_nennt_die_klasse(app, client):
    u, acc = _login_user_with_lessons(app, client)
    resp = client.get("/?view=week&week=2026-09-07")
    assert b"BK" in resp.data  # Label des Zugangs steht im Block


def test_wochentage_stehen_auf_deutsch(app, client):
    u, acc = _login_user_with_lessons(app, client)
    db.session.add(_lesson(acc, "2026-09-16", "07:30", "09:00"))
    db.session.commit()
    resp = client.get("/?view=week&week=2026-09-14")
    assert "Mi".encode("utf-8") in resp.data
    for englisch in (b"Mon", b"Tue", b"Wed", b"Thu", b"Fri"):
        assert englisch not in resp.data


def test_tagesansicht_nennt_den_wochentag_auf_deutsch(app, client):
    u, acc = _login_user_with_lessons(app, client)
    resp = client.get("/?view=day&day=2026-09-16")
    assert "Mittwoch".encode("utf-8") in resp.data
    assert b"Wednesday" not in resp.data
