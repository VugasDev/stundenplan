import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    FERNET_KEY = os.environ.get("FERNET_KEY", "").encode()
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///stundenplan.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REGISTRATION_MODE = os.environ.get("REGISTRATION_MODE", "open")
    INVITE_CODE = os.environ.get("INVITE_CODE", "")

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "25"))
    MAIL_USE_TLS = _bool("MAIL_USE_TLS", False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME") or None
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD") or None
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@example.org")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)

    FETCH_WINDOW_DAYS = 21

    # Prozessweiter Socket-Timeout: verhindert, dass ein haengender SMTP- oder
    # WebUntis-Server einen Gunicorn-Worker dauerhaft blockiert.
    NETWORK_TIMEOUT = int(os.environ.get("NETWORK_TIMEOUT", "20"))

    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-only-not-a-real-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"  # in-memory
    WTF_CSRF_ENABLED = False
    FERNET_KEY = b"dGVzdC1rZXktdGVzdC1rZXktdGVzdC1rZXktMzI9MDA="  # 32-byte urlsafe b64
    RATELIMIT_ENABLED = False
    MAIL_SUPPRESS_SEND = True
