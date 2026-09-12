from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User


def _create_webuntis_accounts_table():
    """Legt die alte Tabelle im Test selbst an (das ORM-Modell wurde entfernt)."""
    db.session.execute(db.text(
        "CREATE TABLE webuntis_accounts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER NOT NULL, "
        "label VARCHAR(100) NOT NULL, "
        "server_url VARCHAR(255) NOT NULL, "
        "school VARCHAR(255) NOT NULL, "
        "username VARCHAR(255) NOT NULL, "
        "password_encrypted TEXT NOT NULL)"
    ))
    db.session.commit()


def _insert_account(user_id, label, server_url, school, username, password_encrypted) -> int:
    result = db.session.execute(db.text(
        "INSERT INTO webuntis_accounts "
        "(user_id, label, server_url, school, username, password_encrypted) "
        "VALUES (:user_id, :label, :server_url, :school, :username, :password_encrypted)"
    ), {"user_id": user_id, "label": label, "server_url": server_url, "school": school,
        "username": username, "password_encrypted": password_encrypted})
    db.session.commit()
    return result.lastrowid


def test_init_db_creates_tables():
    app = create_app(TestConfig)
    runner = app.test_cli_runner()
    result = runner.invoke(args=["init-db"])
    assert result.exit_code == 0
    with app.app_context():
        # Tabelle existiert -> Query wirft nicht
        assert db.session.query(User).count() == 0


def test_migration_legt_je_konto_eine_klasse_und_mitgliedschaft_an(app):
    from app.models import User, SchoolClass, Membership
    from app.cli import migrate_accounts_to_classes
    from app.webuntis_client import UntisClass
    from app.extensions import db

    u = User(email="a@b.de"); u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    _create_webuntis_accounts_table()
    acc_id = _insert_account(u.id, "FI42", "s.webuntis.com", "s", "schueler", "enc")

    zuordnung = migrate_accounts_to_classes(
        lister=lambda credentials: [UntisClass(7, "FI42"), UntisClass(9, "FIT61")],
        cipher=type("C", (), {"decrypt": lambda self, t: "geheim"})(),
    )
    assert zuordnung == {acc_id: 7}
    k = db.session.query(SchoolClass).one()
    assert (k.untis_class_id, k.name) == (7, "FI42")
    assert k.password_encrypted == "enc"          # Spende wird uebernommen
    assert k.donor_user_id == u.id
    assert db.session.query(Membership).count() == 1


def test_migration_ueberspringt_konten_ohne_passenden_klassennamen(app):
    from app.models import User, SchoolClass
    from app.cli import migrate_accounts_to_classes
    from app.webuntis_client import UntisClass
    from app.extensions import db

    u = User(email="a@b.de"); u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    _create_webuntis_accounts_table()
    _insert_account(u.id, "KMS", "s", "s", "u", "enc")

    zuordnung = migrate_accounts_to_classes(
        lister=lambda credentials: [UntisClass(3, "AK61")],
        cipher=type("C", (), {"decrypt": lambda self, t: "geheim"})(),
    )
    assert zuordnung == {}                        # nichts geraten
    assert db.session.query(SchoolClass).count() == 0


def test_migration_ueberlebt_entschluesselungsfehler_bei_einem_konto(app):
    from app.models import User, SchoolClass
    from app.cli import migrate_accounts_to_classes
    from app.webuntis_client import UntisClass
    from app.extensions import db

    u = User(email="a@b.de"); u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    _create_webuntis_accounts_table()
    defekt_id = _insert_account(u.id, "FI42", "s", "s", "u1", "defekt")
    ok_id = _insert_account(u.id, "FIT61", "s", "s", "u2", "enc")

    def decrypt(self, token):
        if token == "defekt":
            raise ValueError("kaputter Chiffretext")
        return "geheim"

    zuordnung = migrate_accounts_to_classes(
        lister=lambda credentials: [UntisClass(7, "FI42"), UntisClass(9, "FIT61")],
        cipher=type("C", (), {"decrypt": decrypt})(),
    )
    # Das defekte Konto wird nicht zugeordnet ...
    assert defekt_id not in zuordnung
    # ... aber das zweite Konto wird trotzdem migriert und bleibt in der DB.
    assert zuordnung == {ok_id: 9}
    k = db.session.query(SchoolClass).one()
    assert (k.untis_class_id, k.name) == (9, "FIT61")


def test_migration_ist_mehrfach_ausfuehrbar_ohne_doppel_eintraege(app):
    from app.models import User, SchoolClass, Membership
    from app.cli import migrate_accounts_to_classes
    from app.webuntis_client import UntisClass
    from app.extensions import db

    u = User(email="a@b.de"); u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    _create_webuntis_accounts_table()
    _insert_account(u.id, "FI42", "s.webuntis.com", "s", "schueler", "enc")

    cipher = type("C", (), {"decrypt": lambda self, t: "geheim"})()
    lister = lambda credentials: [UntisClass(7, "FI42")]

    migrate_accounts_to_classes(lister=lister, cipher=cipher)
    erster_lauf = db.session.query(SchoolClass).one()
    donor_nach_erstem_lauf = erster_lauf.donor_user_id

    migrate_accounts_to_classes(lister=lister, cipher=cipher)

    assert db.session.query(SchoolClass).count() == 1
    assert db.session.query(Membership).count() == 1
    k = db.session.query(SchoolClass).one()
    assert k.donor_user_id == donor_nach_erstem_lauf


def test_migrate_to_classes_legt_lessons_mit_neuem_schema_neu_an(app):
    """Regression fuer K2: eine Bestandsdatenbank hat noch die alte
    lessons-Struktur mit NOT-NULL-Spalte account_id statt class_id.
    db.create_all() allein aendert bestehende Tabellen nicht — der Befehl
    muss die Tabelle deshalb verwerfen und neu anlegen."""
    from app.extensions import db

    db.session.execute(db.text("DROP TABLE lessons"))
    db.session.execute(db.text(
        "CREATE TABLE lessons ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "account_id INTEGER NOT NULL, "
        "date DATE NOT NULL, "
        "start_time TIME NOT NULL, end_time TIME NOT NULL, "
        "subject VARCHAR(100) NOT NULL, room VARCHAR(100) NOT NULL DEFAULT '', "
        "teacher VARCHAR(255) NOT NULL DEFAULT '', "
        "status VARCHAR(20) NOT NULL DEFAULT 'normal', "
        "note VARCHAR(255) NOT NULL DEFAULT '')"
    ))
    db.session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(args=["migrate-to-classes"])
    assert result.exit_code == 0, result.output

    # Die neue Spalte ist abfragbar -> das alte Schema wurde ersetzt.
    db.session.execute(db.text("SELECT class_id FROM lessons")).all()
    assert "webuntis_accounts" in result.output


def test_migration_ohne_tabelle_meldet_leeres_ergebnis(app):
    """Wenn nie ein altes Konto angelegt wurde, existiert die Tabelle nicht."""
    from app.cli import migrate_accounts_to_classes

    zuordnung = migrate_accounts_to_classes(
        lister=lambda credentials: [],
        cipher=type("C", (), {"decrypt": lambda self, t: "geheim"})(),
    )
    assert zuordnung == {}
