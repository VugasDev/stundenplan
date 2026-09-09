import datetime

import pytest

from app.blocks import merge_lessons


def L(start, end, subject="ITD", room="K204", teacher="MUE", status="normal",
      account_id=1, day="2026-09-16"):
    """Baut ein Lesson-aehnliches Objekt, wie es aus der DB kommt."""
    return type("L", (), {
        "date": datetime.date.fromisoformat(day),
        "start_time": datetime.time.fromisoformat(start),
        "end_time": datetime.time.fromisoformat(end),
        "subject": subject, "room": room, "teacher": teacher,
        "status": status, "account_id": account_id,
    })()


def test_doppelstunde_wird_ein_block():
    blocks = merge_lessons([L("07:30", "08:15"), L("08:15", "09:00")])
    assert len(blocks) == 1
    assert blocks[0].start_time == datetime.time(7, 30)
    assert blocks[0].end_time == datetime.time(9, 0)
    assert blocks[0].units == 2


def test_pause_dazwischen_bleibt_getrennt():
    # 20:10 endet, 20:15 beginnt: fuenf Minuten Luecke, also zwei Bloecke.
    blocks = merge_lessons([L("19:25", "20:10", subject="SLP1"),
                            L("20:15", "21:00", subject="SLP1"),
                            L("21:00", "21:45", subject="SLP1")])
    assert [(b.start_time.isoformat("minutes"), b.end_time.isoformat("minutes"))
            for b in blocks] == [("19:25", "20:10"), ("20:15", "21:45")]


def test_verschiedene_faecher_verschmelzen_nie():
    blocks = merge_lessons([L("11:15", "12:00", subject="SWD"),
                            L("12:00", "12:45", subject="EVP")])
    assert len(blocks) == 2


def test_raumwechsel_trennt_den_block():
    blocks = merge_lessons([L("11:15", "12:00", room="K205"),
                            L("12:00", "12:45", room="K104")])
    assert len(blocks) == 2


def test_entfallene_stunde_verschmilzt_nicht_mit_regulaerer():
    blocks = merge_lessons([L("07:30", "08:15", status="normal"),
                            L("08:15", "09:00", status="cancelled")])
    assert len(blocks) == 2
    assert [b.status for b in blocks] == ["normal", "cancelled"]


def test_verschiedene_klassen_verschmelzen_nie():
    blocks = merge_lessons([L("07:30", "08:15", account_id=1),
                            L("08:15", "09:00", account_id=2)])
    assert len(blocks) == 2


def test_gleiche_zeiten_an_verschiedenen_tagen_verschmelzen_nie():
    blocks = merge_lessons([L("07:30", "08:15", day="2026-09-16"),
                            L("08:15", "09:00", day="2026-09-17")])
    assert len(blocks) == 2


def test_bloecke_kommen_chronologisch_zurueck():
    blocks = merge_lessons([L("13:00", "13:45", subject="EVP", day="2026-09-17"),
                            L("07:30", "08:15", subject="ITD", day="2026-09-16")])
    assert [b.subject for b in blocks] == ["ITD", "EVP"]


def test_leere_eingabe_ergibt_keine_bloecke():
    assert merge_lessons([]) == []


# --- Zeitachse ---------------------------------------------------------------

from app.blocks import build_axis, PX_PER_MIN, GAP_HEIGHT, GAP_MIN_MINUTES  # noqa: E402


def B(start, end, **kw):
    return merge_lessons([L(start, end, **kw)])[0]


def test_achse_ohne_bloecke_ist_leer():
    axis = build_axis([])
    assert axis.height == 0
    assert axis.segments == []


def test_block_hoehe_entspricht_seiner_dauer():
    axis = build_axis([B("07:30", "09:00")])
    assert axis.height == pytest.approx(90 * PX_PER_MIN)
    assert axis.y(datetime.time(7, 30)) == pytest.approx(0)
    assert axis.y(datetime.time(9, 0)) == pytest.approx(90 * PX_PER_MIN)


