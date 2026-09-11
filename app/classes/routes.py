from flask import (Blueprint, render_template, redirect, url_for, flash, request,
                   abort, current_app)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import SchoolClass, Membership
from app.classes.forms import JoinForm
from app.verify import verify_and_list_classes

bp = Blueprint("classes", __name__)


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
        # Die Zugangsdaten werden nur weitergereicht, damit die Person im
        # naechsten Schritt spenden kann — gespeichert wird hier nichts.
        return render_template("classes/choose.html", klassen=klassen,
                               server_url=form.server_url.data,
                               school=form.school.data,
                               username=form.username.data,
                               password=form.password.data)
    return render_template("classes/join.html", form=form)


@bp.route("/classes/choose", methods=["POST"])
@login_required
def choose():
    server_url = request.form["server_url"]
    school = request.form["school"]
    untis_class_id = int(request.form["untis_class_id"])
    name = request.form["name"]
    username = request.form["username"]
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
    db.session.commit()
    flash("Spende zurückgezogen. Die Zugangsdaten wurden gelöscht.", "success")
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
