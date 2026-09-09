from flask import Flask

from app.config import Config
from app.extensions import db, login_manager, limiter, csrf, mail


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

    @app.get("/healthz")
    def healthz():
        return "ok"

    return app
