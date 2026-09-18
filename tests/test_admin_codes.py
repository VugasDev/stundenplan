"""Einladungscodes: erstellen, einsehen, einlösen."""
import datetime

from app.extensions import db
from app.models import User, InviteCode


def _admin(client):
    u = User(email="chef@b.de", confirmed=True, is_admin=True)
    u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    client.post("/login", data={"email": "chef@b.de", "password": "geheim123"})
    return u


def _code(**kw):
    vorgabe = dict(code="SESAM", note="Testklasse", max_uses=None, expires_at=None)
    vorgabe.update(kw)
    c = InviteCode(**vorgabe)
    db.session.add(c); db.session.commit()
    return c


# --- Gueltigkeit --------------------------------------------------------------

def test_frischer_code_ist_gueltig(app):
    assert _code().is_valid(datetime.date(2026, 9, 18)) is True


def test_code_ohne_limit_bleibt_beliebig_oft_gueltig(app):
    c = _code(uses=999)
    assert c.is_valid(datetime.date(2026, 9, 18)) is True


def test_erschoepfter_code_ist_ungueltig(app):
    c = _code(max_uses=3, uses=3)
    assert c.is_valid(datetime.date(2026, 9, 18)) is False


def test_abgelaufener_code_ist_ungueltig(app):
    c = _code(expires_at=datetime.date(2026, 9, 17))
    assert c.is_valid(datetime.date(2026, 9, 18)) is False
    # Am Ablauftag selbst gilt er noch.
    assert c.is_valid(datetime.date(2026, 9, 17)) is True


def test_zurueckgezogener_code_ist_ungueltig(app):
    c = _code(revoked=True)
    assert c.is_valid(datetime.date(2026, 9, 18)) is False


# --- Oberflaeche --------------------------------------------------------------

def test_uebersicht_zeigt_code_und_nutzung(app, client):
    _admin(client)
    _code(code="KLASSE42", note="FI-Klasse", max_uses=10, uses=3)
    html = client.get("/admin/codes").data.decode()
    assert "KLASSE42" in html and "FI-Klasse" in html
    assert "3" in html and "10" in html


def test_erstellen_legt_einen_code_an(app, client):
    _admin(client)
    client.post("/admin/codes", data={"note": "Neue Klasse", "max_uses": "5"},
                follow_redirects=True)
    c = db.session.query(InviteCode).one()
    assert c.note == "Neue Klasse" and c.max_uses == 5
    assert len(c.code) >= 8          # nicht zu erraten
    assert c.uses == 0


def test_erstellter_code_ist_zufaellig(app, client):
    _admin(client)
    for _ in range(2):
        client.post("/admin/codes", data={"note": "x", "max_uses": ""},
                    follow_redirects=True)
    codes = [c.code for c in db.session.query(InviteCode).all()]
    assert len(set(codes)) == 2


def test_zuruecknehmen_macht_den_code_unbrauchbar(app, client):
    _admin(client)
    c = _code()
    client.post(f"/admin/codes/{c.id}/revoke", follow_redirects=True)
    assert db.session.get(InviteCode, c.id).revoked is True


# --- Einloesen bei der Registrierung -----------------------------------------

def test_registrierung_akzeptiert_einen_code_aus_der_datenbank(app, client):
    app.config["REGISTRATION_MODE"] = "invite"
    app.config["INVITE_CODE"] = ""
    _code(code="SESAM")
    client.post("/register", data={"email": "neu@b.de", "password": "geheim123",
                                   "invite_code": "SESAM"}, follow_redirects=True)
    assert db.session.query(User).filter_by(email="neu@b.de").first() is not None
    assert db.session.query(InviteCode).one().uses == 1


def test_registrierung_weist_einen_erschoepften_code_ab(app, client):
    app.config["REGISTRATION_MODE"] = "invite"
    app.config["INVITE_CODE"] = ""
    _code(code="SESAM", max_uses=1, uses=1)
    client.post("/register", data={"email": "neu@b.de", "password": "geheim123",
                                   "invite_code": "SESAM"}, follow_redirects=True)
    assert db.session.query(User).filter_by(email="neu@b.de").first() is None


def test_der_code_aus_der_konfiguration_gilt_weiterhin(app, client):
    """Sonst sperrt der Umstieg alle aus, die den alten Code haben."""
    app.config["REGISTRATION_MODE"] = "invite"
    app.config["INVITE_CODE"] = "ALTERCODE"
    client.post("/register", data={"email": "neu@b.de", "password": "geheim123",
                                   "invite_code": "ALTERCODE"}, follow_redirects=True)
    assert db.session.query(User).filter_by(email="neu@b.de").first() is not None
