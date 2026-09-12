# WebUntis-Stundenplan

Multi-User-Web-App: Klassengruppen mit gespendeten WebUntis-Zugängen (eine Person
je Klasse). Alle Mitglieder sehen den gebündelten Plan (Woche/Agenda). Ein Job
ruft halbstündlich ab — tatsächlich nur, wenn nötig.

## Setup

1. `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
2. `.env.example` nach `.env` kopieren und ausfüllen. Schlüssel erzeugen:
   - `SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`
   - `FERNET_KEY`: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
3. DB initialisieren: `flask --app app init-db`
4. Starten (Entwicklung): `flask --app app run`
5. Produktion: `deploy/stundenplan-web.service` nach `/etc/systemd/system/` kopieren
   (startet Gunicorn auf `0.0.0.0:8000`) + Reverse-Proxy davor (HTTPS).
   Die App bindet auf alle Interfaces, damit der Proxy von einem anderen
   Host aus zugreifen kann — sie gehört deshalb in ein Server-Netz, das
   nicht direkt aus dem Internet erreichbar ist.
   `SESSION_COOKIE_SECURE=true` setzen.
   Die App lädt `.env` automatisch über `python-dotenv`. Das gilt für den
   Flask-Entwicklungsserver und `python -m app.fetch`; für den Gunicorn-Prozess
   muss die Umgebung aber trotzdem vorhanden sein (z.B. eigene systemd-Unit mit
   `EnvironmentFile=/opt/stundenplan/.env`, oder vor dem Start `set -a; . .env; set +a`).
   Die mitgelieferte Unit startet **einen** Worker mit vier Threads — passend zu
   SQLite (kein paralleler Schreiber) und zum In-Memory-Rate-Limit-Store. Erst wenn
   die Worker-Zahl erhöht wird, MUSS `RATELIMIT_STORAGE_URI` auf einen gemeinsamen
   Store zeigen (z.B. `redis://localhost:6379`), sonst zählt jeder Worker separat.

## Mail

Bestätigungslinks und Passwort-Reset brauchen einen erreichbaren SMTP-Server —
ohne den kann sich niemand registrieren oder aussperren lassen. Konfiguriert wird
er über `MAIL_*` in der `.env` — inklusive der Absenderadresse.

Fällt der Versand aus, wird der Fehler geloggt statt den Request zu killen: die
Registrierung bleibt bestehen und die Bestätigungsmail lässt sich über
"Keine Bestätigungsmail bekommen?" auf der Login-Seite erneut anfordern.

## Passwort vergessen

`/forgot-password` verschickt einen Link (1 Stunde gültig, 5 Anfragen pro Stunde
und IP). Der Token ist an den aktuellen Passwort-Hash gebunden — nach dem
Zurücksetzen ist er automatisch verbraucht. Wer den Link benutzt, gilt danach als
E-Mail-bestätigt. Ob eine Adresse registriert ist, verrät das Formular nicht.

## Zeitzone

Die App rechnet Uhrzeiten in `TIMEZONE` (Standard `Europe/Berlin`), nicht in der
Zeit des Servers — LXCs laufen üblicherweise auf UTC, und die "Jetzt"-Ansicht
läge sonst im Sommer zwei Stunden zurück. Die Jetzt-Linie im Plan nutzt die Uhr
des Browsers und ist davon unabhängig.

## Abruf

Der Plan einer Klasse wird **einmal** geholt und von allen Mitgliedern gelesen.
Der Timer weckt halbstündlich, tatsächlich abgerufen wird eine Klasse aber nur,
wenn ihr letzter Abruf mindestens 90 Minuten her ist und die Ortszeit zwischen
6:00 und 22:00 liegt.

"Jetzt aktualisieren" ist je Klasse auf einen Abruf alle 15 Minuten begrenzt;
innerhalb dieser Frist wird der gespeicherte Stand angezeigt, mit Angabe seines
Alters.

Es wird nur gespeichert, was im Abruffenster liegt (21 Tage) — vergangene Stunden
werden bei jedem Abruf gelöscht.

## Upgrade einer bestehenden Installation (kontobasiert → klassenbasiert)

Der Umstieg ändert das Datenmodell (`Lesson` hängt jetzt an der Klasse statt
am Nutzerkonto). Für ein laufendes System in dieser Reihenfolge vorgehen:

