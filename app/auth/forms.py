from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo


class RegisterForm(FlaskForm):
    email = StringField("E-Mail", validators=[DataRequired(), Email()])
    password = PasswordField("Passwort", validators=[DataRequired(), Length(min=8)])
    invite_code = StringField("Einladungscode")


class LoginForm(FlaskForm):
    email = StringField("E-Mail", validators=[DataRequired(), Email()])
    password = PasswordField("Passwort", validators=[DataRequired()])


class ForgotPasswordForm(FlaskForm):
    email = StringField("E-Mail", validators=[DataRequired(), Email()])


class ResetPasswordForm(FlaskForm):
    password = PasswordField("Neues Passwort", validators=[DataRequired(), Length(min=8)])
    password_repeat = PasswordField(
        "Passwort wiederholen",
        validators=[DataRequired(), EqualTo("password", message="Die Passwörter stimmen nicht überein.")],
    )
