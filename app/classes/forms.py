from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Length


class JoinForm(FlaskForm):
    server_url = StringField("Server (z.B. xyz.webuntis.com)",
                             validators=[DataRequired(), Length(max=255)])
    school = StringField("Schule (aus ?school=)",
                         validators=[DataRequired(), Length(max=255)])
    username = StringField("WebUntis-Benutzer", validators=[DataRequired()])
    password = PasswordField("WebUntis-Passwort", validators=[DataRequired()])
