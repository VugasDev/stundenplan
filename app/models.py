import datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from flask_login import UserMixin

from app.extensions import db

_hasher = PasswordHasher()


def utcnow() -> datetime.datetime:
    """Naiver UTC-Zeitstempel (ersetzt das in Python 3.12 deprecated datetime.utcnow)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    confirmed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    # Wird ausschliesslich ueber die Kommandozeile gesetzt (flask make-admin).
    # Wer Serverzugang hat, ist ohnehin maechtiger als jeder Admin im Browser.
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    memberships = db.relationship(
        "Membership", back_populates="user", cascade="all, delete-orphan",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = _hasher.hash(password)

    def check_password(self, password: str) -> bool:
        try:
            return _hasher.verify(self.password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False


class SchoolClass(db.Model):
    """Eine Klasse als Abrufquelle — eine Zeile je Klasse, nicht je Person."""
    __tablename__ = "school_classes"
    id = db.Column(db.Integer, primary_key=True)
    server_url = db.Column(db.String(255), nullable=False)
    school = db.Column(db.String(255), nullable=False)
    untis_class_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # Zugangsdaten des Spenders; leer, solange niemand gespendet hat.
    username = db.Column(db.String(255), nullable=True)
    password_encrypted = db.Column(db.Text, nullable=True)
    donor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    last_fetch_at = db.Column(db.DateTime, nullable=True)
    last_fetch_status = db.Column(db.String(255), nullable=True)

    # Wann die letzte Mitgliedschaft endete. Nach der Schonfrist wird die Klasse
    # stillgelegt; ein Wiedereintritt leert das Feld und hebt die Frist auf.
    members_left_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("server_url", "school", "untis_class_id",
                            name="uq_klasse_je_schule"),
    )

    lessons = db.relationship("Lesson", back_populates="school_class",
                              cascade="all, delete-orphan")
    memberships = db.relationship("Membership", back_populates="school_class",
                                  cascade="all, delete-orphan")

    @property
    def has_source(self) -> bool:
        """Kann diese Klasse abgerufen werden?"""
        return bool(self.password_encrypted)


class InviteCode(db.Model):
    """Einladungscode fuer die Registrierung.

    Ein Code gilt fuer eine ganze Gruppe: beliebig oft einloesbar, sofern kein
    Limit gesetzt ist, und bis zu einem optionalen Ablaufdatum. Zurueckziehen
    geht jederzeit — geloescht wird nichts, damit nachvollziehbar bleibt, wie
    oft ein Code benutzt wurde.
    """
    __tablename__ = "invite_codes"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    note = db.Column(db.String(120), nullable=False, default="")
    max_uses = db.Column(db.Integer, nullable=True)      # None = unbegrenzt
    uses = db.Column(db.Integer, nullable=False, default=0)
    expires_at = db.Column(db.Date, nullable=True)       # None = kein Ablauf
    revoked = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def is_valid(self, today: datetime.date) -> bool:
        """Darf dieser Code gerade eingeloest werden?"""
        if self.revoked:
            return False
        if self.max_uses is not None and self.uses >= self.max_uses:
            return False
        # Am Ablauftag selbst gilt er noch.
        if self.expires_at is not None and today > self.expires_at:
            return False
        return True

    @property
    def nutzung(self) -> str:
        """Benutzt im Verhaeltnis zum Limit — fuer die Anzeige."""
        if self.max_uses is None:
            return f"{self.uses} (unbegrenzt)"
        return f"{self.uses} / {self.max_uses}"


class Membership(db.Model):
    """Belegte Zugehoerigkeit einer Person zu einer Klasse."""
    __tablename__ = "memberships"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey("school_classes.id"),
                         nullable=False, index=True)
    verified_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="memberships")
    school_class = db.relationship("SchoolClass", back_populates="memberships")

    __table_args__ = (
        db.UniqueConstraint("user_id", "class_id", name="uq_eine_mitgliedschaft"),
    )


class Lesson(db.Model):
    __tablename__ = "lessons"
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("school_classes.id"),
                         nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    room = db.Column(db.String(100), nullable=False, default="")
    teacher = db.Column(db.String(255), nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="normal")
    note = db.Column(db.String(255), nullable=False, default="")

    school_class = db.relationship("SchoolClass", back_populates="lessons")
