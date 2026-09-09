"""
Proof of Concept: WebUntis-Zugaenge testen.

Nutzung:
  1. poc_accounts.example.json -> poc_accounts.json kopieren
  2. poc_accounts.json mit deinen echten Zugaengen ausfuellen
  3. python poc.py

Das Skript loggt sich pro Zugang ein, holt den persoenlichen
Stundenplan der naechsten 7 Tage und zeigt eine Zusammenfassung.
Passwoerter werden NICHT ausgegeben.

So findest du server/school: oeffne WebUntis im Browser, die URL
sieht aus wie  https://SERVER.webuntis.com/WebUntis/?school=SCHOOL#/...
-> SERVER = z.B. "xyz.webuntis.com", SCHOOL = Wert hinter ?school=
"""

import datetime
import json
import sys
from pathlib import Path

import webuntis

ACCOUNTS_FILE = Path(__file__).parent / "poc_accounts.json"


def test_account(acc: dict) -> None:
    label = acc.get("label", acc.get("username", "?"))
    print(f"\n=== Zugang: {label} ({acc.get('school')}) ===")
    try:
        session = webuntis.Session(
            username=acc["username"],
            password=acc["password"],
            server=acc["server"],
            school=acc["school"],
            useragent="stundenplan-poc",
        )
        session.login()
    except Exception as e:
        print(f"  ❌ Login fehlgeschlagen: {type(e).__name__}: {e}")
        return

    print("  ✅ Login erfolgreich")

    try:
        today = datetime.date.today()
        end = today + datetime.timedelta(days=7)
        timetable = session.my_timetable(start=today, end=end)
        lessons = sorted(timetable, key=lambda p: p.start)
        print(f"  📅 {len(lessons)} Stunden in den naechsten 7 Tagen gefunden")
        for p in lessons[:8]:
            subjects = ", ".join(s.name for s in p.subjects) or "?"
            rooms = ", ".join(r.name for r in p.rooms) or "-"
            teachers = ", ".join(t.name for t in p.teachers) or "-"
            code = p.code or "normal"
            print(
                f"    {p.start:%a %d.%m %H:%M}-{p.end:%H:%M}  "
                f"{subjects:<12} Raum {rooms:<6} Lehrer {teachers:<8} [{code}]"
            )
        if len(lessons) > 8:
            print(f"    ... und {len(lessons) - 8} weitere")
    except Exception as e:
        print(f"  ⚠️  Stundenplan-Abruf fehlgeschlagen: {type(e).__name__}: {e}")
    finally:
        try:
            session.logout()
        except Exception:
            pass


def main() -> None:
    if not ACCOUNTS_FILE.exists():
        print(
            f"Datei {ACCOUNTS_FILE.name} fehlt.\n"
            f"Kopiere poc_accounts.example.json nach poc_accounts.json "
            f"und trage deine Zugaenge ein."
        )
        sys.exit(1)

    accounts = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    print(f"Teste {len(accounts)} Zugang/Zugaenge ...")
    for acc in accounts:
        test_account(acc)
    print("\nFertig.")


if __name__ == "__main__":
    main()
