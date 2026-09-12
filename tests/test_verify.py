import pytest

from app.verify import verify_and_list_classes
from app.webuntis_client import UntisClass


def test_erfolgreicher_login_liefert_die_klassenliste():
    def lister(credentials, **kw):
        assert credentials["username"] == "schueler"
        assert credentials["password"] == "geheim"
        return [UntisClass(7, "FI42")]
    ok, klassen, fehler = verify_and_list_classes(
        "s.webuntis.com", "s", "schueler", "geheim", lister=lister)
    assert ok is True
    assert [k.name for k in klassen] == ["FI42"]
    assert fehler == ""


def test_falsche_zugangsdaten_liefern_keine_klassen():
    def lister(credentials, **kw):
        raise RuntimeError("bad credentials")
    ok, klassen, fehler = verify_and_list_classes(
        "s.webuntis.com", "s", "schueler", "falsch", lister=lister)
    assert ok is False
    assert klassen == []
    assert fehler != ""


def test_fehlermeldung_enthaelt_niemals_das_passwort():
    def lister(credentials, **kw):
        raise RuntimeError(f"Login failed for {credentials['password']}")
    ok, klassen, fehler = verify_and_list_classes(
        "s.webuntis.com", "s", "schueler", "supergeheim", lister=lister)
    assert "supergeheim" not in fehler
