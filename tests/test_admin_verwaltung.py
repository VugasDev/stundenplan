"""Klassen- und Kontenverwaltung im Adminbereich."""
import datetime

from app.extensions import db
from app.models import User, SchoolClass, Membership, Lesson


def _admin(client):
    u = User(email="chef@b.de", confirmed=True, is_admin=True)
    u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    client.post("/login", data={"email": "chef@b.de", "password": "geheim123"})
    return u


_naechste_id = iter(range(1, 1000))


def _klasse(name="AB42", mit_quelle=True):
    # Eigene Untis-ID je Klasse: eine Schule kennt jede Klassen-ID nur einmal.
    k = SchoolClass(server_url="s.webuntis.com", school="s",
                    untis_class_id=next(_naechste_id),
                    name=name,
                    username="u" if mit_quelle else None,
                    password_encrypted="enc" if mit_quelle else None)
    db.session.add(k); db.session.commit()
    return k


def _stunde(k, tag="2026-09-16"):
    return Lesson(class_id=k.id, date=datetime.date.fromisoformat(tag),
                  start_time=datetime.time(8), end_time=datetime.time(9),
                  subject="ITD", room="K204", teacher="MUE", status="normal")


# --- Klassen ------------------------------------------------------------------

def test_uebersicht_zeigt_klasse_mit_zahlen(app, client):
    admin = _admin(client)
    k = _klasse()
    db.session.add_all([Membership(user_id=admin.id, class_id=k.id), _stunde(k)])
    k.last_fetch_status = "ok"
    db.session.commit()
    html = client.get("/admin/klassen").data.decode()
    assert "AB42" in html and "ok" in html


def test_uebersicht_zeigt_auch_klassen_ohne_eigene_mitgliedschaft(app, client):
    """Die Verwaltung sieht alle Klassen — anders als der Stundenplan, der nur
    zeigt, wo man selbst Mitglied ist."""
    _admin(client)
    _klasse(name="FREMD9")
    assert b"FREMD9" in client.get("/admin/klassen").data


def test_loeschen_entfernt_klasse_mitgliedschaften_und_stunden(app, client):
    admin = _admin(client)
    k = _klasse()
    db.session.add_all([Membership(user_id=admin.id, class_id=k.id), _stunde(k)])
    db.session.commit()
    klassen_id = k.id
    client.post(f"/admin/klassen/{klassen_id}/delete", follow_redirects=True)
    assert db.session.get(SchoolClass, klassen_id) is None
    assert db.session.query(Membership).filter_by(class_id=klassen_id).count() == 0
    assert db.session.query(Lesson).filter_by(class_id=klassen_id).count() == 0


def test_loeschen_laesst_andere_klassen_unberuehrt(app, client):
    _admin(client)
    weg, bleibt = _klasse(name="WEG1"), _klasse(name="BLEIBT2")
    db.session.add(_stunde(bleibt)); db.session.commit()
    bleibt_id = bleibt.id
    client.post(f"/admin/klassen/{weg.id}/delete", follow_redirects=True)
    assert db.session.get(SchoolClass, bleibt_id) is not None
    assert db.session.query(Lesson).filter_by(class_id=bleibt_id).count() == 1


def test_loeschen_braucht_die_richtige_klasse(app, client):
    _admin(client)
    assert client.post("/admin/klassen/999/delete").status_code == 404


# --- Konten -------------------------------------------------------------------

def test_kontenuebersicht_zeigt_konten_ohne_passwortdaten(app, client):
    admin = _admin(client)
    weiterer = User(email="schueler@b.de", confirmed=False)
    weiterer.set_password("geheim123")
    db.session.add(weiterer); db.session.commit()
    html = client.get("/admin/konten").data.decode()
    assert "schueler@b.de" in html and "chef@b.de" in html
    # Weder Hash noch Passwort duerfen in der Oberflaeche auftauchen.
    assert weiterer.password_hash not in html
    assert "$argon2" not in html


def test_kontenuebersicht_weist_administratoren_aus(app, client):
    _admin(client)
    html = client.get("/admin/konten").data.decode()
    assert "Admin" in html


def test_passwort_reset_verschickt_eine_mail_an_das_konto(app, client):
    from app.extensions import mail
    _admin(client)
    ziel = User(email="schueler@b.de", confirmed=True)
    ziel.set_password("geheim123")
    db.session.add(ziel); db.session.commit()
    with mail.record_messages() as outbox:
        resp = client.post(f"/admin/konten/{ziel.id}/reset", follow_redirects=True)
    assert resp.status_code == 200
    assert len(outbox) == 1
    assert outbox[0].recipients == ["schueler@b.de"]
    assert f"/reset-password/{ziel.id}/" in outbox[0].body


def test_der_ruecksetzlink_erscheint_nicht_in_der_oberflaeche(app, client):
    """Der Admin loest nur aus — sehen soll den Link nur das Postfach."""
    _admin(client)
    ziel = User(email="schueler@b.de", confirmed=True)
    ziel.set_password("geheim123")
    db.session.add(ziel); db.session.commit()
    resp = client.post(f"/admin/konten/{ziel.id}/reset", follow_redirects=True)
    assert b"/reset-password/" not in resp.data


def test_reset_fuer_unbekanntes_konto_ist_nicht_moeglich(app, client):
    _admin(client)
    assert client.post("/admin/konten/999/reset").status_code == 404
