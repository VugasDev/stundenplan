from flask import (Blueprint, render_template, redirect, url_for, flash, abort,
                   current_app)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import WebUntisAccount
from app.accounts.forms import AccountForm

bp = Blueprint("accounts", __name__)


def _own_account_or_404(account_id: int) -> WebUntisAccount:
    account = db.session.get(WebUntisAccount, account_id)
    if account is None or account.user_id != current_user.id:
        abort(404)
    return account


@bp.route("/accounts")
@login_required
def list_accounts():
    accounts = db.session.query(WebUntisAccount).filter_by(user_id=current_user.id).all()
    return render_template("accounts/list.html", accounts=accounts)


@bp.route("/accounts/add", methods=["GET", "POST"])
@login_required
def add_account():
    form = AccountForm()
    if form.validate_on_submit():
        if not form.password.data:
            flash("Beim Anlegen ist ein Passwort erforderlich.", "error")
            return render_template("accounts/form.html", form=form, mode="add")
        cipher = current_app.extensions["cipher"]
        account = WebUntisAccount(
            user_id=current_user.id,
            label=form.label.data, color=form.color.data,
            server_url=form.server_url.data, school=form.school.data,
            username=form.username.data,
            password_encrypted=cipher.encrypt(form.password.data),
        )
        db.session.add(account)
        db.session.commit()
        flash("Zugang hinzugefügt.", "success")
        return redirect(url_for("accounts.list_accounts"))
    return render_template("accounts/form.html", form=form, mode="add")


@bp.route("/accounts/<int:account_id>/edit", methods=["GET", "POST"])
@login_required
def edit_account(account_id):
    account = _own_account_or_404(account_id)
    form = AccountForm(obj=account)
    if form.validate_on_submit():
        account.label = form.label.data
        account.color = form.color.data
        account.server_url = form.server_url.data
        account.school = form.school.data
        account.username = form.username.data
        if form.password.data:  # leer = unverändert
            account.password_encrypted = current_app.extensions["cipher"].encrypt(form.password.data)
        db.session.commit()
        flash("Zugang aktualisiert.", "success")
        return redirect(url_for("accounts.list_accounts"))
    return render_template("accounts/form.html", form=form, mode="edit", account=account)


@bp.route("/accounts/<int:account_id>/delete", methods=["POST"])
@login_required
def delete_account(account_id):
    account = _own_account_or_404(account_id)
    db.session.delete(account)
    db.session.commit()
    flash("Zugang gelöscht.", "success")
    return redirect(url_for("accounts.list_accounts"))
