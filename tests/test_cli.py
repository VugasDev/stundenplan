from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User


def test_init_db_creates_tables():
    app = create_app(TestConfig)
    runner = app.test_cli_runner()
    result = runner.invoke(args=["init-db"])
    assert result.exit_code == 0
    with app.app_context():
        # Tabelle existiert -> Query wirft nicht
        assert db.session.query(User).count() == 0


def test_migration_legt_je_konto_eine_klasse_und_mitgliedschaft_an(app):
    from app.models import User, WebUntisAccount, SchoolClass, Membership
    from app.cli import migrate_accounts_to_classes
    from app.webuntis_client import UntisClass
    from app.extensions import db

    u = User(email="a@b.de"); u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    acc = WebUntisAccount(user_id=u.id, label="FI42", color="#fff",
                          server_url="s.webuntis.com", school="s",
                          username="schueler", password_encrypted="enc")
    db.session.add(acc); db.session.commit()

    zuordnung = migrate_accounts_to_classes(
        lister=lambda credentials: [UntisClass(7, "FI42"), UntisClass(9, "FIT61")],
        cipher=type("C", (), {"decrypt": lambda self, t: "geheim"})(),
    )
    assert zuordnung == {acc.id: 7}
    k = db.session.query(SchoolClass).one()
    assert (k.untis_class_id, k.name) == (7, "FI42")
    assert k.password_encrypted == "enc"          # Spende wird uebernommen
    assert k.donor_user_id == u.id
    assert db.session.query(Membership).count() == 1


def test_migration_ueberspringt_konten_ohne_passenden_klassennamen(app):
    from app.models import User, WebUntisAccount, SchoolClass
    from app.cli import migrate_accounts_to_classes
    from app.webuntis_client import UntisClass
    from app.extensions import db

    u = User(email="a@b.de"); u.set_password("geheim123")
    db.session.add(u); db.session.commit()
    db.session.add(WebUntisAccount(user_id=u.id, label="KMS", color="#fff",
                                   server_url="s", school="s", username="u",
                                   password_encrypted="enc"))
    db.session.commit()
    zuordnung = migrate_accounts_to_classes(
        lister=lambda credentials: [UntisClass(3, "AK61")],
        cipher=type("C", (), {"decrypt": lambda self, t: "geheim"})(),
    )
    assert zuordnung == {}                        # nichts geraten
    assert db.session.query(SchoolClass).count() == 0
