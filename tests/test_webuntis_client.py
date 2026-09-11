import datetime
from app.webuntis_client import fetch_raw_lessons


class _Named:
    def __init__(self, name):
        self.name = name


class _Period:
    def __init__(self, start, end, subjects, rooms, teachers, code=None):
        self.start, self.end = start, end
        self.subjects = [_Named(s) for s in subjects]
        self.rooms = [_Named(r) for r in rooms]
        self.teachers = [_Named(t) for t in teachers]
        self.code = code


class _FakeSessionRawLessons:
    def __init__(self, periods):
        self._periods = periods
        self.logged_in = False
        self.logged_out = False

    def login(self):
        self.logged_in = True
        return self

    def logout(self):
        self.logged_out = True

    def my_timetable(self, start, end):
        return self._periods


def test_fetch_converts_periods_to_rawlessons():
    d = datetime.datetime(2026, 9, 10, 8, 0)
    periods = [_Period(d, d + datetime.timedelta(minutes=45), ["WB"], ["C005"], ["GS"], None)]
    session = _FakeSessionRawLessons(periods)
    creds = {"server_url": "s", "school": "sch", "username": "u", "password": "p"}

    raw = fetch_raw_lessons(creds, d.date(), d.date(), session_factory=lambda c: session)

    assert session.logged_in and session.logged_out
    assert len(raw) == 1
    assert raw[0].subject == "WB"
    assert raw[0].room == "C005"
    assert raw[0].teacher == "GS"
    assert raw[0].code is None


def test_fetch_handles_empty_element_lists():
    d = datetime.datetime(2026, 9, 10, 8, 0)
    periods = [_Period(d, d + datetime.timedelta(minutes=45), [], [], [], "cancelled")]
    session = _FakeSessionRawLessons(periods)
    creds = {"server_url": "s", "school": "sch", "username": "u", "password": "p"}
    raw = fetch_raw_lessons(creds, d.date(), d.date(), session_factory=lambda c: session)
    assert raw[0].subject == ""
    assert raw[0].room == ""
    assert raw[0].teacher == ""
    assert raw[0].code == "cancelled"


def test_fetch_logs_out_even_on_timetable_error():
    class _Boom(_FakeSessionRawLessons):
        def my_timetable(self, start, end):
            raise RuntimeError("boom")
    session = _Boom([])
    creds = {"server_url": "s", "school": "sch", "username": "u", "password": "p"}
    try:
        fetch_raw_lessons(creds, datetime.date(2026, 9, 10), datetime.date(2026, 9, 10),
                          session_factory=lambda c: session)
    except RuntimeError:
        pass
    assert session.logged_out is True


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
