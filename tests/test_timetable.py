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
    resp = client.get("/?week=2026-09-07")  # Woche enthält den 10.09.
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
    resp = client.get("/?week=2026-09-07")
    assert b"FREMD" not in resp.data


def test_refresh_triggers_fetch_for_own_accounts(app, client, monkeypatch):
    u, acc = _login_user_with_lessons(app, client)
    called = []
    import app.timetable.routes as routes
    monkeypatch.setattr(routes, "fetch_account", lambda account, cipher: called.append(account.id))
    resp = client.post("/refresh", follow_redirects=False)
    assert resp.status_code == 302
    assert called == [acc.id]
