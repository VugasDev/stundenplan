from app.extensions import db
from app.models import User, WebUntisAccount


def _login(app, client):
    u = User(email="a@b.de"); u.set_password("geheim123"); u.confirmed = True
    db.session.add(u); db.session.commit()
    client.post("/login", data={"email": "a@b.de", "password": "geheim123"})
    return u


def test_add_account_encrypts_password(app, client):
    _login(app, client)
    client.post("/accounts/add", data={
        "label": "BK", "color": "#ff0000", "server_url": "xyz.webuntis.com",
        "school": "bku", "username": "fi42", "password": "meingeheim",
    }, follow_redirects=True)
    acc = db.session.query(WebUntisAccount).filter_by(username="fi42").one()
    assert acc.password_encrypted != "meingeheim"
    cipher = app.extensions["cipher"]
    assert cipher.decrypt(acc.password_encrypted) == "meingeheim"


def test_list_shows_own_accounts_only(app, client):
    u = _login(app, client)
    db.session.add(WebUntisAccount(user_id=u.id, label="Meins", color="#fff",
                                   server_url="s", school="x", username="u1",
                                   password_encrypted=app.extensions["cipher"].encrypt("p")))
    other = User(email="x@y.de"); other.set_password("x"); other.confirmed=True
    db.session.add(other); db.session.commit()
    db.session.add(WebUntisAccount(user_id=other.id, label="Fremd", color="#fff",
                                   server_url="s", school="x", username="u2",
                                   password_encrypted=app.extensions["cipher"].encrypt("p")))
    db.session.commit()
    resp = client.get("/accounts")
    assert b"Meins" in resp.data
    assert b"Fremd" not in resp.data


def test_edit_empty_password_keeps_old(app, client):
    u = _login(app, client)
    cipher = app.extensions["cipher"]
    acc = WebUntisAccount(user_id=u.id, label="BK", color="#fff", server_url="s",
                          school="x", username="u1", password_encrypted=cipher.encrypt("alt"))
    db.session.add(acc); db.session.commit()
    client.post(f"/accounts/{acc.id}/edit", data={
        "label": "BK-neu", "color": "#00ff00", "server_url": "s", "school": "x",
        "username": "u1", "password": "",
    }, follow_redirects=True)
    refreshed = db.session.get(WebUntisAccount, acc.id)
    assert refreshed.label == "BK-neu"
    assert cipher.decrypt(refreshed.password_encrypted) == "alt"


def test_cannot_edit_foreign_account(app, client):
    _login(app, client)
    other = User(email="x@y.de"); other.set_password("x"); other.confirmed=True
    db.session.add(other); db.session.commit()
    acc = WebUntisAccount(user_id=other.id, label="Fremd", color="#fff", server_url="s",
                          school="x", username="u2",
                          password_encrypted=app.extensions["cipher"].encrypt("p"))
    db.session.add(acc); db.session.commit()
    resp = client.post(f"/accounts/{acc.id}/edit", data={
        "label": "HACK", "color": "#000", "server_url": "s", "school": "x",
        "username": "u2", "password": "",
    })
    assert resp.status_code == 404
    assert db.session.get(WebUntisAccount, acc.id).label == "Fremd"


def test_delete_own_account(app, client):
    u = _login(app, client)
    acc = WebUntisAccount(user_id=u.id, label="BK", color="#fff", server_url="s",
                          school="x", username="u1",
                          password_encrypted=app.extensions["cipher"].encrypt("p"))
    db.session.add(acc); db.session.commit()
    acc_id = acc.id
    client.post(f"/accounts/{acc_id}/delete", follow_redirects=True)
    assert db.session.get(WebUntisAccount, acc_id) is None
