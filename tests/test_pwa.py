import json

from app.extensions import db
from app.models import User


def _login(client):
    u = User(email="a@b.de", confirmed=True)
    u.set_password("geheim123")
    db.session.add(u)
    db.session.commit()
    client.post("/login", data={"email": "a@b.de", "password": "geheim123"})
    return u


# --- Installierbarkeit --------------------------------------------------------

def test_manifest_wird_ausgeliefert(client):
    resp = client.get("/manifest.webmanifest")
    assert resp.status_code == 200
    assert "manifest" in resp.headers["Content-Type"]


def test_manifest_traegt_was_zum_installieren_noetig_ist(client):
    daten = json.loads(client.get("/manifest.webmanifest").data)
    assert daten["name"] and daten["short_name"]
    assert daten["start_url"] == "/"
    assert daten["display"] == "standalone"      # startet ohne Browserleiste
    assert daten["theme_color"] and daten["background_color"]
    groessen = {i["sizes"] for i in daten["icons"]}
    assert "192x192" in groessen and "512x512" in groessen
    # Fuer Android-Startbildschirme, damit nichts abgeschnitten wird
    assert any("maskable" in i.get("purpose", "") for i in daten["icons"])


def test_alle_im_manifest_genannten_icons_sind_erreichbar(client):
    daten = json.loads(client.get("/manifest.webmanifest").data)
    for icon in daten["icons"]:
        resp = client.get(icon["src"])
        assert resp.status_code == 200, icon["src"]
        assert resp.data[:8] == b"\x89PNG\r\n\x1a\n", f"{icon['src']} ist kein PNG"


def test_seite_verweist_auf_manifest_und_icons(client):
    html = client.get("/login").data.decode()
    assert 'rel="manifest"' in html
    assert 'name="theme-color"' in html
    # iOS nimmt nicht das Manifest, sondern dieses Icon.
    assert 'rel="apple-touch-icon"' in html
    assert 'name="apple-mobile-web-app-capable"' in html


def test_apple_touch_icon_ist_erreichbar_und_ohne_transparenz(client):
    resp = client.get("/static/icons/apple-touch-icon.png")
    assert resp.status_code == 200
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"


# --- Service Worker -----------------------------------------------------------

def test_service_worker_wird_im_wurzelverzeichnis_ausgeliefert(client):
    """Muss unter / liegen, sonst darf er nicht die ganze Seite verwalten."""
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["Content-Type"]


def test_service_worker_wird_registriert(client):
    assert "/sw.js" in client.get("/login").data.decode()


def test_offline_seite_ist_vorhanden(client):
    resp = client.get("/offline")
    assert resp.status_code == 200
    assert "offline".encode("utf-8") in resp.data.lower()


# --- Aufraeumen beim Abmelden -------------------------------------------------

def test_abmelden_weist_den_browser_an_den_speicher_zu_leeren(app, client):
    """Auf einem geteilten Geraet darf nach dem Abmelden kein Plan im
    Browser-Speicher zurueckbleiben."""
    _login(client)
    resp = client.post("/logout")
    assert resp.status_code == 302
    assert resp.headers.get("Clear-Site-Data") == '"cache", "storage"'
