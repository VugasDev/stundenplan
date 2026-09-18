"""Zugriff auf die API hinter der WebUntis-Weboberflaeche.

Die `webuntis`-Bibliothek spricht die alte JSON-RPC-Schnittstelle. Die gibt
Unterrichtstexte und Videokonferenzen gar nicht erst heraus — gemessen ueber
drei Klassen und acht Wochen kam kein einziges Textfeld an. Die Weboberflaeche
selbst benutzt zwei andere Wege, und nur die fuehren zum Ziel:

* Die Wochenuebersicht liefert fuer eine ganze Woche auf einmal alle
  Textfelder und die Markierung, ob eine Videokonferenz hinterlegt ist.
* Die Adresse der Konferenz haelt WebUntis zurueck — in der Wochenuebersicht
  steht dort nur eine Referenz ("0", "-1228725804"). Erst der Detailabruf
  einer einzelnen Stunde nennt die echte URL.

Deshalb die Arbeitsteilung: die Woche in einem Aufruf, der teure Detailabruf
nur fuer die wenigen Stunden mit Konferenz. Ueber drei Wochen und drei Klassen
waren das zuletzt zwei Stunden — statt rund 300 Abrufen je Lauf.
"""
from __future__ import annotations

import datetime
import http.cookiejar
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

# In diesen Feldern verteilt WebUntis die Anmerkungen zu einer Stunde.
TEXTFELDER = ("lessonText", "periodText", "periodInfo", "substText")

# Statt der Adresse steht in der Wochenuebersicht diese Referenz.
KEIN_LINK = "0"

# Die Adresse stammt von einem fremden Server und wird auf unserer Seite zum
# anklickbaren Link. Nur gewoehnliche Web-Adressen sind zulaessig — ein
# "javascript:"- oder "data:"-Wert wuerde im Browser des Nutzers ausgefuehrt.
ERLAUBTE_SCHEMATA = ("http://", "https://")


@dataclass
class Zusatz:
    """Was ueber die Kerndaten einer Stunde hinaus bekannt ist."""
    text: str = ""
    hat_konferenz: bool = False
    video_url: str = ""
    start: datetime.datetime | None = None
    ende: datetime.datetime | None = None


