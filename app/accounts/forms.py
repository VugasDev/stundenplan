from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Length, Optional


class AccountForm(FlaskForm):
    label = StringField("Bezeichnung", validators=[DataRequired(), Length(max=100)])
    server_url = StringField("Server (z.B. xyz.webuntis.com)", validators=[DataRequired()])
    school = StringField("Schule (aus ?school=)", validators=[DataRequired()])
    username = StringField("WebUntis-Benutzer", validators=[DataRequired()])
    # Beim Bearbeiten leer lassen = Passwort unverändert
    password = PasswordField("WebUntis-Passwort", validators=[Optional()])
