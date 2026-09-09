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

## Täglicher Abruf

- Dateien aus `deploy/` nach `/etc/systemd/system/` kopieren, App nach `/opt/stundenplan`.
- `systemctl enable --now stundenplan-fetch.timer`
- Manuell: `flask --app app fetch-now` oder `python -m app.fetch`

## Sicherheit

- WebUntis-Passwörter liegen Fernet-verschlüsselt in der DB; der `FERNET_KEY`
  steht nur in `.env`. **DB und Key getrennt sichern.** Key-Verlust = alle
  WebUntis-Passwörter müssen neu eingegeben werden.
- `REGISTRATION_MODE`: `open` (Default), `invite` (+`INVITE_CODE`), `admin`.

## Tests

`.venv/bin/pytest`