1. **Datenbank sichern.** Bei SQLite reicht eine Kopie der `.db`-Datei, z.B.
   `cp stundenplan.db stundenplan.db.bak`.
2. **Code einspielen** (neuen Branch/Release auschecken, Abhängigkeiten
   aktualisieren: `pip install -r requirements.txt`).
3. **Tests laufen lassen:** `.venv/bin/pytest` — erst danach weiter.
4. **Migration ausführen:** `flask --app app migrate-to-classes`. Der Befehl
   überführt bestehende WebUntis-Konten in Klassenquellen samt
   Mitgliedschaft und legt anschließend die Tabelle `lessons` mit dem neuen
   Schema neu an (die Stunden sind wegwerfbar, der nächste Abruf füllt sie
   binnen 90 Minuten wieder). Konten, deren Anzeigename keinem Klassennamen
   der Schule entspricht, werden gemeldet und müssen einmalig über
   „Klasse hinzufügen" in der Weboberfläche nachgeholt werden.
5. **Dienst und Timer neu starten:**
   ```
   sudo systemctl restart stundenplan-web.service
   sudo systemctl restart stundenplan-fetch.timer
   ```
6. **Erstabruf auslösen**, damit nicht bis zu 30 Minuten auf den Timer
   gewartet werden muss: `flask --app app fetch-now`.
7. **Prüfen:** `/healthz` liefert `ok`, eine Ansicht zeigt aktuelle Stunden,
   `flask --app app migrate-to-classes` erneut ausgeführt meldet keine neuen
   Zuordnungen mehr (idempotent).

**Nachbemerkung:** Die alte Tabelle `webuntis_accounts` bleibt nach der
Migration bestehen und enthält weiterhin verschlüsselte Zugangsdaten. Sie
sollte erst nach erfolgreicher Prüfung von Hand aus der Datenbank entfernt
werden (z.B. `DROP TABLE webuntis_accounts;`).

## Sicherheit

- WebUntis-Passwörter liegen Fernet-verschlüsselt in der DB; der `FERNET_KEY`
  steht nur in `.env`. **DB und Key getrennt sichern.** Key-Verlust = alle
  WebUntis-Passwörter müssen neu eingegeben werden.
- `REGISTRATION_MODE`: `open`, `invite` (+`INVITE_CODE`), `admin`. Für eine
  öffentlich erreichbare Instanz `invite` verwenden.
- Reset- und Bestätigungstoken signiert `SECRET_KEY`. Wird er ausgetauscht,
  verfallen alle offenen Links.

## Tests

`.venv/bin/pytest`

## Wann eine Klasse stillgelegt wird

Stillgelegt heißt: Der Plan dieser Klasse wird nicht mehr abgerufen. Gelöscht
wird nichts zusätzlich — die Löschfristen räumen ihn binnen drei Wochen ab, weil
nichts mehr nachkommt. Tritt jemand wieder bei, läuft der Abruf weiter.

Zwei unabhängige Gründe:

- **Verlassen.** Endet die letzte Mitgliedschaft, beginnt eine Schonfrist von
  sieben Tagen. Ein Wiedereintritt hebt sie auf.
- **Bildungsgang beendet.** Klassennamen folgen dem Schema Kürzel +
  Einschulungsjahr (eine Ziffer) + Parallelklasse, etwa `FI42` für FI, 2024,
  Parallelklasse 2. Ist die Laufzeit des Kürzels hinterlegt, endet der Abruf zum
  Schuljahresende.

Vorbelegt sind `FI` (3 Jahre) sowie `FIT`, `FET` und `FMT` (4 Jahre). Weitere
Kürzel trägt man über `KLASSENLAUFZEITEN` in der `.env` nach.

**Im Zweifel läuft eine Klasse weiter.** Ein Kürzel ohne hinterlegte Laufzeit
wird nie automatisch stillgelegt, ebenso ein Name, der dem Schema nicht folgt —
solche Namen sind häufig. Die Buchstabenzahl des Kürzels taugt bewusst nicht als
Regel: Schulen führen ein- bis dreibuchstabige Kürzel, und gleich lange Kürzel
stehen für Bildungsgänge sehr unterschiedlicher Dauer. Die Klassenliste weist
deshalb aus, wenn eine Laufzeit unbekannt ist.

## Lizenz

MIT — siehe [LICENSE](LICENSE).
