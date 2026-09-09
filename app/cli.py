import click
from flask import current_app

from app.extensions import db


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Erstellt alle Tabellen."""
        db.create_all()
        click.echo("Tabellen erstellt.")

    @app.cli.command("fetch-now")
    def fetch_now():
        """Ruft alle Stundenpläne sofort ab (wie der tägliche Job)."""
        from app.fetch import run_all
        run_all(current_app.extensions["cipher"],
                window_days=current_app.config["FETCH_WINDOW_DAYS"])
        click.echo("Abruf abgeschlossen.")
