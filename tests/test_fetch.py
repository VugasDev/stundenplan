import datetime
from app.extensions import db
from app.models import SchoolClass, Lesson
from app.fetch import fetch_class, run_all, purge_outside_window
from app.lessons import RawLesson


def _klasse(**kw):
    vorgabe = dict(server_url="s", school="s", untis_class_id=7, name="FI42",
                   username="u", password_encrypted="enc")
    vorgabe.update(kw)
    k = SchoolClass(**vorgabe)
    db.session.add(k); db.session.commit()
    return k


class _Cipher:
    def decrypt(self, token): return "geheim"


def _raw(tag="2026-09-16", start="07:30", end="08:15", subject="ITD"):
    d = datetime.date.fromisoformat(tag)
    return RawLesson(
        start=datetime.datetime.combine(d, datetime.time.fromisoformat(start)),
        end=datetime.datetime.combine(d, datetime.time.fromisoformat(end)),
        subject=subject, room="K204", teacher="MUE", code=None)


def test_abruf_speichert_die_stunden_an_der_klasse(app):
    k = _klasse()
    fetch_class(k, _Cipher(), today=datetime.date(2026, 9, 16),
                fetcher=lambda c, kid, s, e: [_raw()])
    assert len(k.lessons) == 1
    assert k.last_fetch_status == "ok"


def test_abruf_uebergibt_die_untis_klassen_id(app):
    k = _klasse(untis_class_id=99)
    gesehen = {}
    def fetcher(credentials, untis_class_id, start, end):
        gesehen["id"] = untis_class_id
        return []
    fetch_class(k, _Cipher(), today=datetime.date(2026, 9, 16), fetcher=fetcher)
    assert gesehen["id"] == 99


def test_klasse_ohne_spende_wird_nicht_abgerufen(app):
    k = _klasse(username=None, password_encrypted=None)
    def fetcher(*a, **kw):
        raise AssertionError("darf nicht aufgerufen werden")
    assert fetch_class(k, _Cipher(), today=datetime.date(2026, 9, 16),
                       fetcher=fetcher) is False


def test_fehler_bleibt_an_der_klasse_haengen_ohne_andere_zu_stoeren(app):
    k = _klasse()
    def fetcher(*a, **kw):
        raise RuntimeError("WebUntis weg")
    fetch_class(k, _Cipher(), today=datetime.date(2026, 9, 16), fetcher=fetcher)
    assert "RuntimeError" in k.last_fetch_status
    assert k.last_fetch_at is not None


def test_stunden_ausserhalb_des_fensters_werden_geloescht(app):
    k = _klasse()
    heute = datetime.date(2026, 9, 16)
    db.session.add_all([
        Lesson(class_id=k.id, date=heute - datetime.timedelta(days=1),
               start_time=datetime.time(8), end_time=datetime.time(9),
               subject="ALT", room="", teacher="", status="normal"),
        Lesson(class_id=k.id, date=heute + datetime.timedelta(days=40),
               start_time=datetime.time(8), end_time=datetime.time(9),
               subject="WEIT", room="", teacher="", status="normal"),
    ])
    db.session.commit()
    geloescht = purge_outside_window(k, heute, 21)
    db.session.commit()
    assert geloescht == 2
    assert k.lessons == []


def test_automatiklauf_ueberspringt_klassen_innerhalb_des_intervalls(app):
    k = _klasse()
    k.last_fetch_at = datetime.datetime(2026, 9, 16, 10, 0)
    db.session.commit()
    anzahl = run_all(_Cipher(), now=datetime.datetime(2026, 9, 16, 10, 30),
                     today=datetime.date(2026, 9, 16),
                     fetcher=lambda c, kid, s, e: [_raw()])
    assert anzahl == 0


def test_automatiklauf_holt_faellige_klassen(app):
    k = _klasse()
    k.last_fetch_at = datetime.datetime(2026, 9, 16, 8, 0)
    db.session.commit()
    anzahl = run_all(_Cipher(), now=datetime.datetime(2026, 9, 16, 10, 0),
                     today=datetime.date(2026, 9, 16),
                     fetcher=lambda c, kid, s, e: [_raw()])
    assert anzahl == 1
