from flask import Flask

from app.config import Config
from app.extensions import db, login_manager, limiter, csrf, mail


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY ist nicht gesetzt — bitte als Umgebungsvariable setzen.")

    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

    from app.crypto import build_cipher
    app.extensions["cipher"] = build_cipher(app)

    from app import models  # noqa: F401  (Tabellen registrieren)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    @app.get("/healthz")
    def healthz():
        return "ok"

    return app
