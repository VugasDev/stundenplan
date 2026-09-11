import datetime
from app.extensions import db
from app.models import User, Lesson


def _login_user_with_lessons(app, client):
    from app.models import SchoolClass, Membership
    u = User(email="a@b.de"); u.set_password("geheim123"); u.confirmed = True
    db.session.add(u); db.session.commit()
    k = SchoolClass(server_url="s", school="sch", untis_class_id=7, name="BK",
                    username="u", password_encrypted="enc")
    db.session.add(k); db.session.commit()
    db.session.add(Membership(user_id=u.id, class_id=k.id))
    db.session.add(Lesson(class_id=k.id, date=datetime.date(2026, 9, 10),
                          start_time=datetime.time(8, 0), end_time=datetime.time(8, 45),
                          subject="WB", room="C005", teacher="GS", status="normal"))
    db.session.commit()
    client.post("/login", data={"email": "a@b.de", "password": "geheim123"})
    return u, k


def _lesson(k, day, start, end, subject="ITD", room="K204", status="normal"):
    return Lesson(class_id=k.id, date=datetime.date.fromisoformat(day),
                  start_time=datetime.time.fromisoformat(start),
                  end_time=datetime.time.fromisoformat(end),
                  subject=subject, room=room, teacher="MUE", status=status)


def test_index_requires_login(client):
    assert client.get("/", follow_redirects=False).status_code in (301, 302)


def test_index_shows_lessons_for_week(app, client):
    _login_user_with_lessons(app, client)
    resp = client.get("/?view=week&week=2026-09-07")  # Woche enthält den 10.09.
    assert resp.status_code == 200
    assert b"WB" in resp.data
    assert b"C005" in resp.data


def test_agenda_view_renders(app, client):
    """Die Agenda zeigt nur Bevorstehendes — der Testfall muss deshalb in der
    Zukunft liegen, sonst schlaegt er ab dem Folgetag fehl."""
    u, k = _login_user_with_lessons(app, client)
    morgen = datetime.date.today() + datetime.timedelta(days=1)
    db.session.add(_lesson(k, morgen.isoformat(), "08:00", "09:30", subject="AGENDA"))
    db.session.commit()
    resp = client.get("/?view=agenda")
    assert resp.status_code == 200
    assert b"AGENDA" in resp.data


def test_user_cannot_see_other_users_lessons(app, client):
    from app.models import SchoolClass
    _login_user_with_lessons(app, client)
    other = User(email="x@y.de"); other.set_password("x"); other.confirmed = True
    db.session.add(other); db.session.commit()
    ok = SchoolClass(server_url="s", school="sch", untis_class_id=8, name="Geheim")
    db.session.add(ok); db.session.commit()
    db.session.add(Lesson(class_id=ok.id, date=datetime.date(2026, 9, 10),
                          start_time=datetime.time(9, 0), end_time=datetime.time(9, 45),
                          subject="FREMD", room="Z9", teacher="XX", status="normal"))
    db.session.commit()
    resp = client.get("/?view=week&week=2026-09-07")
    assert b"FREMD" not in resp.data


def test_ohne_mitgliedschaft_sieht_man_fremde_klassen_nicht(app, client):
    from app.models import SchoolClass
    u, k = _login_user_with_lessons(app, client)
    fremd = SchoolClass(server_url="s", school="sch", untis_class_id=99, name="FREMD")
    db.session.add(fremd); db.session.commit()
    db.session.add(_lesson(fremd, "2026-09-10", "09:00", "09:45", subject="GEHEIM"))
    db.session.commit()
    resp = client.get("/?view=week&week=2026-09-07")
    assert b"GEHEIM" not in resp.data


def test_refresh_innerhalb_der_sperrfrist_ruft_nicht_ab(app, client, monkeypatch):
    import app.timetable.routes as routes
    from app.zeit import local_now
    u, k = _login_user_with_lessons(app, client)
    k.last_fetch_at = local_now()      # gerade eben abgerufen
    db.session.commit()
    gerufen = []
    monkeypatch.setattr(routes, "fetch_class",
                        lambda sc, cipher: gerufen.append(sc.id))
    resp = client.post("/refresh", follow_redirects=True)
    assert gerufen == []
    assert "Minute".encode("utf-8") in resp.data   # Hinweis auf die Wartezeit


def test_refresh_nach_ablauf_der_sperrfrist_ruft_ab(app, client, monkeypatch):
    import datetime as dt
    import app.timetable.routes as routes
    from app.zeit import local_now
    u, k = _login_user_with_lessons(app, client)
    k.last_fetch_at = local_now() - dt.timedelta(minutes=20)
    db.session.commit()
    gerufen = []
    monkeypatch.setattr(routes, "fetch_class",
                        lambda sc, cipher: gerufen.append(sc.id))
    client.post("/refresh", follow_redirects=True)
    assert gerufen == [k.id]


# --- Ansichten ---------------------------------------------------------------

