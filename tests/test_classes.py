import datetime
import pytest

from app.extensions import db
from app.models import User, SchoolClass, Membership
from app.webuntis_client import UntisClass


@pytest.fixture
def user(app, client):
    u = User(email="a@b.de", confirmed=True); u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    client.post("/login", data={"email": "a@b.de", "password": "geheim123"})
    return u


def _patch_verify(monkeypatch, klassen=(UntisClass(7, "FI42"),), ok=True):
    import app.classes.routes as routes
    monkeypatch.setattr(routes, "verify_and_list_classes",
                        lambda *a, **kw: (ok, list(klassen), "" if ok else "Fehler"))


def test_beitritt_zeigt_die_klassen_zur_auswahl(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    resp = client.post("/classes/join", data={
        "server_url": "s.webuntis.com", "school": "s",
        "username": "schueler", "password": "geheim"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"FI42" in resp.data


def test_falsche_zugangsdaten_legen_nichts_an(app, client, user, monkeypatch):
    _patch_verify(monkeypatch, ok=False)
    client.post("/classes/join", data={
        "server_url": "s.webuntis.com", "school": "s",
        "username": "schueler", "password": "falsch"}, follow_redirects=True)
    assert db.session.query(SchoolClass).count() == 0
    assert db.session.query(Membership).count() == 0


def test_beitritt_ohne_spende_speichert_kein_passwort(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    client.post("/classes/choose", data={
        "server_url": "s.webuntis.com", "school": "s", "username": "schueler",
        "password": "geheim", "untis_class_id": "7", "name": "FI42",
        "spenden": ""}, follow_redirects=True)
    k = db.session.query(SchoolClass).one()
    assert k.password_encrypted is None
    assert k.has_source is False
    assert db.session.query(Membership).count() == 1


def test_spende_speichert_die_zugangsdaten_verschluesselt(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    client.post("/classes/choose", data={
        "server_url": "s.webuntis.com", "school": "s", "username": "schueler",
        "password": "geheim", "untis_class_id": "7", "name": "FI42",
        "spenden": "ja"}, follow_redirects=True)
    k = db.session.query(SchoolClass).one()
    assert k.has_source is True
    assert k.password_encrypted != "geheim"       # verschluesselt, nicht im Klartext
    assert app.extensions["cipher"].decrypt(k.password_encrypted) == "geheim"
    assert k.donor_user_id == user.id


def test_zweiter_beitritt_nutzt_die_vorhandene_quelle(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    client.post("/classes/choose", data={
        "server_url": "s.webuntis.com", "school": "s", "username": "erster",
        "password": "geheim", "untis_class_id": "7", "name": "FI42",
        "spenden": "ja"}, follow_redirects=True)
    zweiter = User(email="c@d.de", confirmed=True); zweiter.set_password("geheim123")
    db.session.add(zweiter); db.session.commit()
    client.post("/logout")
    client.post("/login", data={"email": "c@d.de", "password": "geheim123"})
    client.post("/classes/choose", data={
        "server_url": "s.webuntis.com", "school": "s", "username": "zweiter",
        "password": "anderes", "untis_class_id": "7", "name": "FI42",
        "spenden": ""}, follow_redirects=True)
    assert db.session.query(SchoolClass).count() == 1      # keine zweite Quelle
    assert db.session.query(Membership).count() == 2
    k = db.session.query(SchoolClass).one()
    assert k.username == "erster"                          # Spende bleibt beim Ersten


def test_widerruf_loescht_die_zugangsdaten(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    client.post("/classes/choose", data={
        "server_url": "s.webuntis.com", "school": "s", "username": "schueler",
        "password": "geheim", "untis_class_id": "7", "name": "FI42",
        "spenden": "ja"}, follow_redirects=True)
    k = db.session.query(SchoolClass).one()
    client.post(f"/classes/{k.id}/revoke", follow_redirects=True)
    k = db.session.get(SchoolClass, k.id)
    assert k.password_encrypted is None
    assert k.username is None
    assert k.donor_user_id is None


def test_nur_der_spender_darf_widerrufen(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    client.post("/classes/choose", data={
        "server_url": "s.webuntis.com", "school": "s", "username": "schueler",
        "password": "geheim", "untis_class_id": "7", "name": "FI42",
        "spenden": "ja"}, follow_redirects=True)
    k = db.session.query(SchoolClass).one()
    fremder = User(email="x@y.de", confirmed=True); fremder.set_password("geheim123")
    db.session.add(fremder); db.session.commit()
    client.post("/logout")
    client.post("/login", data={"email": "x@y.de", "password": "geheim123"})
    resp = client.post(f"/classes/{k.id}/revoke")
    assert resp.status_code == 404
    assert db.session.get(SchoolClass, k.id).password_encrypted is not None
