import datetime
from app.extensions import db
from app.models import User, Lesson


def test_user_password_hashing(app):
    u = User(email="a@b.de")
    u.set_password("geheim")
    db.session.add(u)
    db.session.commit()
    assert u.password_hash != "geheim"
    assert u.check_password("geheim") is True
    assert u.check_password("falsch") is False
    assert u.confirmed is False


def test_klassenquelle_ohne_spende_hat_keine_zugangsdaten(app):
    from app.models import SchoolClass
    k = SchoolClass(server_url="s.webuntis.com", school="s",
                    untis_class_id=42, name="FI42")
    db.session.add(k); db.session.commit()
    assert k.has_source is False
    assert k.password_encrypted is None


def test_klassenquelle_mit_spende_kennt_ihren_spender(app):
    from app.models import SchoolClass, User
    u = User(email="spender@b.de"); u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    k = SchoolClass(server_url="s.webuntis.com", school="s", untis_class_id=42,
                    name="FI42", username="u", password_encrypted="verschluesselt",
                    donor_user_id=u.id)
    db.session.add(k); db.session.commit()
    assert k.has_source is True
    assert k.donor_user_id == u.id


def test_mitgliedschaft_verbindet_person_und_klasse(app):
    from app.models import SchoolClass, Membership, User
    u = User(email="a@b.de"); u.set_password("geheim123")
    k = SchoolClass(server_url="s", school="s", untis_class_id=1, name="FI42")
    db.session.add_all([u, k]); db.session.commit()
    m = Membership(user_id=u.id, class_id=k.id)
    db.session.add(m); db.session.commit()
    assert m.verified_at is not None
    assert k in [x.school_class for x in u.memberships]


def test_stunden_haengen_an_der_klasse_nicht_an_der_person(app):
    from app.models import SchoolClass, Lesson
    import datetime
    k = SchoolClass(server_url="s", school="s", untis_class_id=1, name="FI42")
    db.session.add(k); db.session.commit()
    db.session.add(Lesson(class_id=k.id, date=datetime.date(2026, 9, 16),
                          start_time=datetime.time(7, 30), end_time=datetime.time(9, 0),
                          subject="ITD", room="K204", teacher="MUE", status="normal"))
    db.session.commit()
    assert len(k.lessons) == 1
