from __future__ import annotations

from flask import current_app
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, BadData

_SALT = "email-confirm"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_confirm_token(email: str) -> str:
    return _serializer().dumps(email, salt=_SALT)


def confirm_token(token: str, max_age_seconds: int = 86400) -> str | None:
    try:
        return _serializer().loads(token, salt=_SALT, max_age=max_age_seconds)
    except BadData:
        return None


def send_confirmation(email: str, confirm_url: str) -> None:
    from app.extensions import mail
    msg = Message("Stundenplan — E-Mail bestätigen", recipients=[email])
    msg.body = (
        "Hallo,\n\n"
        "bitte bestätige deine Registrierung über diesen Link:\n"
        f"{confirm_url}\n\n"
        "Der Link ist 24 Stunden gültig.\n"
    )
    mail.send(msg)
