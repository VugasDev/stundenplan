import re
import datetime
import pytest

from app.extensions import db
from app.models import User, SchoolClass, Membership, Lesson
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


def _join_und_token(client, server_url="s.webuntis.com", school="s",
                    username="schueler", password="geheim"):
    """Durchläuft /classes/join wie ein echter Nutzer und liefert das darin
    ausgestellte Token für die anschliessende /classes/choose-Anfrage."""
    resp = client.post("/classes/join", data={
        "server_url": server_url, "school": school,
        "username": username, "password": password}, follow_redirects=True)
    match = re.search(rb'name="token" value="([^"]+)"', resp.data)
    assert match is not None, "Token nicht im choose.html gefunden"
    return match.group(1).decode()


def test_join_ist_ratenbegrenzt():
    """Regression fuer W3: jeder POST auf /classes/join loeste einen echten
    Login gegen die Schule aus — unbegrenzt, also zum Durchprobieren von
    Passwoertern nutzbar. Eigene App-Instanz mit eingeschaltetem Rate-Limit,
    damit die uebrigen Tests (TestConfig hat RATELIMIT_ENABLED=False) davon
    unberuehrt bleiben."""
    from app import create_app
    from app.config import TestConfig
    from app.extensions import db as _db

    class RatenbegrenzteTestConfig(TestConfig):
        RATELIMIT_ENABLED = True

    app = create_app(RatenbegrenzteTestConfig)
    with app.app_context():
        _db.create_all()
        u = User(email="a@b.de", confirmed=True); u.set_password("geheim123")
        _db.session.add(u); _db.session.commit()
        client = app.test_client()
        client.post("/login", data={"email": "a@b.de", "password": "geheim123"})
        _patch_verify(monkeypatch=pytest.MonkeyPatch(), ok=False)

        antworten = [client.post("/classes/join", data={
            "server_url": "s.webuntis.com", "school": "s",
            "username": "schueler", "password": "falsch"}) for _ in range(11)]
        _db.session.remove()
        _db.drop_all()
    assert antworten[-1].status_code == 429
    assert all(a.status_code != 429 for a in antworten[:10])


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
    token = _join_und_token(client)
    client.post("/classes/choose", data={
        "token": token, "password": "geheim", "untis_class_id": "7",
        "name": "FI42", "spenden": ""}, follow_redirects=True)
    k = db.session.query(SchoolClass).one()
    assert k.password_encrypted is None
    assert k.has_source is False
    assert db.session.query(Membership).count() == 1


