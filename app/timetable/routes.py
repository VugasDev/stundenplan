from __future__ import annotations

import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

from app.extensions import db, limiter
from app.models import WebUntisAccount, Lesson
from app.fetch import fetch_class
from app.blocks import merge_lessons, build_axis, agenda_view, axis_payload
from app.zeit import local_now, local_today

bp = Blueprint("timetable", __name__)

AGENDA_VORSCHAU_TAGE = 14


def _monday_of(d: datetime.date) -> datetime.date:
    return d - datetime.timedelta(days=d.weekday())


def _parse_date(arg: str | None, default: datetime.date) -> datetime.date:
    if arg:
        try:
            return datetime.date.fromisoformat(arg)
        except ValueError:
            pass
    return default


def _own_accounts() -> list[WebUntisAccount]:
    return db.session.query(WebUntisAccount).filter_by(user_id=current_user.id).all()


def _lessons_between(account_ids, von: datetime.date, bis: datetime.date):
    if not account_ids:
        return []
    return (db.session.query(Lesson)
            .filter(Lesson.account_id.in_(account_ids),
                    Lesson.date >= von, Lesson.date <= bis)
            .order_by(Lesson.date, Lesson.start_time).all())


def _positioned(blocks, axis):
    """Ergaenzt jeden Block um seine Lage auf der Achse."""
    return [(b, axis.y(b.start_time), axis.span(b.start_time, b.end_time))
            for b in blocks]


@bp.route("/")
@login_required
def index():
    view = request.args.get("view", "agenda")
    accounts = _own_accounts()
    labels = {a.id: a.label for a in accounts}
    account_ids = [a.id for a in accounts]
    zone = current_app.config["TIMEZONE"]
    heute = local_today(zone)

    gemeinsam = {"accounts": accounts, "labels": labels, "view": view, "heute": heute}

    if view == "week":
        monday = _monday_of(_parse_date(request.args.get("week"), heute))
        sunday = monday + datetime.timedelta(days=6)
        blocks = merge_lessons(_lessons_between(account_ids, monday, sunday))
        axis = build_axis(blocks)
        # Wochenende nur zeigen, wenn dort tatsaechlich Unterricht liegt.
        belegte_tage = {b.date for b in blocks}
        tage = [monday + datetime.timedelta(days=i) for i in range(7)
                if i < 5 or (monday + datetime.timedelta(days=i)) in belegte_tage]
        spalten = [(tag, _positioned([b for b in blocks if b.date == tag], axis))
                   for tag in tage]
        return render_template(
            "timetable/week.html", axis=axis, spalten=spalten,
            axis_daten=axis_payload(axis), jetzt_sichtbar=monday <= heute <= sunday,
            monday=monday, sunday=sunday,
            prev_week=(monday - datetime.timedelta(days=7)).isoformat(),
            next_week=(monday + datetime.timedelta(days=7)).isoformat(),
            **gemeinsam)

    if view == "day":
        tag = _parse_date(request.args.get("day"), heute)
        blocks = merge_lessons(_lessons_between(account_ids, tag, tag))
        axis = build_axis(blocks)
        return render_template(
            "timetable/day.html", axis=axis, eintraege=_positioned(blocks, axis),
            axis_daten=axis_payload(axis), jetzt_sichtbar=(tag == heute),
            tag=tag,
            prev_day=(tag - datetime.timedelta(days=1)).isoformat(),
            next_day=(tag + datetime.timedelta(days=1)).isoformat(),
            **gemeinsam)

    bis = heute + datetime.timedelta(days=AGENDA_VORSCHAU_TAGE)
    blocks = merge_lessons(_lessons_between(account_ids, heute, bis))
    return render_template("timetable/agenda.html",
                           agenda=agenda_view(blocks, local_now(zone)),
                           **gemeinsam)


@bp.route("/refresh", methods=["POST"])
@limiter.limit("10 per hour")
@login_required
def refresh():
    cipher = current_app.extensions["cipher"]
    for account in _own_accounts():
        # ACHTUNG: Diese Route arbeitet noch mit Konten statt Klassen (WebUntisAccount
        # statt SchoolClass). Der Aufruf wurde in Aufgabe 5 nur so weit angepasst, dass
        # der Import wieder traegt (fetch_account existiert nicht mehr) — fachlich ist
        # das falsch und wuerde hier zur Laufzeit mit AttributeError abstuerzen. Die
        # Umstellung dieser Ansicht auf Klassen gehoert zu Aufgabe 7.
        fetch_class(account, cipher)
    flash("Stundenpläne aktualisiert.", "success")
    return redirect(request.referrer or url_for("timetable.index"))
