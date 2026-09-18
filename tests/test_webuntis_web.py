"""Zusatzinformationen aus der Web-Oberflaeche von WebUntis.

Die JSON-RPC-Schnittstelle, die die `webuntis`-Bibliothek nutzt, liefert
weder Unterrichtstexte noch Konferenzlinks. Beides steht nur in der API
hinter der Weboberflaeche.
"""
import datetime

from app.webuntis_web import infos_aus_wochendaten, konferenz_aus_detail


def _antwort(perioden, class_id=42):
    return {"data": {"result": {"data": {"elementPeriods": {str(class_id): perioden}}}}}


def _periode(**felder):
    grund = {"id": 1, "date": 20260916, "startTime": 1925, "endTime": 2010,
             "lessonText": "", "periodText": "", "periodInfo": "", "substText": ""}
    return {**grund, **felder}


def test_findet_den_unterrichtstext_zur_stunde():
    infos = infos_aus_wochendaten(_antwort([_periode(lessonText="Klausur Teil 2")]), 42)
    schluessel = (datetime.date(2026, 9, 16), datetime.time(19, 25))
    assert infos[schluessel].text == "Klausur Teil 2"


def test_fasst_die_verschiedenen_textfelder_zusammen():
    """WebUntis verteilt Anmerkungen auf mehrere Felder — der Leser will alle."""
    infos = infos_aus_wochendaten(_antwort([_periode(
        lessonText="Bitte Laptop mitbringen", substText="Raumwechsel")]), 42)
    text = infos[(datetime.date(2026, 9, 16), datetime.time(19, 25))].text
    assert "Bitte Laptop mitbringen" in text and "Raumwechsel" in text


def test_nennt_denselben_text_nur_einmal():
    """Oft steht derselbe Satz in mehreren Feldern — doppelt liest sich schlecht."""
    infos = infos_aus_wochendaten(_antwort([_periode(
        lessonText="Einschulung", periodText="Einschulung", substText="Einschulung")]), 42)
    assert infos[(datetime.date(2026, 9, 16), datetime.time(19, 25))].text == "Einschulung"


def test_merkt_sich_welche_stunde_eine_konferenz_hat():
    infos = infos_aus_wochendaten(_antwort([_periode(
        videoCall={"active": True, "videoCallUrl": "-1228725804"})]), 42)
    assert infos[(datetime.date(2026, 9, 16), datetime.time(19, 25))].hat_konferenz is True


def test_ohne_konferenz_bleibt_die_markierung_aus():
    infos = infos_aus_wochendaten(_antwort([_periode()]), 42)
    assert infos[(datetime.date(2026, 9, 16), datetime.time(19, 25))].hat_konferenz is False


def test_haelt_start_und_ende_fuer_den_detailabruf_fest():
    """Der Detailabruf adressiert die Stunde ueber ihr Zeitfenster, nicht ueber die ID."""
    info = infos_aus_wochendaten(_antwort([_periode()]), 42)[
        (datetime.date(2026, 9, 16), datetime.time(19, 25))]
    assert info.start == datetime.datetime(2026, 9, 16, 19, 25)
    assert info.ende == datetime.datetime(2026, 9, 16, 20, 10)


def test_ignoriert_perioden_einer_fremden_klasse():
    infos = infos_aus_wochendaten(_antwort([_periode(lessonText="fremd")], class_id=99), 42)
    assert infos == {}


def test_vertraegt_eine_leere_antwort():
    assert infos_aus_wochendaten({}, 42) == {}


# --- Detailabruf --------------------------------------------------------------

def test_liest_den_konferenzlink_aus_der_detailantwort():
    link = konferenz_aus_detail(
        {"videoCall": {"isActive": True, "videoCallUrl": "https://teams.microsoft.com/l/x"}})
    assert link == "https://teams.microsoft.com/l/x"


def test_abgeschaltete_konferenz_liefert_keinen_link():
    assert konferenz_aus_detail(
        {"videoCall": {"isActive": False, "videoCallUrl": "https://teams.microsoft.com/l/x"}}) == ""


def test_platzhalter_statt_adresse_liefert_keinen_link():
    """In der Wochenuebersicht steht statt der Adresse eine Referenz — die nuetzt nichts."""
    assert konferenz_aus_detail({"videoCall": {"isActive": True, "videoCallUrl": "0"}}) == ""


def test_detailantwort_ohne_konferenz_liefert_keinen_link():
    assert konferenz_aus_detail({"lessonId": 5}) == ""


def test_verwirft_adressen_die_kein_web_link_sind():
    """Der Wert kommt von einem fremden Server und landet als Link auf der
    Seite. Alles ausser http/https koennte im Browser des Nutzers etwas
    ausfuehren, statt eine Konferenz zu oeffnen."""
    for adresse in ("javascript:alert(1)", "data:text/html,<script>x</script>",
                    "file:///etc/passwd", "  javascript:alert(1)"):
        assert konferenz_aus_detail(
            {"videoCall": {"isActive": True, "videoCallUrl": adresse}}) == "", adresse


def test_laesst_gewoehnliche_web_adressen_durch():
    for adresse in ("https://teams.microsoft.com/l/x", "http://intern.example/raum"):
        assert konferenz_aus_detail(
            {"videoCall": {"isActive": True, "videoCallUrl": adresse}}) == adresse