def test_standardansicht_ist_die_agenda(app, client):
    _login_user_with_lessons(app, client)
    resp = client.get("/")
    assert b'data-view="agenda"' in resp.data


def test_doppelstunde_erscheint_als_ein_block(app, client):
    u, k = _login_user_with_lessons(app, client)
    db.session.add_all([_lesson(k, "2026-09-16", "07:30", "08:15"),
                        _lesson(k, "2026-09-16", "08:15", "09:00")])
    db.session.commit()
    resp = client.get("/?view=week&week=2026-09-14")
    # Leerzeichen wichtig: sonst zaehlt 'tt-block-head' mit.
    assert resp.data.count(b'class="tt-block ') == 1
    assert b"07:30" in resp.data and b"09:00" in resp.data


def test_wochenansicht_staucht_die_luecke_zur_abendschule(app, client):
    u, k = _login_user_with_lessons(app, client)
    db.session.add_all([_lesson(k, "2026-09-16", "13:00", "14:30", subject="EVP"),
                        _lesson(k, "2026-09-16", "17:00", "18:30", subject="PK")])
    db.session.commit()
    resp = client.get("/?view=week&week=2026-09-14")
    assert b"tt-gap" in resp.data
    assert "2 Std 30 min frei".encode("utf-8") in resp.data


def test_tagesansicht_zeigt_nur_den_gewaehlten_tag(app, client):
    u, k = _login_user_with_lessons(app, client)
    db.session.add_all([_lesson(k, "2026-09-16", "07:30", "09:00", subject="HEUTE"),
                        _lesson(k, "2026-09-17", "07:30", "09:00", subject="MORGEN")])
    db.session.commit()
    resp = client.get("/?view=day&day=2026-09-16")
    assert resp.status_code == 200
    assert b"HEUTE" in resp.data and b"MORGEN" not in resp.data


def test_entfall_und_vertretung_werden_unterschiedlich_markiert(app, client):
    u, k = _login_user_with_lessons(app, client)
    db.session.add_all([
        _lesson(k, "2026-09-16", "07:30", "09:00", subject="AUS", status="cancelled"),
        _lesson(k, "2026-09-16", "09:25", "10:55", subject="VER", status="substitution"),
    ])
    db.session.commit()
    resp = client.get("/?view=week&week=2026-09-14")
    assert b"tt-cancelled" in resp.data
    assert b"tt-substitution" in resp.data


def test_block_nennt_die_klasse(app, client):
    u, k = _login_user_with_lessons(app, client)
    resp = client.get("/?view=week&week=2026-09-07")
    assert b"BK" in resp.data  # Name der Klasse steht im Block


def test_wochentage_stehen_auf_deutsch(app, client):
    u, k = _login_user_with_lessons(app, client)
    db.session.add(_lesson(k, "2026-09-16", "07:30", "09:00"))
    db.session.commit()
    resp = client.get("/?view=week&week=2026-09-14")
    assert "Mi".encode("utf-8") in resp.data
    for englisch in (b"Mon", b"Tue", b"Wed", b"Thu", b"Fri"):
        assert englisch not in resp.data


def test_tagesansicht_nennt_den_wochentag_auf_deutsch(app, client):
    u, k = _login_user_with_lessons(app, client)
    resp = client.get("/?view=day&day=2026-09-16")
    assert "Mittwoch".encode("utf-8") in resp.data
    assert b"Wednesday" not in resp.data


def test_wochenansicht_zeigt_die_jetzt_linie_nur_in_der_aktuellen_woche(app, client):
    u, k = _login_user_with_lessons(app, client)
    heute = datetime.date.today()
    montag = heute - datetime.timedelta(days=heute.weekday())
    db.session.add(_lesson(k, heute.isoformat(), "07:30", "09:00"))
    db.session.commit()
    diese = client.get(f"/?view=week&week={montag.isoformat()}")
    assert b'class="tt-now"' in diese.data
    andere = client.get("/?view=week&week=2026-01-05")
    assert b'class="tt-now"' not in andere.data


def test_tagesansicht_zeigt_die_jetzt_linie_nur_heute(app, client):
    u, k = _login_user_with_lessons(app, client)
    heute = datetime.date.today()
    db.session.add_all([_lesson(k, heute.isoformat(), "07:30", "09:00"),
                        _lesson(k, (heute + datetime.timedelta(days=1)).isoformat(),
                                "07:30", "09:00", subject="MORGEN")])
    db.session.commit()
    assert b'class="tt-now"' in client.get(f"/?view=day&day={heute.isoformat()}").data
    morgen = (heute + datetime.timedelta(days=1)).isoformat()
    assert b'class="tt-now"' not in client.get(f"/?view=day&day={morgen}").data


def test_agenda_haelt_sich_selbst_aktuell(app, client):
    _login_user_with_lessons(app, client)
    resp = client.get("/")
    assert b"agenda-refresh.js" in resp.data
