"""Angemeldet bleiben — auf dem eigenen Telefon will niemand taeglich tippen."""
from app.extensions import db
from app.models import User


def _nutzer():
    u = User(email="a@b.de", confirmed=True)
    u.set_password("geheim123")
    db.session.add(u)
    db.session.commit()
    return u


def _cookies(resp):
    return [h for k, h in resp.headers.items() if k.lower() == "set-cookie"]


def test_anmeldeformular_bietet_angemeldet_bleiben(app, client):
    html = client.get("/login").data.decode()
    assert 'name="remember"' in html
    assert "ngemeldet bleiben" in html


def test_mit_haekchen_wird_die_anmeldung_behalten(app, client):
    _nutzer()
    resp = client.post("/login", data={"email": "a@b.de", "password": "geheim123",
                                       "remember": "y"})
    assert resp.status_code == 302
    assert any("remember_token" in c for c in _cookies(resp)), _cookies(resp)


def test_ohne_haekchen_endet_die_anmeldung_mit_dem_browser(app, client):
    _nutzer()
    resp = client.post("/login", data={"email": "a@b.de", "password": "geheim123"})
    assert resp.status_code == 302
    assert not any("remember_token" in c for c in _cookies(resp))


def test_das_dauerhafte_cookie_ist_fuer_skripte_unlesbar(app, client):
    """Wer es auslesen koennte, waere dauerhaft angemeldet — nicht nur bis
    zum Schliessen des Browsers."""
    _nutzer()
    resp = client.post("/login", data={"email": "a@b.de", "password": "geheim123",
                                       "remember": "y"})
    keks = next(c for c in _cookies(resp) if "remember_token" in c)
    assert "HttpOnly" in keks
    assert "SameSite=Lax" in keks


def test_abmelden_entfernt_das_dauerhafte_cookie(app, client):
    """Auf einem geteilten Geraet darf die Anmeldung nicht zurueckbleiben."""
    _nutzer()
    client.post("/login", data={"email": "a@b.de", "password": "geheim123",
                                "remember": "y"})
    resp = client.post("/logout")
    keks = next((c for c in _cookies(resp) if "remember_token" in c), "")
    assert keks, _cookies(resp)
    assert "Expires=Thu, 01 Jan 1970" in keks or "Max-Age=0" in keks
