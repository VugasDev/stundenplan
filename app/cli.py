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
        from app.zeit import local_today
        run_all(current_app.extensions["cipher"],
                today=local_today(current_app.config["TIMEZONE"]),
                window_days=current_app.config["FETCH_WINDOW_DAYS"])
        click.echo("Abruf abgeschlossen.")

    @app.cli.command("migrate-to-classes")
    def migrate_to_classes():
        """Ueberfuehrt bestehende Zugaenge in Klassenquellen.

        Reihenfolge wichtig: erst die Altdaten aus webuntis_accounts lesen und
        nach school_classes/memberships ueberfuehren, danach erst lessons
        verwerfen und neu anlegen — sonst waeren die Altdaten weg, bevor sie
        gelesen wurden.
        """
        db.create_all()
        zuordnung = migrate_accounts_to_classes()
        click.echo(f"{len(zuordnung)} Zugang/Zugänge überführt.")

        # lessons.account_id war NOT NULL und heisst jetzt class_id;
        # db.create_all() aendert bestehende Tabellen nicht. Die Stunden sind
        # per Definition wegwerfbar (der naechste Abruf bringt sie binnen 90
        # Minuten zurueck) — die Tabelle wird deshalb verworfen und mit dem
        # neuen Schema neu angelegt, statt sie muehsam zu migrieren.
        if db.inspect(db.engine).has_table("lessons"):
            db.session.execute(db.text("DROP TABLE lessons"))
            db.session.commit()
        db.create_all()
        click.echo("Tabelle 'lessons' mit dem neuen Schema (class_id) neu "
                   "angelegt. Der naechste Abruf fuellt sie binnen 90 Minuten "
                   "wieder.")
        click.echo("Hinweis: Die Tabelle 'webuntis_accounts' enthält weiterhin "
                   "verschlüsselte Zugangsdaten. Nach erfolgreicher Prüfung "
                   "von Hand entfernen.")


def migrate_accounts_to_classes(lister=None, cipher=None) -> dict:
    """Ueberfuehrt bestehende Konten in Klassenquellen samt Mitgliedschaft.

    Zugeordnet wird nur, wenn der Anzeigename des Kontos exakt einem Klassennamen
    der Schule entspricht. Der Anzeigename ist frei gewaehlt ("KMS" etwa ist keine
    Klasse) — geraten wird deshalb nicht, solche Konten bleiben stehen und werden
    gemeldet.
    """
    from app.models import SchoolClass, Membership
    from app.webuntis_client import fetch_classes

    lister = lister or fetch_classes
    cipher = cipher or current_app.extensions["cipher"]
    zuordnung = {}

    # Das ORM-Modell WebUntisAccount wurde entfernt (Task 9) — die alte Tabelle
    # wird deshalb per direktem SQL gelesen, ohne dass ein Modell noetig ist.
    if not db.inspect(db.engine).has_table("webuntis_accounts"):
        click.echo("  Keine Tabelle 'webuntis_accounts' vorhanden — nichts zu migrieren.")
        return zuordnung

    accounts = db.session.execute(db.text(
        "SELECT id, user_id, label, server_url, school, username, password_encrypted "
        "FROM webuntis_accounts"
    )).mappings().all()

    for acc in accounts:
        try:
            passwort = cipher.decrypt(acc["password_encrypted"])
        except Exception as exc:
            click.echo(f"  {acc['label']}: Zugangsdaten nicht entschlüsselbar ({type(exc).__name__})")
            continue

        credentials = {"server_url": acc["server_url"], "school": acc["school"],
                       "username": acc["username"], "password": passwort}
        try:
            klassen = lister(credentials)
        except Exception as exc:
            click.echo(f"  {acc['label']}: Klassenliste nicht abrufbar ({type(exc).__name__})")
            continue

        treffer = [k for k in klassen if k.name.upper() == acc["label"].upper()]
        if not treffer:
            click.echo(f"  {acc['label']}: kein Klassenname passt — bitte in der "
                       f"Weboberfläche unter 'Klasse hinzufügen' nachholen")
            continue

        ziel = treffer[0]
        school_class = (db.session.query(SchoolClass)
                        .filter_by(server_url=acc["server_url"], school=acc["school"],
                                   untis_class_id=ziel.id).first())
        if school_class is None:
            school_class = SchoolClass(
                server_url=acc["server_url"], school=acc["school"],
                untis_class_id=ziel.id, name=ziel.name,
                username=acc["username"], password_encrypted=acc["password_encrypted"],
                donor_user_id=acc["user_id"])
            db.session.add(school_class)
            db.session.flush()

        vorhanden = (db.session.query(Membership)
                     .filter_by(user_id=acc["user_id"], class_id=school_class.id).first())
        if vorhanden is None:
            db.session.add(Membership(user_id=acc["user_id"], class_id=school_class.id))
        zuordnung[acc["id"]] = ziel.id
        # Sofort sichern, damit ein Fehler bei einem spaeteren Konto den
        # Fortschritt dieses Kontos nicht zunichtemacht.
        db.session.commit()

    return zuordnung
