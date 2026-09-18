"""Anklickbare Unterrichtsbloecke mit Zusatzinfos und Konferenzlink.

Wichtigster Fall ist der Fernunterricht der Abendschule: dort haengt am
Termin ein Teams-Link, der sich direkt oeffnen lassen soll.
"""
import datetime

from app.extensions import db
from app.models import User, SchoolClass, Membership, Lesson

TEAMS = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc/0"


def _angemeldet(client, **stunde):
    u = User(email="a@b.de", confirmed=True)
    u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    k = SchoolClass(server_url="s", school="sch", untis_class_id=7, name="FIT61",
                    username="u", password_encrypted="enc")
    db.session.add(k); db.session.commit()
    db.session.add(Membership(user_id=u.id, class_id=k.id))
    vorgabe = dict(class_id=k.id, date=datetime.date(2026, 9, 16),
                   start_time=datetime.time(17, 0), end_time=datetime.time(17, 45),
                   subject="SWE", room="", teacher="VS", status="normal")
    vorgabe.update(stunde)
    db.session.add(Lesson(**vorgabe))
    db.session.commit()
    client.post("/login", data={"email": "a@b.de", "password": "geheim123"})
    return k


def _seiten(client):
    return {"woche": client.get("/?view=week&week=2026-09-16").data.decode(),
            "tag": client.get("/?view=day&day=2026-09-16").data.decode()}


# --- Die Angaben muessen ueberhaupt in der Seite stehen ------------------------

def test_block_traegt_die_anmerkung_der_stunde(app, client):
    _angemeldet(client, note="Bitte Laptop mitbringen")
    for name, html in _seiten(client).items():
        assert "Bitte Laptop mitbringen" in html, name


def test_block_traegt_den_konferenzlink(app, client):
    _angemeldet(client, video_url=TEAMS)
    for name, html in _seiten(client).items():
        assert TEAMS in html, name


def test_stunde_ohne_zusaetze_bringt_keinen_leeren_link(app, client):
    _angemeldet(client)
    assert "teams.microsoft.com" not in _seiten(client)["tag"]


# --- Bedienbarkeit ------------------------------------------------------------

def test_bloecke_sind_anklickbar_und_mit_der_tastatur_erreichbar(app, client):
    """Als Schaltflaeche, nicht als blosses div — sonst kommt man per Tastatur
    und mit Screenreader nicht heran."""
    _angemeldet(client, note="Klausur")
    html = _seiten(client)["tag"]
    assert '<button type="button" class="tt-block' in html


def test_seite_bringt_das_fenster_fuer_die_details_mit(app, client):
    _angemeldet(client, note="Klausur")
    for name, html in _seiten(client).items():
        assert "<dialog" in html, name
        assert "stunden-details.js" in html, name


def test_konferenzlink_oeffnet_in_neuem_tab_und_ohne_rueckkanal(app, client):
    """rel=noopener: die fremde Seite darf nicht auf unser Fenster zugreifen."""
    _angemeldet(client, video_url=TEAMS)
    html = _seiten(client)["tag"]
    assert 'target="_blank"' in html and "noopener" in html


# --- Agenda -------------------------------------------------------------------

def test_agenda_zeigt_den_konferenzlink_der_naechsten_stunde(app, client, monkeypatch):
    """Die Agenda ist die Startseite — von hier tritt man der Konferenz bei.

    Die Uhr wird festgesetzt: die Agenda zeigt nur den laufenden Tag, sonst
    haenge das Ergebnis davon ab, wann der Test zufaellig laeuft.
    """
    from app.timetable import routes
    jetzt = datetime.datetime(2026, 9, 16, 16, 0)
    monkeypatch.setattr(routes, "local_today", lambda *a, **kw: jetzt.date())
    monkeypatch.setattr(routes, "local_now", lambda *a, **kw: jetzt)
    _angemeldet(client, video_url=TEAMS)     # Stunde um 17:00 desselben Tages
    html = client.get("/").data.decode()
    assert "Als Nächstes" in html
    assert TEAMS in html


def test_anmerkung_kann_nicht_aus_dem_attribut_ausbrechen(app, client):
    """Der Text stammt von WebUntis und landet in einem HTML-Attribut.

    Ohne Maskierung koennte ein praeparierter Unterrichtstext eigenes Markup
    in die Seite schreiben.
    """
    _angemeldet(client, note='" onmouseover="alert(1)" x="')
    html = _seiten(client)["tag"]
    assert '" onmouseover="alert(1)" x="' not in html   # unmaskiert = ausgebrochen
    assert "onmouseover" in html                        # der Text steht drin …
    assert "&#34;" in html or "&quot;" in html          # … aber maskiert
