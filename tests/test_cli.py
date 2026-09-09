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
