from __future__ import annotations

import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

from app.extensions import db, limiter
from app.models import WebUntisAccount, Lesson
from app.fetch import fetch_account

bp = Blueprint("timetable", __name__)


def _monday_of(d: datetime.date) -> datetime.date:
    return d - datetime.timedelta(days=d.weekday())


def _parse_week(arg: str | None) -> datetime.date:
    if arg:
        try:
            return _monday_of(datetime.date.fromisoformat(arg))
        except ValueError:
            pass
    return _monday_of(datetime.date.today())


def _own_account_ids() -> list[int]:
    rows = db.session.query(WebUntisAccount.id).filter_by(user_id=current_user.id).all()
    return [r[0] for r in rows]


@bp.route("/")
@login_required
def index():
    view = request.args.get("view", "week")
    monday = _parse_week(request.args.get("week"))
    sunday = monday + datetime.timedelta(days=6)

    account_ids = _own_account_ids()
    accounts = db.session.query(WebUntisAccount).filter_by(user_id=current_user.id).all()
    colors = {a.id: a.color for a in accounts}
    labels = {a.id: a.label for a in accounts}

    lessons = []
    if account_ids:
        lessons = (db.session.query(Lesson)
                   .filter(Lesson.account_id.in_(account_ids),
                           Lesson.date >= monday, Lesson.date <= sunday)
                   .order_by(Lesson.date, Lesson.start_time).all())

    days = [monday + datetime.timedelta(days=i) for i in range(7)]
    # Zeitschienen = alle vorkommenden Startzeiten, sortiert
    slots = sorted({l.start_time for l in lessons})
    grid = {(l.date, l.start_time): [] for l in lessons}
    for l in lessons:
        grid[(l.date, l.start_time)].append(l)

    return render_template(
        "timetable/index.html",
        view=view, monday=monday, sunday=sunday,
        prev_week=(monday - datetime.timedelta(days=7)).isoformat(),
        next_week=(monday + datetime.timedelta(days=7)).isoformat(),
        days=days, slots=slots, grid=grid, lessons=lessons,
        colors=colors, labels=labels, accounts=accounts,
    )


@bp.route("/refresh", methods=["POST"])
@limiter.limit("10 per hour")
@login_required
def refresh():
    cipher = current_app.extensions["cipher"]
    accounts = db.session.query(WebUntisAccount).filter_by(user_id=current_user.id).all()
    for account in accounts:
        fetch_account(account, cipher)
    flash("Stundenpläne aktualisiert.", "success")
    return redirect(url_for("timetable.index"))
