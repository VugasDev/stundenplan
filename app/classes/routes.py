from flask import (Blueprint, render_template, redirect, url_for, flash, request,
                   abort, current_app)
from flask_login import login_required, current_user
from itsdangerous import URLSafeTimedSerializer, BadData

from app.extensions import db
from app.models import SchoolClass, Membership, Lesson
from app.classes.forms import JoinForm
from app.verify import verify_and_list_classes

bp = Blueprint("classes", __name__)

_JOIN_SALT = "classes-join"
_JOIN_MAX_AGE_SECONDS = 15 * 60


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def _generate_join_token(server_url: str, school: str, username: str, klassen) -> str:
    """Bindet das, was choose() verwendet, an das, was join() tatsächlich
    verifiziert hat — die Zugangsdaten und die verifizierte Klassenliste
    können danach nicht mehr durch beliebige Formulardaten ersetzt werden."""
    payload = {
        "server_url": server_url,
        "school": school,
        "username": username,
        "klassen_ids": [k.id for k in klassen],
    }
    return _serializer().dumps(payload, salt=_JOIN_SALT)


def _verify_join_token(token: str):
    """Liefert die Nutzlast oder None, wenn das Token fehlt, manipuliert oder
    abgelaufen ist."""
    try:
        return _serializer().loads(token, salt=_JOIN_SALT,
                                   max_age=_JOIN_MAX_AGE_SECONDS)
    except BadData:
        return None


def _own_memberships():
    return (db.session.query(Membership)
            .filter_by(user_id=current_user.id).all())


@bp.route("/classes")
@login_required
def list_classes():
    return render_template("classes/list.html", memberships=_own_memberships())


@bp.route("/classes/join", methods=["GET", "POST"])
@login_required
def join():
    form = JoinForm()
    if form.validate_on_submit():
        ok, klassen, fehler = verify_and_list_classes(
            form.server_url.data, form.school.data,
            form.username.data, form.password.data)
        if not ok:
            flash(fehler, "error")
            return render_template("classes/join.html", form=form)
        # Das Token bindet Server, Schule, Benutzername und die verifizierte
        # Klassenliste — choose() vertraut nur ihm, nie dem Formular. Das
        # Passwort wird nur weitergereicht, damit die Person im naechsten
        # Schritt spenden kann — gespeichert wird es hier nicht.
        token = _generate_join_token(form.server_url.data, form.school.data,
                                     form.username.data, klassen)
        return render_template("classes/choose.html", klassen=klassen,
                               token=token,
                               password=form.password.data)
    return render_template("classes/join.html", form=form)


@bp.route("/classes/choose", methods=["POST"])
@login_required
def choose():
    daten = _verify_join_token(request.form.get("token", ""))
    if daten is None:
        flash("Die Auswahl ist zu lange her oder ungültig. Bitte noch einmal "
              "starten.", "error")
        return redirect(url_for("classes.join"))

    server_url = daten["server_url"]
    school = daten["school"]
    username = daten["username"]

    try:
        untis_class_id = int(request.form["untis_class_id"])
    except (KeyError, ValueError):
        abort(400)
    if untis_class_id not in daten["klassen_ids"]:
        flash("Diese Klasse gehört nicht zur geprüften Auswahl. Bitte noch "
              "einmal starten.", "error")
        return redirect(url_for("classes.join"))

    name = request.form["name"]
    password = request.form["password"]
    spenden = bool(request.form.get("spenden"))

    school_class = (db.session.query(SchoolClass)
                    .filter_by(server_url=server_url, school=school,
                               untis_class_id=untis_class_id).first())
    if school_class is None:
        school_class = SchoolClass(server_url=server_url, school=school,
                                   untis_class_id=untis_class_id, name=name)
        db.session.add(school_class)
        db.session.flush()

    # Gespendet wird nur, wenn die Klasse noch keine Quelle hat.
    if spenden and not school_class.has_source:
        cipher = current_app.extensions["cipher"]
        school_class.username = username
        school_class.password_encrypted = cipher.encrypt(password)
        school_class.donor_user_id = current_user.id

    vorhanden = (db.session.query(Membership)
                 .filter_by(user_id=current_user.id, class_id=school_class.id).first())
    if vorhanden is None:
        db.session.add(Membership(user_id=current_user.id, class_id=school_class.id))
    db.session.commit()

    if school_class.has_source:
        flash(f"Klasse {school_class.name} hinzugefügt.", "success")
    else:
        flash(f"Klasse {school_class.name} hinzugefügt. Für sie liegt noch kein "
              "Zugang vor — bis jemand spendet, bleibt der Plan leer.", "error")
    return redirect(url_for("classes.list_classes"))


@bp.route("/classes/<int:class_id>/revoke", methods=["POST"])
@login_required
def revoke(class_id):
    school_class = db.session.get(SchoolClass, class_id)
    if school_class is None or school_class.donor_user_id != current_user.id:
        abort(404)
    school_class.username = None
    school_class.password_encrypted = None
    school_class.donor_user_id = None
    school_class.last_fetch_at = None
    school_class.last_fetch_status = None
    # Ohne Quelle findet nie wieder ein Abruf statt — die Stunden der Klasse
    # muessen deshalb mit dem Widerruf verschwinden, sonst blieben sie allen
    # Mitgliedern unbegrenzt sichtbar (Spec: Löschfristen, keine Historie).
    (db.session.query(Lesson)
     .filter_by(class_id=school_class.id)
     .delete(synchronize_session=False))
    db.session.commit()
    flash("Spende zurückgezogen. Die Zugangsdaten und gespeicherten Stunden "
          "wurden gelöscht.", "success")
    return redirect(url_for("classes.list_classes"))


@bp.route("/classes/<int:class_id>/leave", methods=["POST"])
@login_required
def leave(class_id):
    m = (db.session.query(Membership)
         .filter_by(user_id=current_user.id, class_id=class_id).first())
    if m is None:
        abort(404)
    db.session.delete(m)
    db.session.commit()
    flash("Klasse entfernt.", "success")
    return redirect(url_for("classes.list_classes"))
