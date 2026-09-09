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
5. Produktion: hinter Gunicorn (`gunicorn "app:create_app()"`) + Caddy/nginx (HTTPS).
   `SESSION_COOKIE_SECURE=true` setzen.
   Die App lädt `.env` automatisch über `python-dotenv`. Das gilt für den
   Flask-Entwicklungsserver und `python -m app.fetch`; für den Gunicorn-Prozess
   muss die Umgebung aber trotzdem vorhanden sein (z.B. eigene systemd-Unit mit
   `EnvironmentFile=/opt/stundenplan/.env`, oder vor dem Start `set -a; . .env; set +a`).
   Bei mehreren Gunicorn-Workern MUSS `RATELIMIT_STORAGE_URI` auf einen
   gemeinsamen Backend-Store zeigen (z.B. `redis://localhost:6379`), sonst zählt
   jeder Worker die Rate-Limits separat.

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
- `REGISTRATION_MODE`: `open` (Default), `invite` (+`INVITE_CODE`), `admin`.

## Tests

`.venv/bin/pytest`