def test_kurze_pause_bleibt_massstabsgetreu():
    # 25 Minuten Pause liegen unter der Stauchschwelle.
    assert 25 < GAP_MIN_MINUTES
    axis = build_axis([B("07:30", "09:00"), B("09:25", "10:55")])
    assert axis.y(datetime.time(9, 25)) == pytest.approx(115 * PX_PER_MIN)


def test_lange_luecke_wird_auf_feste_hoehe_gestaucht():
    # Tagesschule bis 14:30, Abendschule ab 17:00 — 150 Minuten Luft.
    axis = build_axis([B("13:00", "14:30"), B("17:00", "18:30")])
    luecke = axis.y(datetime.time(17, 0)) - axis.y(datetime.time(14, 30))
    assert luecke == pytest.approx(GAP_HEIGHT)
    assert luecke < 150 * PX_PER_MIN


def test_gestauchte_luecke_wird_als_segment_mit_dauer_ausgewiesen():
    axis = build_axis([B("13:00", "14:30"), B("17:00", "18:30")])
    gaps = [s for s in axis.segments if s.kind == "gap"]
    assert len(gaps) == 1
    assert gaps[0].minutes == 150
    assert gaps[0].label == "2 Std 30 min frei"


def test_luecke_zaehlt_nur_wenn_an_keinem_tag_unterricht_liegt():
    # Dienstag hat 14:30-17:00 frei, Mittwoch fuellt genau dieses Fenster.
    # Ueber die Woche gesehen ist damit nichts frei — nichts wird gestaucht.
    axis = build_axis([B("13:00", "14:30", day="2026-09-16"),
                       B("17:00", "18:30", day="2026-09-16"),
                       B("14:30", "17:00", day="2026-09-17")])
    assert [s for s in axis.segments if s.kind == "gap"] == []
    assert axis.span(datetime.time(13, 0), datetime.time(18, 30)) == pytest.approx(330 * PX_PER_MIN)


def test_nur_der_tatsaechlich_freie_teil_einer_luecke_wird_gestaucht():
    # Mittwoch 15-16 unterbricht die Luecke: 14:30-15:00 bleibt massstabsgetreu,
    # das durchgehend freie Fenster 16:00-17:00 wird gestaucht.
    axis = build_axis([B("13:00", "14:30", day="2026-09-16"),
                       B("17:00", "18:30", day="2026-09-16"),
                       B("15:00", "16:00", day="2026-09-17")])
    gaps = [(s.start.isoformat("minutes"), s.end.isoformat("minutes"))
            for s in axis.segments if s.kind == "gap"]
    assert gaps == [("16:00", "17:00")]
    assert axis.span(datetime.time(14, 30), datetime.time(15, 0)) == pytest.approx(30 * PX_PER_MIN)


def test_achse_beschriftet_volle_stunden():
    axis = build_axis([B("07:30", "09:00")])
    assert [t.isoformat("minutes") for t, _ in axis.ticks] == ["08:00", "09:00"]


def test_ticks_ueberspringen_gestauchte_luecken():
    axis = build_axis([B("13:00", "14:30"), B("17:00", "18:30")])
    beschriftet = [t.isoformat("minutes") for t, _ in axis.ticks]
    assert "15:00" not in beschriftet and "16:00" not in beschriftet
    assert "14:00" in beschriftet and "18:00" in beschriftet


def test_span_liefert_die_hoehe_eines_blocks():
    axis = build_axis([B("07:30", "09:00")])
    assert axis.span(datetime.time(7, 30), datetime.time(9, 0)) == pytest.approx(90 * PX_PER_MIN)


# --- Agenda ------------------------------------------------------------------

from app.blocks import agenda_view  # noqa: E402

DI = "2026-09-16"
MI = "2026-09-17"


def _now(day, uhrzeit):
    return datetime.datetime.combine(datetime.date.fromisoformat(day),
                                     datetime.time.fromisoformat(uhrzeit))


