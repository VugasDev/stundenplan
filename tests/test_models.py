import datetime
from app.extensions import db
from app.models import User, WebUntisAccount, Lesson


def test_user_password_hashing(app):
    u = User(email="a@b.de")
    u.set_password("geheim")
    db.session.add(u)
    db.session.commit()
    assert u.password_hash != "geheim"
    assert u.check_password("geheim") is True
    assert u.check_password("falsch") is False
    assert u.confirmed is False


def test_account_lesson_relationship(app):
    u = User(email="a@b.de")
    u.set_password("x")
    db.session.add(u)
    db.session.commit()
    acc = WebUntisAccount(
        user_id=u.id, label="BK", color="#ff0000",
        server_url="xyz.webuntis.com", school="s", username="u",
        password_encrypted="enc",
    )
    db.session.add(acc)
    db.session.commit()
    lesson = Lesson(
        account_id=acc.id, date=datetime.date(2026, 9, 10),
        start_time=datetime.time(8, 0), end_time=datetime.time(8, 45),
        subject="WB", room="C005", teacher="GS", status="normal", note="",
    )
    db.session.add(lesson)
    db.session.commit()
    assert acc.lessons[0].subject == "WB"
    assert lesson.account.label == "BK"
