from __future__ import annotations

from flask import current_app
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, BadData

_SALT = "email-confirm"
_RESET_SALT = "password-reset"


def _serializer(secret: str | None = None) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret or current_app.config["SECRET_KEY"])


def generate_confirm_token(email: str) -> str:
    return _serializer().dumps(email, salt=_SALT)


def confirm_token(token: str, max_age_seconds: int = 86400) -> str | None:
    try:
        return _serializer().loads(token, salt=_SALT, max_age=max_age_seconds)
    except BadData:
        return None


def _reset_secret(user) -> str:
    """Bindet den Reset-Token an den aktuellen Passwort-Hash — nach einer
    Passwortänderung werden alle älteren Reset-Links dadurch ungültig."""
    return f"{current_app.config['SECRET_KEY']}:{user.password_hash}"


def generate_reset_token(user) -> str:
    return _serializer(_reset_secret(user)).dumps(user.id, salt=_RESET_SALT)


def verify_reset_token(user, token: str, max_age_seconds: int = 3600) -> bool:
    try:
        user_id = _serializer(_reset_secret(user)).loads(
            token, salt=_RESET_SALT, max_age=max_age_seconds
        )
    except BadData:
        return False
    return user_id == user.id


def _send(msg: Message) -> bool:
    """Verschickt die Mail und meldet Erfolg. Ein nicht erreichbarer SMTP-Server
    darf den Request nicht mit einem 500er beenden."""
    from app.extensions import mail
    try:
        mail.send(msg)
        return True
    except Exception:
        current_app.logger.exception("Mailversand an %s fehlgeschlagen", msg.recipients)
        return False


def send_confirmation(email: str, confirm_url: str) -> bool:
    msg = Message("Stundenplan — E-Mail bestätigen", recipients=[email])
    msg.body = (
        "Hallo,\n\n"
        "bitte bestätige deine Registrierung über diesen Link:\n"
        f"{confirm_url}\n\n"
        "Der Link ist 24 Stunden gültig.\n"
    )
    return _send(msg)


def send_password_reset(email: str, reset_url: str) -> bool:
    msg = Message("Stundenplan — Passwort zurücksetzen", recipients=[email])
    msg.body = (
        "Hallo,\n\n"
        "über diesen Link kannst du ein neues Passwort vergeben:\n"
        f"{reset_url}\n\n"
        "Der Link ist 1 Stunde gültig und verfällt, sobald du ihn benutzt hast.\n"
        "Wenn du kein neues Passwort angefordert hast, ignoriere diese Mail —\n"
        "dein bisheriges Passwort bleibt dann unverändert.\n"
    )
    return _send(msg)