def _zeitpunkt(datum: int, uhrzeit: int) -> datetime.datetime:
    """WebUntis zaehlt Datum als 20260916 und Uhrzeit als 1925."""
    return datetime.datetime(datum // 10000, datum // 100 % 100, datum % 100,
                             uhrzeit // 100, uhrzeit % 100)


def _zusammengefasst(periode: dict) -> str:
    """Alle Anmerkungen der Stunde, jede nur einmal.

    Derselbe Satz steht oft in mehreren Feldern gleichzeitig — bei einer
    Einschulung etwa in lessonText, periodText und substText.
    """
    teile: list[str] = []
    for feld in TEXTFELDER:
        wert = (periode.get(feld) or "").strip()
        if wert and wert not in teile:
            teile.append(wert)
    return " · ".join(teile)


def infos_aus_wochendaten(antwort: dict, untis_class_id: int
                          ) -> dict[tuple[datetime.date, datetime.time], Zusatz]:
    """Zusatzinfos einer Woche, aufgeschluesselt nach Tag und Beginn.

    Tag und Beginn sind der Schluessel, weil die Periodennummern der
    Weboberflaeche nicht zu denen der JSON-RPC-Schnittstelle passen muessen.
    """
    perioden = (antwort.get("data", {}).get("result", {}).get("data", {})
                .get("elementPeriods", {}).get(str(untis_class_id), []))
    infos: dict[tuple[datetime.date, datetime.time], Zusatz] = {}
    for periode in perioden:
        try:
            start = _zeitpunkt(periode["date"], periode["startTime"])
            ende = _zeitpunkt(periode["date"], periode["endTime"])
        except (KeyError, TypeError, ValueError):
            continue
        infos[(start.date(), start.time())] = Zusatz(
            text=_zusammengefasst(periode),
            hat_konferenz=bool((periode.get("videoCall") or {}).get("active")),
            start=start, ende=ende,
        )
    return infos


def _adresse(eintrag: dict) -> str:
    konferenz = eintrag.get("videoCall") or {}
    adresse = (konferenz.get("videoCallUrl") or "").strip()
    if not konferenz.get("isActive") or adresse == KEIN_LINK:
        return ""
    if not adresse.lower().startswith(ERLAUBTE_SCHEMATA):
        return ""
    return adresse


def konferenz_aus_detail(antwort: dict) -> str:
    """Adresse der Videokonferenz aus dem Detailabruf einer Stunde.

    Der Server antwortet mit einem Umschlag: die eigentlichen Angaben stehen
    in einer Liste unter "calendarEntries". Eine Stunde kann darin mehrfach
    auftauchen, und nicht jeder Eintrag traegt die Konferenz — deshalb wird
    der erste mit einer brauchbaren Adresse genommen.
    """
    eintraege = antwort.get("calendarEntries")
    if not isinstance(eintraege, list):
        return _adresse(antwort)
    for eintrag in eintraege:
        if isinstance(eintrag, dict):
            adresse = _adresse(eintrag)
            if adresse:
                return adresse
    return ""


class WebSitzung:
    """Angemeldete Verbindung zur Weboberflaeche.

    Die Anmeldung laeuft ueber dieselbe JSON-RPC-Methode wie beim
    Bibliotheksweg; entscheidend ist das Sitzungs-Cookie, das dabei gesetzt
    wird. Die neueren REST-Pfade verlangen zusaetzlich ein Zugriffstoken, das
    man sich mit diesem Cookie abholt.
    """

    ANMELDUNG = "/WebUntis/jsonrpc.do"
    TOKEN = "/WebUntis/api/token/new"
    WOCHE = "/WebUntis/api/public/timetable/weekly/data"
    DETAIL = "/WebUntis/api/rest/view/v2/calendar-entry/detail"
    ZEITLIMIT = 30

    def __init__(self, zugang: dict):
        self.basis = f"https://{zugang['server_url']}"
        self.school = zugang["school"]
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self._kopf = {"Accept": "*/*", "User-Agent": "stundenplan-app"}
        self._anmelden(zugang)

    def _anmelden(self, zugang: dict) -> None:
        anfrage = json.dumps({
            "id": "stundenplan", "jsonrpc": "2.0", "method": "authenticate",
            "params": {"user": zugang["username"], "password": zugang["password"],
                       "client": "stundenplan-app"},
        }).encode()
        adresse = f"{self.basis}{self.ANMELDUNG}?school={urllib.parse.quote(self.school)}"
        antwort = json.loads(self._opener.open(urllib.request.Request(
            adresse, data=anfrage,
            headers={**self._kopf, "Content-Type": "application/json"}),
            timeout=self.ZEITLIMIT).read())
        if "error" in antwort:
            raise RuntimeError(f"Anmeldung abgelehnt: "
                               f"{antwort['error'].get('message', 'ohne Angabe')}")
        token = self._lesen(self.TOKEN, roh=True).strip()
        self._kopf["Authorization"] = f"Bearer {token}"

    def _lesen(self, pfad: str, roh: bool = False):
        antwort = self._opener.open(
            urllib.request.Request(self.basis + pfad, headers=self._kopf),
            timeout=self.ZEITLIMIT).read()
        return antwort.decode("utf-8", "replace") if roh else json.loads(antwort)

    def wochendaten(self, untis_class_id: int, datum: datetime.date) -> dict:
        return self._lesen(f"{self.WOCHE}?elementType=1&elementId={untis_class_id}"
                           f"&date={datum.isoformat()}&formatId=1")

    def detail(self, untis_class_id: int, start: datetime.datetime,
               ende: datetime.datetime) -> dict:
        # elementType als Zahl, nicht als Name — der Server erwartet hier ein Long.
        return self._lesen(
            f"{self.DETAIL}?elementId={untis_class_id}&elementType=1"
            f"&startDateTime={start.strftime('%Y-%m-%dT%H:%M')}"
            f"&endDateTime={ende.strftime('%Y-%m-%dT%H:%M')}&homeworkOption=DUE")

    def abmelden(self) -> None:
        try:
            self._lesen("/WebUntis/api/logout", roh=True)
        except Exception:
            # Die Sitzung laeuft ohnehin von selbst ab; ein misslungenes
            # Abmelden darf den Abruf nicht nachtraeglich scheitern lassen.
            pass


def _wochenanfaenge(start: datetime.date, ende: datetime.date) -> list[datetime.date]:
    """Je ein Stichtag pro angefangener Kalenderwoche des Zeitraums.

    Der Wochenabruf liefert immer die volle Kalenderwoche des uebergebenen
    Tages. Deshalb wird auf Montag normalisiert: sonst zaehlt man in
    Siebenerschritten ab einem beliebigen Wochentag, fragt dieselbe Woche
    womoeglich zweimal ab und laesst die letzte angefangene Woche aus.
    """
    tage, laufend = [], start - datetime.timedelta(days=start.weekday())
    while laufend <= ende:
        tage.append(laufend)
        laufend += datetime.timedelta(days=7)
    return tage


def hole_zusatzinfos(zugang: dict, untis_class_id: int, start: datetime.date,
                     ende: datetime.date, sitzung_factory=WebSitzung
                     ) -> dict[tuple[datetime.date, datetime.time], Zusatz]:
    """Zusatzinfos eines Zeitraums: Texte je Woche, Links nur wo noetig."""
    sitzung = sitzung_factory(zugang)
    infos: dict[tuple[datetime.date, datetime.time], Zusatz] = {}
    try:
        for stichtag in _wochenanfaenge(start, ende):
            infos.update(infos_aus_wochendaten(
                sitzung.wochendaten(untis_class_id, stichtag), untis_class_id))
        for eintrag in infos.values():
            if not eintrag.hat_konferenz:
                continue
            try:
                eintrag.video_url = konferenz_aus_detail(
                    sitzung.detail(untis_class_id, eintrag.start, eintrag.ende))
            except Exception:
                # Ohne Link bleibt der Text der Stunde trotzdem nuetzlich.
                pass
    finally:
        sitzung.abmelden()
    return infos
