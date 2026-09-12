import datetime

import pytest

from app.lifecycle import parse_class_name, resolve_intake_year


# --- Namensschema -------------------------------------------------------------
# XX(X) Bildungsgang, Y letzte Ziffer des Einschulungsjahres, Z Parallelklasse.

def test_klassenname_wird_in_seine_teile_zerlegt():
    teile = parse_class_name("FI42")
    assert (teile.kuerzel, teile.jahresziffer, teile.parallel) == ("FI", 4, "2")


def test_dreibuchstabiges_kuerzel_wird_erkannt():
    teile = parse_class_name("FIT61")
    assert (teile.kuerzel, teile.jahresziffer, teile.parallel) == ("FIT", 6, "1")


def test_einbuchstabiges_kuerzel_wird_erkannt():
    # Am KMS gibt es 37 Klassen mit einem Buchstaben (B, E, G, I, N, R).
    teile = parse_class_name("B62")
    assert (teile.kuerzel, teile.jahresziffer, teile.parallel) == ("B", 6, "2")


def test_mehrstellige_parallelklasse_bleibt_erhalten():
    teile = parse_class_name("FI411")
    assert (teile.kuerzel, teile.jahresziffer, teile.parallel) == ("FI", 4, "11")


def test_kuerzel_wird_in_grossbuchstaben_normalisiert():
    assert parse_class_name("fi42").kuerzel == "FI"


@pytest.mark.parametrize("name", [
    "BEL1",        # zu wenige Ziffern fuer Jahr + Parallelklasse
    "Beratung",    # gar keine Ziffer
    "Bez.Reg.",    # Sonderzeichen
    "JFCH",
    "",
    "42",          # kein Kuerzel
])
def test_abweichende_namen_werden_nicht_geraten(name):
    """28 der 167 Klassen am BKU folgen dem Schema nicht — sie duerfen nicht
    stillgelegt werden, nur weil sich irgendwie Ziffern finden lassen."""
    assert parse_class_name(name) is None


# --- Jahresziffer aufloesen ---------------------------------------------------

def test_jahresziffer_wird_im_fenster_um_das_schuljahr_aufgeloest():
    # Im Schuljahr 2026/27 ist "4" das Jahr 2024, nicht 2014 und nicht 2034.
    assert resolve_intake_year(4, datetime.date(2026, 9, 12)) == 2024
    assert resolve_intake_year(6, datetime.date(2026, 9, 12)) == 2026


def test_mehrdeutige_ziffer_wird_zum_spaeteren_jahr_aufgeloest():
    """Im Zweifel das spaetere Jahr — die Fehlerarten sind nicht gleich schwer.

    Eine laufende Klasse zu frueh stillzulegen nimmt jemandem mitten im
    Schuljahr den Plan weg. Eine langst beendete Klasse weiter abzurufen kostet
    nur einen unnoetigen Abruf. Also wird "7" im Schuljahr 2026/27 als 2027
    gelesen und nicht als 2017.
    """
    assert resolve_intake_year(7, datetime.date(2026, 9, 12)) == 2027
    assert resolve_intake_year(7, datetime.date(2027, 9, 1)) == 2027
    # Erst wenn 2027 aus dem Fenster faellt, wird aus der 7 wieder ein alter Jahrgang.
    assert resolve_intake_year(7, datetime.date(2037, 9, 1)) == 2037


def test_aufloesung_liefert_immer_genau_ein_jahr_je_ziffer():
    heute = datetime.date(2026, 9, 12)
    jahre = {resolve_intake_year(z, heute) for z in range(10)}
    assert len(jahre) == 10
    # Fenster: neun Jahre zurueck bis ein Jahr voraus.
    assert min(jahre) == 2018 and max(jahre) == 2027
