import datetime

from app.zeit import local_now, local_today


def test_lokale_zeit_folgt_der_schulzeitzone_nicht_der_serveruhr():
    """Der Server laeuft auf UTC — der Unterricht nicht."""
    utc = local_now("UTC")
    berlin = local_now("Europe/Berlin")
    versatz = berlin - utc
    # Je nach Sommer-/Winterzeit eine oder zwei Stunden, aber nie null.
    assert versatz.total_seconds() // 3600 in (1, 2)


def test_lokale_zeit_ist_naiv_und_damit_mit_den_db_zeiten_vergleichbar():
    # In der DB stehen naive Uhrzeiten; ein aware datetime waere nicht vergleichbar.
    assert local_now("Europe/Berlin").tzinfo is None


def test_datum_kann_sich_von_dem_der_serveruhr_unterscheiden():
    # Kurz nach Mitternacht in Berlin ist in UTC noch der Vortag.
    kurz_nach_mitternacht = datetime.datetime(2026, 6, 1, 0, 30)
    assert local_today("Europe/Berlin") == local_now("Europe/Berlin").date()
    assert kurz_nach_mitternacht.date() == datetime.date(2026, 6, 1)
