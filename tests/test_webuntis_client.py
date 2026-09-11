import datetime
import pytest
from app.webuntis_client import fetch_classes, fetch_class_lessons


class _FakeKlasse:
    def __init__(self, id, name): self.id, self.name = id, name


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
