"""Einmalige Pruefung der Klassenzugehoerigkeit.

Das Passwort wird genau einmal gegen die Schule verwendet und danach verworfen —
gespeichert wird es nur, wenn die Person ausdruecklich spendet (siehe app/classes).
"""
from __future__ import annotations

from app.webuntis_client import fetch_classes


def verify_and_list_classes(server_url: str, school: str, username: str,
                            password: str, lister=fetch_classes):
    """Prueft die Zugangsdaten und liefert die Klassen der Schule.

    Rueckgabe: (erfolg, klassen, fehlermeldung). Die Fehlermeldung ist fuer die
    Anzeige gedacht und enthaelt bewusst nie die uebergebenen Zugangsdaten.
    """
    credentials = {"server_url": server_url, "school": school,
                   "username": username, "password": password}
    try:
        return True, list(lister(credentials)), ""
    except Exception:
        # Die Originalmeldung koennte die Zugangsdaten enthalten — nicht durchreichen.
        return False, [], ("Anmeldung bei WebUntis fehlgeschlagen. Bitte Server, "
                           "Schule, Benutzername und Passwort prüfen.")
