from flask import (Blueprint, render_template, redirect, url_for, flash, request,
                   current_app)
from flask_login import login_user, logout_user, login_required

from app.extensions import db, limiter
from app.models import User
from app.auth.forms import RegisterForm, LoginForm
from app import mailer

bp = Blueprint("auth", __name__)


def _registration_allowed(form) -> tuple[bool, str]:
    mode = current_app.config["REGISTRATION_MODE"]
    if mode == "admin":
        return False, "Registrierung ist deaktiviert. Bitte wende dich an den Admin."
    if mode == "invite":
        if form.invite_code.data != current_app.config["INVITE_CODE"] or not current_app.config["INVITE_CODE"]:
            return False, "Ungültiger Einladungscode."
    return True, ""


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        allowed, msg = _registration_allowed(form)
        if not allowed:
            flash(msg, "error")
            return render_template("auth/register.html", form=form)
        if db.session.query(User).filter_by(email=form.email.data).first():
            flash("Diese E-Mail ist bereits registriert.", "error")
            return render_template("auth/register.html", form=form)
        user = User(email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        token = mailer.generate_confirm_token(user.email)
        confirm_url = url_for("auth.confirm", token=token, _external=True)
        mailer.send_confirmation(user.email, confirm_url)
        flash("Fast geschafft! Bitte bestätige den Link in deiner E-Mail.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per hour")
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(User).filter_by(email=form.email.data).first()
        if not user or not user.check_password(form.password.data):
            flash("E-Mail oder Passwort falsch.", "error")
            return render_template("auth/login.html", form=form)
        if not user.confirmed:
            flash("Bitte bestätige zuerst deine E-Mail-Adresse.", "error")
            return render_template("auth/login.html", form=form)
        login_user(user)
        # Literaler Pfad statt url_for: entkoppelt Auth vom timetable-Endpoint,
        # der erst in Task 9 entsteht. "/" gehört ab Task 9 timetable.index.
        return redirect("/")
    return render_template("auth/login.html", form=form)


@bp.route("/confirm/<token>")
def confirm(token):
    email = mailer.confirm_token(token)
    if not email:
        flash("Bestätigungslink ungültig oder abgelaufen.", "error")
        return redirect(url_for("auth.login"))
    user = db.session.query(User).filter_by(email=email).first()
    if user and not user.confirmed:
        user.confirmed = True
        db.session.commit()
        flash("E-Mail bestätigt — du kannst dich jetzt anmelden.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Abgemeldet.", "success")
    return redirect(url_for("auth.login"))
