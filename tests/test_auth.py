from app.extensions import db
from app.models import User
from app import mailer


def test_register_creates_unconfirmed_user_and_sends_mail(app, client):
    from app.extensions import mail
    with mail.record_messages() as outbox:
        resp = client.post("/register", data={"email": "a@b.de", "password": "geheim123",
                                               "invite_code": ""}, follow_redirects=True)
    assert resp.status_code == 200
    user = db.session.query(User).filter_by(email="a@b.de").one()
    assert user.confirmed is False
    assert len(outbox) == 1


def test_login_blocked_until_confirmed(app, client):
    u = User(email="a@b.de"); u.set_password("geheim123"); db.session.add(u); db.session.commit()
    resp = client.post("/login", data={"email": "a@b.de", "password": "geheim123"},
                       follow_redirects=True)
    # Unbestätigt: bleibt auf der Login-Seite mit Hinweis (kein erfolgreicher Login)
    assert resp.status_code == 200
    assert "bestätige".encode("utf-8") in resp.data
    # (Dass eine geschützte Seite Unangemeldete umleitet, prüft Task 9.)


def test_confirm_then_login_succeeds(app, client):
    u = User(email="a@b.de"); u.set_password("geheim123"); db.session.add(u); db.session.commit()
    with app.app_context():
        token = mailer.generate_confirm_token("a@b.de")
    client.get(f"/confirm/{token}", follow_redirects=True)
    assert db.session.query(User).filter_by(email="a@b.de").one().confirmed is True
    resp = client.post("/login", data={"email": "a@b.de", "password": "geheim123"},
                       follow_redirects=False)
    assert resp.status_code == 302  # Redirect nach erfolgreichem Login


def test_register_invite_mode_requires_code(app, client):
    app.config["REGISTRATION_MODE"] = "invite"
    app.config["INVITE_CODE"] = "SESAM"
    bad = client.post("/register", data={"email": "x@y.de", "password": "geheim123",
                                         "invite_code": "falsch"}, follow_redirects=True)
    assert db.session.query(User).filter_by(email="x@y.de").first() is None
    client.post("/register", data={"email": "x@y.de", "password": "geheim123",
                                   "invite_code": "SESAM"}, follow_redirects=True)
    assert db.session.query(User).filter_by(email="x@y.de").first() is not None


def test_register_survives_unreachable_smtp(app, client, monkeypatch):
    """Ein toter Mailserver darf keinen 500er ausloesen — sonst bleibt der
    frisch angelegte Account unbestaetigt und unerreichbar."""
    def boom(*args, **kwargs):
        raise ConnectionRefusedError(111, "Connection refused")
    monkeypatch.setattr("app.extensions.mail.send", boom)
    resp = client.post("/register", data={"email": "a@b.de", "password": "geheim123",
                                          "invite_code": ""}, follow_redirects=True)
    assert resp.status_code == 200
    assert "konnte nicht versendet".encode("utf-8") in resp.data
    assert db.session.query(User).filter_by(email="a@b.de").one().confirmed is False


def test_resend_confirmation_sends_again(app, client):
    from app.extensions import mail
    u = User(email="a@b.de"); u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    with mail.record_messages() as outbox:
        resp = client.post("/resend-confirmation", data={"email": "a@b.de"},
                           follow_redirects=True)
    assert resp.status_code == 200
    assert len(outbox) == 1


def test_resend_confirmation_does_not_leak_unknown_addresses(app, client):
    from app.extensions import mail
    with mail.record_messages() as outbox:
        resp = client.post("/resend-confirmation", data={"email": "niemand@b.de"},
                           follow_redirects=True)
    assert resp.status_code == 200
    assert len(outbox) == 0


def test_logout_requires_post(app, client):
    u = User(email="a@b.de", confirmed=True); u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    client.post("/login", data={"email": "a@b.de", "password": "geheim123"})
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 302
