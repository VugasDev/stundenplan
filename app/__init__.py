import socket

from flask import Flask, send_from_directory, render_template

from app.config import Config
from app.extensions import db, login_manager, limiter, csrf, mail


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY ist nicht gesetzt — bitte als Umgebungsvariable setzen.")

    socket.setdefaulttimeout(app.config["NETWORK_TIMEOUT"])

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

    # Manifest und Service Worker gehoeren an die Wurzel: ein Service Worker
    # darf nur den Pfad verwalten, unter dem er ausgeliefert wird — aus
    # /static/sw.js koennte er die Seiten der App nicht behandeln.
    @app.get("/manifest.webmanifest")
    def manifest():
        return send_from_directory(app.static_folder, "manifest.webmanifest",
                                   mimetype="application/manifest+json")

    @app.get("/sw.js")
    def service_worker():
        antwort = send_from_directory(app.static_folder, "sw.js",
                                      mimetype="text/javascript")
        # Der Worker selbst darf nicht veralten, sonst bleibt eine alte
        # Fassung dauerhaft aktiv.
        antwort.headers["Cache-Control"] = "no-cache"
        return antwort

    @app.get("/offline")
    def offline():
        return render_template("offline.html")

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.timetable import bp as timetable_bp
    app.register_blueprint(timetable_bp)

    from app.classes import bp as classes_bp
    app.register_blueprint(classes_bp)

    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    from app.blocks import wochentag_kurz, wochentag_lang
    app.jinja_env.filters["wochentag_kurz"] = wochentag_kurz
    app.jinja_env.filters["wochentag_lang"] = wochentag_lang

    from app.cli import register_cli
    register_cli(app)

    return app
