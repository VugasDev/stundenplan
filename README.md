# WebUntis-Stundenplan

Multi-User-Web-App: jede Person hinterlegt ihre WebUntis-Zugänge und sieht
ihre Stundenpläne gebündelt (Woche/Agenda). Ein täglicher Job ruft ab.

## Setup

1. `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
2. `.env.example` nach `.env` kopieren und ausfüllen. Schlüssel erzeugen:
   - `SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`
   - `FERNET_KEY`: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
3. DB initialisieren: `flask --app app init-db`
4. Starten (Entwicklung): `flask --app app run`
5. Produktion: `deploy/stundenplan-web.service` nach `/etc/systemd/system/` kopieren
   (startet Gunicorn auf `127.0.0.1:8000`) + Caddy davor (HTTPS).
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
er über `MAIL_*` in der `.env`; Absender ist `noreply@example.org`.

Fällt der Versand aus, wird der Fehler geloggt statt den Request zu killen: die
Registrierung bleibt bestehen und die Bestätigungsmail lässt sich über
"Keine Bestätigungsmail bekommen?" auf der Login-Seite erneut anfordern.

## Passwort vergessen

`/forgot-password` verschickt einen Link (1 Stunde gültig, 5 Anfragen pro Stunde
und IP). Der Token ist an den aktuellen Passwort-Hash gebunden — nach dem
Zurücksetzen ist er automatisch verbraucht. Wer den Link benutzt, gilt danach als
E-Mail-bestätigt. Ob eine Adresse registriert ist, verrät das Formular nicht.

## Täglicher Abruf

- Dateien aus `deploy/` nach `/etc/systemd/system/` kopieren, App nach `/opt/stundenplan`.
- Der Fetch-Service läuft als dedizierter `stundenplan`-User, nicht als root:
  `sudo useradd --system --home /opt/stundenplan stundenplan` und
  `sudo chown -R stundenplan:stundenplan /opt/stundenplan`.
- `systemctl enable --now stundenplan-fetch.timer`
- Manuell: `flask --app app fetch-now` oder `python -m app.fetch`

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