# --- Abruf: Wochen sammeln, Detail nur wo noetig ------------------------------

class FakeSitzung:
    """Steht fuer die angemeldete Verbindung zur Weboberflaeche."""

    def __init__(self, wochen=None, details=None, detail_fehler=False):
        self.wochen = wochen or {}
        self.details = details or {}
        self.detail_fehler = detail_fehler
        self.abgefragte_wochen = []
        self.abgefragte_details = []
        self.abgemeldet = False

    def wochendaten(self, untis_class_id, datum):
        self.abgefragte_wochen.append(datum)
        return self.wochen.get(datum, _antwort([], untis_class_id))

    def detail(self, untis_class_id, start, ende):
        self.abgefragte_details.append(start)
        if self.detail_fehler:
            raise RuntimeError("Detailabruf fehlgeschlagen")
        return self.details.get(start, {})

    def abmelden(self):
        self.abgemeldet = True


def _hole(sitzung, start, ende, class_id=42):
    from app.webuntis_web import hole_zusatzinfos
    return hole_zusatzinfos({}, class_id, start, ende,
                            sitzung_factory=lambda zugang: sitzung)


def test_fragt_jede_angefangene_woche_genau_einmal_ab():
    """Ein Abruf je Woche statt einer je Stunde — sonst trifft die Schule viel Last."""
    sitzung = FakeSitzung()
    _hole(sitzung, datetime.date(2026, 9, 16), datetime.date(2026, 10, 6))
    # 16.09. ist ein Mittwoch, 06.10. ein Dienstag — das sind vier
    # Kalenderwochen. Stichtag ist jeweils der Montag, damit keine Woche
    # doppelt abgefragt wird und keine hinten herausfaellt.
    assert len(sitzung.abgefragte_wochen) == 4
    assert sitzung.abgefragte_wochen[0] == datetime.date(2026, 9, 14)
    assert sitzung.abgefragte_wochen[-1] == datetime.date(2026, 10, 5)


def test_ruft_das_detail_nur_fuer_stunden_mit_konferenz_ab():
    sitzung = FakeSitzung(wochen={datetime.date(2026, 9, 14): _antwort([
        _periode(id=1, startTime=1925),
        _periode(id=2, startTime=2015, videoCall={"active": True, "videoCallUrl": "-77"}),
    ])})
    _hole(sitzung, datetime.date(2026, 9, 16), datetime.date(2026, 9, 18))
    assert sitzung.abgefragte_details == [datetime.datetime(2026, 9, 16, 20, 15)]


def test_traegt_den_konferenzlink_bei_der_richtigen_stunde_ein():
    beginn = datetime.datetime(2026, 9, 16, 20, 15)
    sitzung = FakeSitzung(
        wochen={datetime.date(2026, 9, 14): _antwort([
            _periode(startTime=2015, videoCall={"active": True, "videoCallUrl": "-77"})])},
        details={beginn: {"videoCall": {"isActive": True,
                                        "videoCallUrl": "https://teams.microsoft.com/l/x"}}})
    infos = _hole(sitzung, datetime.date(2026, 9, 16), datetime.date(2026, 9, 18))
    assert infos[(datetime.date(2026, 9, 16), datetime.time(20, 15))].video_url == \
        "https://teams.microsoft.com/l/x"


def test_ein_gescheiterter_detailabruf_kostet_nicht_die_uebrigen_infos():
    """Der Text der Stunde ist auch ohne Link etwas wert."""
    sitzung = FakeSitzung(
        wochen={datetime.date(2026, 9, 14): _antwort([_periode(
            startTime=2015, lessonText="Fernunterricht",
            videoCall={"active": True, "videoCallUrl": "-77"})])},
        detail_fehler=True)
    infos = _hole(sitzung, datetime.date(2026, 9, 16), datetime.date(2026, 9, 18))
    eintrag = infos[(datetime.date(2026, 9, 16), datetime.time(20, 15))]
    assert eintrag.text == "Fernunterricht" and eintrag.video_url == ""


def test_meldet_sich_am_ende_wieder_ab():
    sitzung = FakeSitzung()
    _hole(sitzung, datetime.date(2026, 9, 16), datetime.date(2026, 9, 18))
    assert sitzung.abgemeldet is True


# --- Der Umschlag der Detailantwort -------------------------------------------

def test_packt_den_umschlag_der_detailantwort_aus():
    """Der Server antwortet nicht mit der Stunde selbst, sondern mit einer
    Liste unter "calendarEntries". Gemessen am echten Server: ohne Auspacken
    kommt nie eine Adresse an, obwohl eine hinterlegt ist."""
    assert konferenz_aus_detail({"calendarEntries": [
        {"videoCall": {"isActive": True,
                       "videoCallUrl": "https://teams.microsoft.com/l/x"}}]}) == \
        "https://teams.microsoft.com/l/x"


def test_findet_die_adresse_auch_wenn_sie_nicht_im_ersten_eintrag_steht():
    assert konferenz_aus_detail({"calendarEntries": [
        {"lessonId": 1},
        {"videoCall": {"isActive": True,
                       "videoCallUrl": "https://teams.microsoft.com/l/y"}}]}) == \
        "https://teams.microsoft.com/l/y"


def test_leerer_umschlag_liefert_keinen_link():
    assert konferenz_aus_detail({"calendarEntries": []}) == ""
