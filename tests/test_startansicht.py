"""Welche Ansicht beim Öffnen erscheint — feste Wahl oder die letzte."""
from app.extensions import db
from app.models import User, SchoolClass, Membership


def _angemeldet(client, **einstellung):
    u = User(email="a@b.de", confirmed=True)
    u.set_password("geheim123")
    for feld, wert in einstellung.items():
        setattr(u, feld, wert)
    db.session.add(u); db.session.commit()
    k = SchoolClass(server_url="s", school="sch", untis_class_id=7, name="FI42",
                    username="u", password_encrypted="enc")
    db.session.add(k); db.session.commit()
    db.session.add(Membership(user_id=u.id, class_id=k.id))
    db.session.commit()
    client.post("/login", data={"email": "a@b.de", "password": "geheim123"})
    return u


def _ansicht(client, pfad="/"):
    html = client.get(pfad).data.decode()
    for name in ("agenda", "day", "week"):
        if f'data-view="{name}"' in html:
            return name
    return None


# --- Feste Startansicht -------------------------------------------------------

def test_ohne_einstellung_bleibt_die_agenda_die_startansicht(app, client):
    _angemeldet(client)
    assert _ansicht(client) == "agenda"


def test_eingestellte_startansicht_wird_beim_oeffnen_gezeigt(app, client):
    _angemeldet(client, start_view="week")
    assert _ansicht(client) == "week"


def test_eine_ansicht_in_der_adresse_hat_vorrang_vor_der_einstellung(app, client):
    _angemeldet(client, start_view="week")
    assert _ansicht(client, "/?view=day") == "day"


# --- Zuletzt genutzte Ansicht -------------------------------------------------

def test_der_ansichtswechsel_wird_gemerkt(app, client):
    nutzer = _angemeldet(client)
    client.get("/?view=week")
    db.session.refresh(nutzer)
    assert nutzer.last_view == "week"


def test_mit_zuletzt_genutzt_oeffnet_die_letzte_ansicht(app, client):
    _angemeldet(client, start_view="last")
    client.get("/?view=week")
    assert _ansicht(client) == "week"


def test_zuletzt_genutzt_ohne_vorgeschichte_zeigt_die_agenda(app, client):
    _angemeldet(client, start_view="last")
    assert _ansicht(client) == "agenda"


def test_ein_unbekannter_wert_in_der_adresse_fuehrt_zur_agenda(app, client):
    """Der Parameter kommt von aussen und darf nichts Unerwartetes anrichten."""
    nutzer = _angemeldet(client)
    assert _ansicht(client, "/?view=../../etc/passwd") == "agenda"
    db.session.refresh(nutzer)
    assert nutzer.last_view in (None, "", "agenda")


# --- Einstellungsseite --------------------------------------------------------

def test_einstellungsseite_zeigt_die_aktuelle_wahl(app, client):
    _angemeldet(client, start_view="day")
    html = client.get("/einstellungen").data.decode()
    assert "Startansicht" in html
    assert 'value="day"' in html and "checked" in html


def test_einstellung_wird_gespeichert(app, client):
    nutzer = _angemeldet(client)
    client.post("/einstellungen", data={"start_view": "week"},
                follow_redirects=True)
    db.session.refresh(nutzer)
    assert nutzer.start_view == "week"


def test_ein_unerlaubter_wert_wird_nicht_uebernommen(app, client):
    nutzer = _angemeldet(client, start_view="agenda")
    client.post("/einstellungen", data={"start_view": "gibtsnicht"},
                follow_redirects=True)
    db.session.refresh(nutzer)
    assert nutzer.start_view == "agenda"


def test_einstellungen_erfordern_eine_anmeldung(app, client):
    assert client.get("/einstellungen", follow_redirects=False).status_code in (301, 302)
    assert client.post("/einstellungen", data={"start_view": "week"},
                       follow_redirects=False).status_code in (301, 302)


def test_die_einstellungen_sind_verlinkt(app, client):
    _angemeldet(client)
    assert "/einstellungen" in client.get("/").data.decode()