def test_spende_speichert_die_zugangsdaten_verschluesselt(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    token = _join_und_token(client)
    client.post("/classes/choose", data={
        "token": token, "password": "geheim", "untis_class_id": "7",
        "name": "FI42", "spenden": "ja"}, follow_redirects=True)
    k = db.session.query(SchoolClass).one()
    assert k.has_source is True
    assert k.password_encrypted != "geheim"       # verschluesselt, nicht im Klartext
    assert app.extensions["cipher"].decrypt(k.password_encrypted) == "geheim"
    assert k.donor_user_id == user.id


def test_spende_mit_fehlschlagender_erneuter_pruefung_hinterlegt_keine_quelle(
        app, client, user, monkeypatch):
    """Regression fuer W2: choose() nahm das Passwort ungeprueft aus dem
    Formular. Wer sich einmal gueltig anmeldet, koennte damit fuer jede
    Klasse der Schule ein falsches Passwort als Spende eintragen. Direkt vor
    dem Speichern wird jetzt erneut verifiziert; schlaegt das fehl, wird
    nicht gespendet, die Klasse bleibt fuer einen echten Spender offen."""
    _patch_verify(monkeypatch)  # /classes/join: Erst-Login gelingt
    token = _join_und_token(client)
    _patch_verify(monkeypatch, ok=False)  # erneute Pruefung vor dem Speichern schlaegt fehl
    client.post("/classes/choose", data={
        "token": token, "password": "geheim", "untis_class_id": "7",
        "name": "FI42", "spenden": "ja"}, follow_redirects=True)
    k = db.session.query(SchoolClass).one()
    assert k.has_source is False
    assert k.password_encrypted is None
    assert k.donor_user_id is None
    # Die Mitgliedschaft entsteht trotzdem.
    assert db.session.query(Membership).count() == 1


def test_zweiter_beitritt_nutzt_die_vorhandene_quelle(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    token = _join_und_token(client, username="erster", password="geheim")
    client.post("/classes/choose", data={
        "token": token, "password": "geheim", "untis_class_id": "7",
        "name": "FI42", "spenden": "ja"}, follow_redirects=True)
    zweiter = User(email="c@d.de", confirmed=True); zweiter.set_password("geheim123")
    db.session.add(zweiter); db.session.commit()
    client.post("/logout")
    client.post("/login", data={"email": "c@d.de", "password": "geheim123"})
    token2 = _join_und_token(client, username="zweiter", password="anderes")
    client.post("/classes/choose", data={
        "token": token2, "password": "anderes", "untis_class_id": "7",
        "name": "FI42", "spenden": ""}, follow_redirects=True)
    assert db.session.query(SchoolClass).count() == 1      # keine zweite Quelle
    assert db.session.query(Membership).count() == 2
    k = db.session.query(SchoolClass).one()
    assert k.username == "erster"                          # Spende bleibt beim Ersten


def test_widerruf_loescht_die_zugangsdaten(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    token = _join_und_token(client)
    client.post("/classes/choose", data={
        "token": token, "password": "geheim", "untis_class_id": "7",
        "name": "FI42", "spenden": "ja"}, follow_redirects=True)
    k = db.session.query(SchoolClass).one()
    client.post(f"/classes/{k.id}/revoke", follow_redirects=True)
    k = db.session.get(SchoolClass, k.id)
    assert k.password_encrypted is None
    assert k.username is None
    assert k.donor_user_id is None


def test_widerruf_loescht_auch_die_stunden_und_den_abrufstatus(app, client, user, monkeypatch):
    """Regression fuer K3: ohne Quelle findet nie wieder ein Abruf statt —
    ohne Loeschung blieben die Stunden der Klasse unbegrenzt fuer alle
    Mitglieder sichtbar (Verstoss gegen 'Löschfristen' und 'Keine Historie')."""
    _patch_verify(monkeypatch)
    token = _join_und_token(client)
    client.post("/classes/choose", data={
        "token": token, "password": "geheim", "untis_class_id": "7",
        "name": "FI42", "spenden": "ja"}, follow_redirects=True)
    k = db.session.query(SchoolClass).one()
    k.last_fetch_status = "ok"
    k.last_fetch_at = datetime.datetime(2026, 9, 16, 10, 0)
    db.session.add(Lesson(class_id=k.id, date=datetime.date(2026, 9, 16),
                          start_time=datetime.time(8, 0), end_time=datetime.time(8, 45),
                          subject="WB", room="C005", teacher="GS", status="normal"))
    db.session.commit()

    client.post(f"/classes/{k.id}/revoke", follow_redirects=True)

    assert db.session.query(Lesson).filter_by(class_id=k.id).count() == 0
    k = db.session.get(SchoolClass, k.id)
    assert k.last_fetch_status is None
    assert k.last_fetch_at is None


def test_nur_der_spender_darf_widerrufen(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    token = _join_und_token(client)
    client.post("/classes/choose", data={
        "token": token, "password": "geheim", "untis_class_id": "7",
        "name": "FI42", "spenden": "ja"}, follow_redirects=True)
    k = db.session.query(SchoolClass).one()
    fremder = User(email="x@y.de", confirmed=True); fremder.set_password("geheim123")
    db.session.add(fremder); db.session.commit()
    client.post("/logout")
    client.post("/login", data={"email": "x@y.de", "password": "geheim123"})
    resp = client.post(f"/classes/{k.id}/revoke")
    assert resp.status_code == 404
    assert db.session.get(SchoolClass, k.id).password_encrypted is not None


def test_choose_ohne_gueltiges_token_legt_nichts_an(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    client.post("/classes/choose", data={
        "server_url": "erfunden.webuntis.com", "school": "erfunden",
        "username": "boese", "password": "boese",
        "untis_class_id": "1", "name": "ERFUNDEN",
        "spenden": "ja"}, follow_redirects=True)
    assert db.session.query(SchoolClass).count() == 0
    assert db.session.query(Membership).count() == 0


def test_token_einer_schule_erlaubt_keinen_beitritt_bei_anderer_schule(
        app, client, user, monkeypatch):
    # Klasse mit derselben untis_class_id existiert bereits unter Schule B —
    # ein für Schule A ausgestelltes Token darf trotzdem nicht auf sie zugreifen,
    # weil choose() Server/Schule ausschliesslich dem Token entnimmt, nie dem
    # Formular.
    bestehende = SchoolClass(server_url="b.webuntis.com", school="schule-b",
                             untis_class_id=7, name="FI42-B",
                             username="fremdspender",
                             password_encrypted="verschluesselt-fremd")
    db.session.add(bestehende); db.session.commit()

    _patch_verify(monkeypatch)
    token = _join_und_token(client, server_url="a.webuntis.com", school="schule-a")
    client.post("/classes/choose", data={
        "token": token, "password": "geheim", "untis_class_id": "7",
        "name": "FI42", "spenden": "ja"}, follow_redirects=True)

    # Es muss eine zweite, eigene Klasse für Schule A entstanden sein — die
    # Spende der Schule B darf weder gelesen noch überschrieben worden sein.
    assert db.session.query(SchoolClass).count() == 2
    klasse_a = (db.session.query(SchoolClass)
                .filter_by(server_url="a.webuntis.com", school="schule-a").one())
    assert klasse_a.username == "schueler"
    klasse_b = db.session.get(SchoolClass, bestehende.id)
    assert klasse_b.username == "fremdspender"


def test_manipulierter_name_im_formular_wird_ignoriert(app, client, user, monkeypatch):
    """Regression fuer W4: der Anzeigename kam bisher ungeprueft aus dem
    Formular — wer eine Klasse zuerst anlegt, konnte den fuer alle
    sichtbaren Namen frei bestimmen. Gespeichert wird jetzt der Name aus der
    verifizierten Klassenliste im Token."""
    _patch_verify(monkeypatch, klassen=(UntisClass(7, "FI42"),))
    token = _join_und_token(client)
    client.post("/classes/choose", data={
        "token": token, "password": "geheim", "untis_class_id": "7",
        "name": "GEFAELSCHT", "spenden": ""}, follow_redirects=True)
    k = db.session.query(SchoolClass).one()
    assert k.name == "FI42"


def test_nicht_verifizierte_klassen_id_wird_abgewiesen(app, client, user, monkeypatch):
    _patch_verify(monkeypatch, klassen=(UntisClass(7, "FI42"),))
    token = _join_und_token(client)
    client.post("/classes/choose", data={
        "token": token, "password": "geheim", "untis_class_id": "42",
        "name": "FREMD", "spenden": "ja"}, follow_redirects=True)
    assert db.session.query(SchoolClass).count() == 0
    assert db.session.query(Membership).count() == 0


def test_fehlende_formularfelder_fuehren_zu_verstaendlicher_meldung(app, client, user, monkeypatch):
    """Regression fuer G3: fehlende Formularfelder (z.B. Passwort) durften
    nicht in einer technischen 500er-Seite enden, sondern sollen mit einer
    verstaendlichen deutschen Meldung zurueck zum Beitrittsformular fuehren."""
    _patch_verify(monkeypatch)
    token = _join_und_token(client)
    resp = client.post("/classes/choose", data={
        "token": token, "untis_class_id": "7"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Bitte alle Felder ausfüllen".encode("utf-8") in resp.data
    assert db.session.query(SchoolClass).count() == 0


def test_abgelaufenes_token_wird_abgewiesen(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    import app.classes.routes as routes
    token = _join_und_token(client)
    monkeypatch.setattr(routes, "_JOIN_MAX_AGE_SECONDS", -1)
    resp = client.post("/classes/choose", data={
        "token": token, "password": "geheim", "untis_class_id": "7",
        "name": "FI42", "spenden": "ja"}, follow_redirects=True)
    assert db.session.query(SchoolClass).count() == 0
    assert resp.status_code == 200


def _beitritt(client, spenden=""):
    """Vollstaendiger Beitritt zu FI42 ueber den regulaeren Weg."""
    token = _join_und_token(client)
    return client.post("/classes/choose", data={
        "token": token, "password": "geheim", "untis_class_id": "7",
        "name": "FI42", "spenden": spenden}, follow_redirects=True)


# --- Zeitstempel fuer verlassene Klassen -------------------------------------

def test_austritt_der_letzten_person_vermerkt_den_zeitpunkt(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    _beitritt(client, spenden="ja")
    k = db.session.query(SchoolClass).one()
    assert k.members_left_at is None
    client.post(f"/classes/{k.id}/leave", follow_redirects=True)
    k = db.session.get(SchoolClass, k.id)
    assert k.members_left_at is not None


def test_austritt_bei_verbleibenden_mitgliedern_vermerkt_nichts(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    _beitritt(client, spenden="ja")
    k = db.session.query(SchoolClass).one()
    zweiter = User(email="zweit@b.de", confirmed=True); zweiter.set_password("geheim123")
    db.session.add(zweiter); db.session.commit()
    db.session.add(Membership(user_id=zweiter.id, class_id=k.id)); db.session.commit()
    client.post(f"/classes/{k.id}/leave", follow_redirects=True)
    k = db.session.get(SchoolClass, k.id)
    assert k.members_left_at is None      # es liest ja noch jemand mit


def test_wiedereintritt_loescht_den_zeitpunkt(app, client, user, monkeypatch):
    _patch_verify(monkeypatch)
    _beitritt(client, spenden="ja")
    k = db.session.query(SchoolClass).one()
    client.post(f"/classes/{k.id}/leave", follow_redirects=True)
    assert db.session.get(SchoolClass, k.id).members_left_at is not None
    _beitritt(client, spenden="")
    assert db.session.get(SchoolClass, k.id).members_left_at is None
