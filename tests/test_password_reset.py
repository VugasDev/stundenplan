import pytest

from app.extensions import db, mail
from app.models import User
from app import mailer


@pytest.fixture
def user(app):
    u = User(email="schueler@schule.de", confirmed=True)
    u.set_password("altespasswort")
    db.session.add(u)
    db.session.commit()
    return u


def _request_reset(client, email="schueler@schule.de"):
    with mail.record_messages() as outbox:
        resp = client.post("/forgot-password", data={"email": email},
                           follow_redirects=True)
    return resp, outbox


def test_forgot_password_sends_mail_with_reset_link(app, client, user):
    resp, outbox = _request_reset(client)
    assert resp.status_code == 200
    assert len(outbox) == 1
    assert f"/reset-password/{user.id}/" in outbox[0].body


def test_forgot_password_unknown_address_is_indistinguishable(app, client, user):
    known, known_box = _request_reset(client)
    unknown, unknown_box = _request_reset(client, "niemand@schule.de")
    # Gleiche Antwort — sonst verraet das Formular, welche Adressen registriert sind.
    assert known.data == unknown.data
    assert len(unknown_box) == 0


def test_reset_sets_new_password(app, client, user):
    token = mailer.generate_reset_token(user)
    resp = client.post(f"/reset-password/{user.id}/{token}",
                       data={"password": "neuespasswort", "password_repeat": "neuespasswort"},
                       follow_redirects=True)
    assert resp.status_code == 200
    reloaded = db.session.get(User, user.id)
    assert reloaded.check_password("neuespasswort")
    assert not reloaded.check_password("altespasswort")
    login = client.post("/login", data={"email": user.email, "password": "neuespasswort"})
    assert login.status_code == 302


def test_reset_token_is_single_use(app, client, user):
    token = mailer.generate_reset_token(user)
    client.post(f"/reset-password/{user.id}/{token}",
                data={"password": "neuespasswort", "password_repeat": "neuespasswort"},
                follow_redirects=True)
    # Nach der Aenderung haengt der Token an einem Hash, den es nicht mehr gibt.
    zweiter = client.get(f"/reset-password/{user.id}/{token}", follow_redirects=False)
    assert zweiter.status_code == 302
    assert "/forgot-password" in zweiter.headers["Location"]


def test_reset_token_of_one_user_does_not_work_for_another(app, client, user):
    other = User(email="fremd@schule.de", confirmed=True)
    other.set_password("fremdespasswort")
    db.session.add(other)
    db.session.commit()
    token = mailer.generate_reset_token(user)
    resp = client.get(f"/reset-password/{other.id}/{token}", follow_redirects=False)
    assert resp.status_code == 302
    assert "/forgot-password" in resp.headers["Location"]


def test_expired_token_is_rejected(app, client, user):
    token = mailer.generate_reset_token(user)
    assert mailer.verify_reset_token(user, token, max_age_seconds=-1) is False


def test_reset_confirms_a_pending_registration(app, client):
    u = User(email="neu@schule.de", confirmed=False)
    u.set_password("altespasswort")
    db.session.add(u)
    db.session.commit()
    token = mailer.generate_reset_token(u)
    client.post(f"/reset-password/{u.id}/{token}",
                data={"password": "neuespasswort", "password_repeat": "neuespasswort"},
                follow_redirects=True)
    assert db.session.get(User, u.id).confirmed is True


def test_mismatched_repeat_does_not_change_password(app, client, user):
    token = mailer.generate_reset_token(user)
    client.post(f"/reset-password/{user.id}/{token}",
                data={"password": "neuespasswort", "password_repeat": "vertippt"},
                follow_redirects=True)
    assert db.session.get(User, user.id).check_password("altespasswort")
