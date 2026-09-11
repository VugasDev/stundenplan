import datetime

from app.schedule import (may_fetch_automatically, may_fetch_manually,
                          cooldown_remaining, age_in_minutes,
                          AUTO_INTERVAL_MINUTES, MANUAL_COOLDOWN_MINUTES)


def _zeit(h, m=0):
    return datetime.datetime(2026, 9, 16, h, m)


def test_nachts_wird_nicht_automatisch_abgerufen():
    assert may_fetch_automatically(None, _zeit(23)) is False
    assert may_fetch_automatically(None, _zeit(5, 59)) is False
    assert may_fetch_automatically(None, _zeit(6)) is True
    assert may_fetch_automatically(None, _zeit(21, 59)) is True
    assert may_fetch_automatically(None, _zeit(22)) is False


def test_automatischer_abruf_haelt_das_intervall_ein():
    letzter = _zeit(10)
    zu_frueh = letzter + datetime.timedelta(minutes=AUTO_INTERVAL_MINUTES - 1)
    faellig = letzter + datetime.timedelta(minutes=AUTO_INTERVAL_MINUTES)
    assert may_fetch_automatically(letzter, zu_frueh) is False
    assert may_fetch_automatically(letzter, faellig) is True


def test_manueller_abruf_ist_nach_der_sperrfrist_wieder_moeglich():
    letzter = _zeit(10)
    assert may_fetch_manually(letzter, _zeit(10, 14)) is False
    assert may_fetch_manually(letzter, _zeit(10, 15)) is True


def test_manueller_abruf_ignoriert_das_nachtfenster():
    # Wer nachts nachsieht, soll aktualisieren duerfen — nur der Automat schweigt.
    assert may_fetch_manually(None, _zeit(23, 30)) is True


def test_ohne_bisherigen_abruf_darf_sofort_geholt_werden():
    assert may_fetch_manually(None, _zeit(12)) is True
    assert cooldown_remaining(None, _zeit(12)) == 0


def test_restliche_sperrzeit_wird_aufgerundet_gemeldet():
    letzter = _zeit(10)
    assert cooldown_remaining(letzter, _zeit(10, 1)) == MANUAL_COOLDOWN_MINUTES - 1
    assert cooldown_remaining(letzter, _zeit(10, 20)) == 0


def test_alter_des_zwischenstands():
    assert age_in_minutes(None, _zeit(10)) is None
    assert age_in_minutes(_zeit(10), _zeit(10, 7)) == 7


def test_zukunfts_zeitstempel_cooldown_wird_nicht_ueberschritten():
    # Systemzeitsprung oder Zeitumstellung: letzter Abruf liegt in der Zukunft.
    # cooldown_remaining darf nie laenger als MANUAL_COOLDOWN_MINUTES sein.
    letzter = _zeit(10)
    eine_stunde_zurueck = letzter - datetime.timedelta(hours=1)
    assert cooldown_remaining(letzter, eine_stunde_zurueck) <= MANUAL_COOLDOWN_MINUTES


def test_zukunfts_zeitstempel_alter_wird_nicht_negativ():
    # age_in_minutes darf nie negativ sein.
    letzter = _zeit(10)
    eine_stunde_zurueck = letzter - datetime.timedelta(hours=1)
    alter = age_in_minutes(letzter, eine_stunde_zurueck)
    assert alter is not None
    assert alter >= 0


def test_zukunfts_zeitstempel_abruf_verhalten():
    # Bei Zukunfts-Zeitstempel: kein Abruf, solange die Frist rechnerisch nicht abgelaufen ist.
    # Begründung: Der Zukunfts-Zeitstempel bedeutet, dass der "letzte Abruf" noch nicht
    # stattgefunden hat (oder die Systemzeit ist vor dem Abruf). In beiden Fällen ist
    # die sichere Reaktion, nicht sofort wieder abzurufen — wir klemmen die verstrichene
    # Zeit auf null, als würde der Abruf gerade jetzt stattfinden.
    letzter = _zeit(10)
    eine_stunde_zurueck = letzter - datetime.timedelta(hours=1)
    assert may_fetch_manually(letzter, eine_stunde_zurueck) is False
    assert may_fetch_automatically(letzter, eine_stunde_zurueck) is False
