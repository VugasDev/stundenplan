"""Wer den Verwaltungsbereich betreten darf — und wer ihn nicht einmal sieht."""
import pytest

from app.extensions import db
from app.models import User

SEITEN = ["/admin", "/admin/codes", "/admin/klassen", "/admin/konten"]


def _user(email="a@b.de", admin=False):
    u = User(email=email, confirmed=True, is_admin=admin)
    u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    return u


def _anmelden(client, email="a@b.de"):
    client.post("/login", data={"email": email, "password": "geheim123"})


def test_neue_konten_sind_keine_administratoren(app):
    assert _user().is_admin is False


@pytest.mark.parametrize("seite", SEITEN)
def test_ohne_anmeldung_fuehrt_der_bereich_zur_anmeldung(client, seite):
    resp = client.get(seite)
    assert resp.status_code in (301, 302)
    assert "/login" in resp.headers["Location"]


@pytest.mark.parametrize("seite", SEITEN)
def test_normale_konten_sehen_den_bereich_nicht(app, client, seite):
    """404 statt 403: Wer nicht hineindarf, soll nicht einmal erfahren,
    dass es den Bereich gibt."""
    _user(); _anmelden(client)
    assert client.get(seite).status_code == 404


@pytest.mark.parametrize("seite", SEITEN)
def test_administratoren_kommen_hinein(app, client, seite):
    _user(email="chef@b.de", admin=True); _anmelden(client, "chef@b.de")
    assert client.get(seite).status_code == 200


def test_die_navigation_verraet_den_bereich_nur_administratoren(app, client):
    _user(); _anmelden(client)
    assert b"/admin" not in client.get("/login").data
    client.post("/logout")
    _user(email="chef@b.de", admin=True); _anmelden(client, "chef@b.de")
    assert b"/admin" in client.get("/").data
