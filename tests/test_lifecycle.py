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


# --- Ende des Bildungsgangs ---------------------------------------------------

from app.lifecycle import course_ended, STANDARD_LAUFZEITEN  # noqa: E402

LAUFZEITEN = {"FI": 3, "FIT": 4, "FET": 4, "FMT": 4}


def test_dreijaehrige_klasse_endet_zum_schuljahresende():
    # FI42: 2024 eingeschult, drei Jahre -> laeuft bis Sommer 2027.
    assert course_ended("FI42", datetime.date(2027, 7, 1), LAUFZEITEN) is False
    assert course_ended("FI42", datetime.date(2027, 8, 1), LAUFZEITEN) is True


def test_vierjaehrige_klasse_laeuft_ein_jahr_laenger():
    # FIT61: 2026 eingeschult, vier Jahre -> bis Sommer 2030.
    assert course_ended("FIT61", datetime.date(2030, 7, 1), LAUFZEITEN) is False
    assert course_ended("FIT61", datetime.date(2030, 8, 1), LAUFZEITEN) is True


def test_laufende_klasse_ist_nicht_beendet():
    assert course_ended("FI42", datetime.date(2026, 9, 12), LAUFZEITEN) is False
    assert course_ended("FIT61", datetime.date(2026, 9, 12), LAUFZEITEN) is False


def test_unbekanntes_kuerzel_ergibt_keine_aussage():
    """Ohne hinterlegte Laufzeit wird nicht geraten — die Klasse laeuft weiter."""
    assert course_ended("AVV41", datetime.date(2026, 9, 12), LAUFZEITEN) is None
    assert course_ended("B62", datetime.date(2026, 9, 12), LAUFZEITEN) is None


def test_abweichender_name_ergibt_keine_aussage():
    assert course_ended("Beratung", datetime.date(2026, 9, 12), LAUFZEITEN) is None
    assert course_ended("BEL1", datetime.date(2026, 9, 12), LAUFZEITEN) is None


def test_die_belegten_kuerzel_sind_vorbelegt():
    # Gemessen am 2026-09-12: FI ist Berufsschule, FIT/FET/FMT sind Fachschule.
    assert STANDARD_LAUFZEITEN["FI"] == 3
    assert STANDARD_LAUFZEITEN["FIT"] == 4
    assert STANDARD_LAUFZEITEN["FET"] == 4
    assert STANDARD_LAUFZEITEN["FMT"] == 4


# --- Niemand liest die Klasse mehr -------------------------------------------

from app.lifecycle import abandoned, SCHONFRIST_TAGE  # noqa: E402


class _Klasse:
    """Traegt nur, was fuer die Entscheidung noetig ist."""
    def __init__(self, name="FI42", members_left_at=None):
        self.name = name
        self.members_left_at = members_left_at


def test_klasse_mit_mitgliedern_ist_nicht_verlassen():
    assert abandoned(_Klasse(), datetime.date(2026, 9, 12)) is False


def test_schonfrist_von_sieben_tagen_wird_eingehalten():
    assert SCHONFRIST_TAGE == 7
    weg_seit = datetime.date(2026, 9, 5)
    assert abandoned(_Klasse(members_left_at=weg_seit),
                     datetime.date(2026, 9, 11)) is False
    assert abandoned(_Klasse(members_left_at=weg_seit),
                     datetime.date(2026, 9, 12)) is True


def test_wiedereintritt_hebt_die_schonfrist_auf():
    # Der Zeitstempel wird beim Beitritt zurueckgesetzt; ohne ihn laeuft nichts ab.
    assert abandoned(_Klasse(members_left_at=None),
                     datetime.date(2030, 1, 1)) is False


# --- Zusammenfuehrung: wird abgerufen oder nicht? ----------------------------

from app.lifecycle import dormant_reason  # noqa: E402


def test_laufende_klasse_mit_mitgliedern_wird_abgerufen():
    assert dormant_reason(_Klasse(), datetime.date(2026, 9, 12), LAUFZEITEN) is None


def test_verlassene_klasse_wird_stillgelegt():
    k = _Klasse(members_left_at=datetime.date(2026, 9, 1))
    assert dormant_reason(k, datetime.date(2026, 9, 12), LAUFZEITEN) == "verlassen"


def test_abgelaufener_bildungsgang_wird_stillgelegt():
    assert dormant_reason(_Klasse("FI42"), datetime.date(2027, 8, 1),
                          LAUFZEITEN) == "beendet"


def test_unbekanntes_kuerzel_mit_mitgliedern_laeuft_weiter():
    assert dormant_reason(_Klasse("AVV41"), datetime.date(2040, 1, 1),
                          LAUFZEITEN) is None


# --- Laufzeiten aus der Konfiguration ----------------------------------------

from app.lifecycle import laufzeiten_aus_konfiguration  # noqa: E402


def test_ohne_eintrag_gelten_die_vorbelegten_laufzeiten():
    assert laufzeiten_aus_konfiguration(None) == STANDARD_LAUFZEITEN
    assert laufzeiten_aus_konfiguration("") == STANDARD_LAUFZEITEN


def test_eigene_laufzeiten_ergaenzen_die_vorbelegten():
    ergebnis = laufzeiten_aus_konfiguration('{"AVV": 1, "BFA": 2}')
    assert ergebnis["AVV"] == 1 and ergebnis["BFA"] == 2
    assert ergebnis["FI"] == 3          # Vorbelegung bleibt erhalten


def test_eigener_eintrag_ueberschreibt_die_vorbelegung():
    assert laufzeiten_aus_konfiguration('{"FI": 4}')["FI"] == 4


def test_kuerzel_werden_in_grossbuchstaben_verglichen():
    assert laufzeiten_aus_konfiguration('{"avv": 1}')["AVV"] == 1


def test_unbrauchbare_konfiguration_faellt_auf_die_vorbelegung_zurueck():
    """Ein Tippfehler in der .env darf nicht den Abruf lahmlegen."""
    assert laufzeiten_aus_konfiguration("{kaputt") == STANDARD_LAUFZEITEN
    assert laufzeiten_aus_konfiguration('{"FI": "drei"}') == STANDARD_LAUFZEITEN
    assert laufzeiten_aus_konfiguration('["FI", 3]') == STANDARD_LAUFZEITEN
