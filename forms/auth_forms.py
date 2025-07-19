from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, ValidationError


class LoginForm(FlaskForm):
    """Form for user login"""

    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email cannot be empty"),
            Email(message="Please enter a valid email address"),
        ],
    )
    password = PasswordField("Password", validators=[DataRequired(message="Password cannot be empty")])
    submit = SubmitField("Log In")

    def validate(self, extra_validators=None):
        """Custom validation to handle empty fields case"""
        if not super(LoginForm, self).validate():
            # If either field is empty, generate a custom error message
            if not self.email.data and not self.password.data:
                self.email.errors.append("Email and password cannot be empty")
            return False
        return True
