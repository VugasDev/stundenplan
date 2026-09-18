"""Verwaltungsbereich: Einladungscodes, Klassen, Konten.

Alles hier setzt `is_admin` voraus. Fehlt das Recht, antwortet der Bereich mit
404 statt 403 — wer nicht hinein darf, soll nicht einmal erfahren, dass es ihn
gibt. Das Recht selbst wird nur ueber die Kommandozeile vergeben.
"""
from functools import wraps

import datetime
import secrets
import string

from flask import (Blueprint, render_template, abort, request, redirect,
                   url_for, flash, current_app)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import InviteCode, User, SchoolClass, Membership, Lesson
from app import mailer
from app.zeit import local_today

# Ohne leicht verwechselbare Zeichen (0/O, 1/I/l) — Codes werden abgetippt.
_ZEICHEN = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def neuer_code(laenge: int = 10) -> str:
    return "".join(secrets.choice(_ZEICHEN) for _ in range(laenge))


def _ganzzahl(wert):
    """Leeres Feld heisst 'kein Limit', nicht 'null Einloesungen'."""
    try:
        zahl = int((wert or "").strip())
    except ValueError:
        return None
    return zahl if zahl > 0 else None


def _datum(wert):
    try:
        return datetime.date.fromisoformat((wert or "").strip())
    except ValueError:
        return None

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    """Wie login_required, nur strenger — und ohne den Bereich zu verraten."""
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(404)
        return f(*args, **kwargs)
    return wrapper


@bp.route("/", strict_slashes=False)
@admin_required
def index():
    """Einstieg.

    strict_slashes=False mit Bedacht: Sonst beantwortet Flask /admin mit einer
    308-Weiterleitung auf /admin/ — und zwar bevor die Rechte geprueft werden.
    Ein Fremder erfuehre damit am Statuscode, dass es den Bereich gibt, obwohl
    er 404 sehen soll.
    """
    return render_template("admin/index.html")


@bp.route("/codes", methods=["GET", "POST"])
@admin_required
def codes():
    if request.method == "POST":
        note = (request.form.get("note") or "").strip()[:120]
        max_uses = _ganzzahl(request.form.get("max_uses"))
        expires_at = _datum(request.form.get("expires_at"))
        code = InviteCode(code=neuer_code(), note=note,
                          max_uses=max_uses, expires_at=expires_at)
        db.session.add(code)
        db.session.commit()
        flash(f"Code {code.code} erstellt.", "success")
        return redirect(url_for("admin.codes"))

    heute = local_today(current_app.config["TIMEZONE"])
    alle = (db.session.query(InviteCode)
            .order_by(InviteCode.revoked, InviteCode.created_at.desc()).all())
    return render_template("admin/codes.html", codes=alle, heute=heute)


@bp.post("/codes/<int:code_id>/revoke")
@admin_required
def code_revoke(code_id):
    code = db.session.get(InviteCode, code_id)
    if code is None:
        abort(404)
    code.revoked = True
    db.session.commit()
    flash(f"Code {code.code} zurückgezogen.", "success")
    return redirect(url_for("admin.codes"))


@bp.get("/klassen")
@admin_required
def klassen():
    """Alle verwalteten Klassen — auch die, in denen der Admin nicht Mitglied ist."""
    zeilen = []
    for k in db.session.query(SchoolClass).order_by(SchoolClass.school,
                                                    SchoolClass.name).all():
        zeilen.append({
            "klasse": k,
            "mitglieder": db.session.query(Membership).filter_by(class_id=k.id).count(),
            "stunden": db.session.query(Lesson).filter_by(class_id=k.id).count(),
        })
    return render_template("admin/klassen.html", zeilen=zeilen)


@bp.post("/klassen/<int:class_id>/delete")
@admin_required
def klasse_loeschen(class_id):
    school_class = db.session.get(SchoolClass, class_id)
    if school_class is None:
        abort(404)
    name = school_class.name
    # Mitgliedschaften und Stunden haengen per cascade daran und gehen mit.
    db.session.delete(school_class)
    db.session.commit()
    flash(f"Klasse {name} gelöscht — samt Mitgliedschaften und Stunden.", "success")
    return redirect(url_for("admin.klassen"))


@bp.get("/konten")
@admin_required
def konten():
    zeilen = []
    for u in db.session.query(User).order_by(User.created_at.desc()).all():
        zeilen.append({
            "user": u,
            "klassen": db.session.query(Membership).filter_by(user_id=u.id).count(),
        })
    return render_template("admin/konten.html", zeilen=zeilen)


@bp.post("/konten/<int:user_id>/reset")
@admin_required
def konto_reset(user_id):
    """Stoesst einen Passwort-Ruecksetzlink an.

    Der Link geht ausschliesslich an das hinterlegte Postfach — die Verwaltung
    bekommt ihn nicht zu sehen und kann damit kein fremdes Konto uebernehmen.
    """
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    token = mailer.generate_reset_token(user)
    reset_url = url_for("auth.reset_password", user_id=user.id, token=token,
                        _external=True)
    if mailer.send_password_reset(user.email, reset_url):
        flash(f"Rücksetzlink an {user.email} verschickt.", "success")
    else:
        flash(f"Mail an {user.email} konnte nicht versendet werden.", "error")
    return redirect(url_for("admin.konten"))