def test_agenda_zeigt_die_naechste_einheit_des_tages():
    blocks = merge_lessons([L("07:30", "09:00", subject="ITD", day=DI),
                            L("09:25", "10:55", subject="SWD", day=DI)])
    view = agenda_view(blocks, _now(DI, "09:10"))
    assert view.current is None
    assert [b.subject for b in view.upcoming] == ["SWD"]


def test_agenda_kennzeichnet_die_laufende_einheit():
    blocks = merge_lessons([L("07:30", "09:00", subject="ITD", day=DI),
                            L("09:25", "10:55", subject="SWD", day=DI)])
    view = agenda_view(blocks, _now(DI, "08:00"))
    assert view.current.subject == "ITD"
    assert [b.subject for b in view.upcoming] == ["SWD"]


def test_agenda_laesst_vergangene_einheiten_weg():
    blocks = merge_lessons([L("07:30", "09:00", subject="ITD", day=DI),
                            L("13:00", "14:30", subject="EVP", day=DI)])
    view = agenda_view(blocks, _now(DI, "12:00"))
    assert [b.subject for b in view.upcoming] == ["EVP"]


def test_agenda_zeigt_keine_einheiten_anderer_tage():
    blocks = merge_lessons([L("07:30", "09:00", subject="ITD", day=DI),
                            L("07:30", "09:00", subject="WB", day=MI)])
    view = agenda_view(blocks, _now(DI, "06:00"))
    assert [b.subject for b in view.upcoming] == ["ITD"]


def test_nach_schulschluss_bleibt_nur_der_ausblick_auf_den_naechsten_tag():
    blocks = merge_lessons([L("07:30", "09:00", subject="ITD", day=DI),
                            L("08:00", "09:30", subject="WB", day=MI),
                            L("09:45", "11:15", subject="WB2", day=MI)])
    view = agenda_view(blocks, _now(DI, "20:00"))
    assert view.current is None
    assert view.upcoming == []
    # Nur der erste Block des naechsten Tages — kein zweiter Wochenplan.
    assert view.next_day.subject == "WB"


def test_ohne_weiteren_unterricht_bleibt_die_agenda_leer():
    blocks = merge_lessons([L("07:30", "09:00", day=DI)])
    view = agenda_view(blocks, _now(DI, "20:00"))
    assert view.current is None and view.upcoming == [] and view.next_day is None


def test_agenda_meldet_wenn_nach_der_laufenden_einheit_schluss_ist():
    blocks = merge_lessons([L("19:25", "21:45", subject="SLP1", day=DI)])
    view = agenda_view(blocks, _now(DI, "21:30"))
    assert view.current.subject == "SLP1"
    assert view.upcoming == []
    assert view.feierabend is True


def test_agenda_meldet_keinen_feierabend_solange_noch_etwas_kommt():
    blocks = merge_lessons([L("19:25", "20:10", subject="SLP1", day=DI),
                            L("20:15", "21:45", subject="SLP2", day=DI)])
    view = agenda_view(blocks, _now(DI, "19:30"))
    assert view.feierabend is False


# --- Daten fuer die Jetzt-Linie ---------------------------------------------

from app.blocks import axis_payload  # noqa: E402


def test_achse_liefert_ihre_segmente_fuer_den_browser():
    axis = build_axis([B("13:00", "14:30"), B("17:00", "18:30")])
    daten = axis_payload(axis)
    assert daten["height"] == pytest.approx(axis.height)
    # Minuten seit Mitternacht: im Browser einfacher zu rechnen als "13:00".
    assert daten["segments"][0]["start"] == 780
    assert daten["segments"][0]["end"] == 870
    assert daten["segments"][0]["kind"] == "scaled"


def test_segmentdaten_enthalten_auch_die_gestauchte_luecke():
    daten = axis_payload(build_axis([B("13:00", "14:30"), B("17:00", "18:30")]))
    gaps = [s for s in daten["segments"] if s["kind"] == "gap"]
    assert len(gaps) == 1
    assert (gaps[0]["start"], gaps[0]["end"]) == (870, 1020)


def test_leere_achse_liefert_leere_segmentliste():
    assert axis_payload(build_axis([])) == {"height": 0.0, "segments": []}
