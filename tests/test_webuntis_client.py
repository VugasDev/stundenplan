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


class _FakeSession:
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
    session = _FakeSession(periods)
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
    session = _FakeSession(periods)
    creds = {"server_url": "s", "school": "sch", "username": "u", "password": "p"}
    raw = fetch_raw_lessons(creds, d.date(), d.date(), session_factory=lambda c: session)
    assert raw[0].subject == ""
    assert raw[0].room == ""
    assert raw[0].teacher == ""
    assert raw[0].code == "cancelled"


def test_fetch_logs_out_even_on_timetable_error():
    class _Boom(_FakeSession):
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
