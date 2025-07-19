from typing import Any
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.urls import url_parse

from auth.utils import check_password
from forms.auth_forms import LoginForm


def init_auth_routes(app, login_manager, user_manager, bcrypt) -> Blueprint:
    """Initialize authentication routes"""

    auth_bp = Blueprint("auth", __name__)

    @login_manager.user_loader
    def load_user(user_id) -> Any:

        return user_manager.get_user_by_id(user_id)

    @login_manager.unauthorized_handler
    def unauthorized() -> str:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("login", next=request.url))

    @app.route("/login", methods=["GET", "POST"])
    def login() -> str:
        # Redirect if user is already logged in
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        form = LoginForm()
        if form.validate_on_submit():
            user = user_manager.get_user_by_email(form.email.data)

            # Handle non-existent user
            if user is None:
                flash("Invalid username or password.", "danger")
                return render_template("login.html", form=form)

            # Handle locked account
            if user_manager.check_if_locked(user):
                flash(
                    "Your account has been locked due to multiple failed login attempts. Please contact support.",
                    "danger",
                )
                return render_template("login.html", form=form)

            # Check password
            if check_password(bcrypt, user.password, form.password.data):
                login_user(user)
                user_manager.reset_failed_login(user)
                flash("Welcome back!", "success")

                # Handle next page redirection
                next_page = request.args.get("next")
                if not next_page or url_parse(next_page).netloc != "":
                    next_page = url_for("dashboard")
                return redirect(next_page)
            else:
                # Increment failed login attempts
                user_manager.increment_failed_login(user)
                flash("Invalid username or password.", "danger")

        # If GET request or validation failed, show login form
        return render_template("login.html", form=form)

    @app.route("/logout")
    @login_required
    def logout() -> str:
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard() -> str:
        return render_template("dashboard.html")

    return auth_bp
