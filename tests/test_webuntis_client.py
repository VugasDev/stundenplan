import datetime
import pytest
from app.webuntis_client import fetch_classes, fetch_class_lessons


class _FakeKlasse:
    def __init__(self, id, name): self.id, self.name = id, name


class _FakeNamed:
    def __init__(self, name): self.name = name


class _FakePeriode:
    """Nachbildung einer webuntis-Periode mit den Feldern, die
    fetch_class_lessons tatsaechlich liest."""
    def __init__(self, start, end, subjects=(), rooms=(), teachers=(), code=None):
        self.start, self.end = start, end
        self.subjects = [_FakeNamed(n) for n in subjects]
        self.rooms = [_FakeNamed(n) for n in rooms]
        self.teachers = [_FakeNamed(n) for n in teachers]
        self.code = code


class _FakeSession:
    """Minimale Nachbildung der webuntis-Session."""
    def __init__(self, klassen=(), perioden=()):
        self._klassen, self._perioden = klassen, perioden
        self.angefragte_klasse = None
        self.eingeloggt = False
    def login(self): self.eingeloggt = True; return self
    def logout(self): self.eingeloggt = False
    def klassen(self): return self._klassen
    def timetable(self, start, end, **kw):
        self.angefragte_klasse = kw.get("klasse")
        return self._perioden


def test_klassenliste_wird_auf_id_und_name_reduziert():
    fake = _FakeSession(klassen=[_FakeKlasse(7, "FI42"), _FakeKlasse(9, "FIT61")])
    klassen = fetch_classes({}, session_factory=lambda c: fake)
    assert [(k.id, k.name) for k in klassen] == [(7, "FI42"), (9, "FIT61")]
    assert fake.eingeloggt is False   # Abmeldung auch im Erfolgsfall


def test_klassenplan_fragt_genau_die_uebergebene_klasse_ab():
    fake = _FakeSession(perioden=[])
    fetch_class_lessons({}, 7, datetime.date(2026, 9, 14), datetime.date(2026, 9, 20),
                        session_factory=lambda c: fake)
    assert fake.angefragte_klasse == 7


def test_klassenplan_fuehrt_mehrere_faecher_raeume_lehrer_zusammen():
    """Regression fuer W6: fetch_class_lessons wurde nur mit einer leeren
    Periodenliste getestet. Ein falscher Attributname bei _join_names oder
    der Code-Durchreichung fiele damit erst im Betrieb auf, und dort nur als
    'Fach leer'."""
    start = datetime.datetime(2026, 9, 16, 7, 30)
    end = datetime.datetime(2026, 9, 16, 8, 15)
    periode_voll = _FakePeriode(
        start, end, subjects=["ITD", "WBE"], rooms=["K204", "K205"],
        teachers=["MUE", "SCH"], code="cancelled")
    periode_leer = _FakePeriode(start, end, subjects=[], rooms=[], teachers=[], code=None)
    fake = _FakeSession(perioden=[periode_voll, periode_leer])

    ergebnis = fetch_class_lessons({}, 7, datetime.date(2026, 9, 14),
                                   datetime.date(2026, 9, 20),
                                   session_factory=lambda c: fake)

    voll, leer = ergebnis
    assert voll.subject == "ITD, WBE"
    assert voll.room == "K204, K205"
    assert voll.teacher == "MUE, SCH"
    assert voll.code == "cancelled"
    assert voll.start == start and voll.end == end

    assert leer.subject == ""
    assert leer.room == ""
    assert leer.teacher == ""
    assert leer.code is None


def test_fetch_classes_logs_out_even_on_error():
    class _Boom(_FakeSession):
        def klassen(self):
            raise RuntimeError("boom")
    fake = _Boom()
    with pytest.raises(RuntimeError):
        fetch_classes({}, session_factory=lambda c: fake)
    assert fake.eingeloggt is False


def test_fetch_class_lessons_logs_out_even_on_error():
    class _Boom(_FakeSession):
        def timetable(self, start, end, **kw):
            raise RuntimeError("boom")
    fake = _Boom()
    with pytest.raises(RuntimeError):
        fetch_class_lessons({}, 7, datetime.date(2026, 9, 14), datetime.date(2026, 9, 20),
                            session_factory=lambda c: fake)
    assert fake.eingeloggt is False


# --- Unvollstaendige Angaben einer Periode ------------------------------------

class _WirftBeimZugriff:
    """Bildet nach, was die Bibliothek bei einer Vertretung mit entferntem
    Lehrer tut.

    Entscheidend: Schon das *Lesen* des Attributs wirft, nicht erst das
    Iterieren — `teachers` ist bei webuntis eine Property, die die Lehrer-ID 0
    nachschlaegt, keinen Treffer findet und dabei IndexError wirft. Ein Test,
    der nur das Iterieren scheitern laesst, geht an der Ursache vorbei.
    """
    def __get__(self, obj, typ=None):
        raise IndexError("list index out of range")


def _periode_mit_luecke(kaputt=(), subject="SWD"):
    """Periode, bei der die genannten Attribute beim Lesen scheitern."""
    felder = {
        "start": datetime.datetime(2026, 9, 30, 13, 0),
        "end": datetime.datetime(2026, 9, 30, 13, 45),
        "subjects": [_Kuerzel(subject)],
        "rooms": [_Kuerzel("K205")],
        "teachers": [_Kuerzel("MUE")],
        "code": None,
    }
    for name in kaputt:
        felder[name] = _WirftBeimZugriff()      # als Klassenattribut = Property
    return type("Periode", (), felder)()


class _Kuerzel:
    def __init__(self, name): self.name = name


class _SessionMitPerioden:
    def __init__(self, perioden): self._perioden = perioden
    def login(self): return self
    def logout(self): pass
    def timetable(self, start, end, **kw): return self._perioden


def test_stunde_ohne_lesbaren_lehrer_faellt_nicht_aus():
    """Eine einzelne kaputte Angabe darf nicht den ganzen Klassenplan kosten."""
    p = _periode_mit_luecke(kaputt=["teachers"])
    ergebnis = fetch_class_lessons({}, 7, datetime.date(2026, 9, 30),
                                   datetime.date(2026, 10, 1),
                                   session_factory=lambda c: _SessionMitPerioden([p]))
    assert len(ergebnis) == 1
    assert ergebnis[0].subject == "SWD"      # der Rest bleibt erhalten
    assert ergebnis[0].room == "K205"
    assert ergebnis[0].teacher == ""         # nur die Lehrerangabe fehlt


def test_eine_kaputte_stunde_reisst_die_anderen_nicht_mit():
    perioden = [_periode_mit_luecke(subject="ITD"),
                _periode_mit_luecke(kaputt=["teachers"], subject="KAPUTT"),
                _periode_mit_luecke(subject="EVP")]
    ergebnis = fetch_class_lessons({}, 7, datetime.date(2026, 9, 30),
                                   datetime.date(2026, 10, 1),
                                   session_factory=lambda c: _SessionMitPerioden(perioden))
    assert [r.subject for r in ergebnis] == ["ITD", "KAPUTT", "EVP"]


def test_auch_fach_und_raum_werden_abgesichert():
    p = _periode_mit_luecke(kaputt=["subjects", "rooms"])
    ergebnis = fetch_class_lessons({}, 7, datetime.date(2026, 9, 30),
                                   datetime.date(2026, 10, 1),
                                   session_factory=lambda c: _SessionMitPerioden([p]))
    assert ergebnis[0].subject == "" and ergebnis[0].room == ""
    assert ergebnis[0].teacher == "MUE"
