"""Registration, login, logout and account page."""
from urllib.parse import urlparse

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..db import DBError, friendly_error
from ..security import login_required, login_user, logout_user
from ..services import orders, users

bp = Blueprint("auth", __name__)


def _safe_next(target):
    if not target:
        return None
    u = urlparse(target)
    if u.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.get("user_id"):
        return redirect(url_for("main.home"))
    if request.method == "POST":
        user = users.authenticate(request.form.get("email", ""), request.form.get("password", ""))
        if not user:
            flash("Incorrect e-mail or password.", "error")
            return render_template("auth/login.html", email=request.form.get("email", "")), 401
        login_user(user)
        flash(f"Welcome back, {user['full_name'].split()[0]}!", "success")
        return redirect(_safe_next(request.form.get("next")) or url_for("main.home"))
    return render_template("auth/login.html", next=_safe_next(request.args.get("next")))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.get("user_id"):
        return redirect(url_for("main.home"))
    form = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in ("full_name", "email", "phone", "city")}
        pw, confirm = request.form.get("password", ""), request.form.get("confirm", "")
        if pw != confirm:
            flash("Passwords do not match.", "error")
            return render_template("auth/register.html", form=form), 400
        try:
            user = users.register(form["full_name"], form["email"], pw, form["phone"], form["city"])
        except DBError as e:
            flash(str(e), "error")
            return render_template("auth/register.html", form=form), 400
        except Exception as e:  # noqa: BLE001
            flash(friendly_error(e), "error")
            return render_template("auth/register.html", form=form), 400
        login_user(user)
        flash("Account created. Happy sustainable shopping!", "success")
        return redirect(url_for("main.home"))
    return render_template("auth/register.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.home"))


@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "profile":
                users.update_profile(g.user_id, *(request.form.get(k, "") for k in
                                                  ("full_name", "phone", "address_line", "city", "state", "pincode")))
                flash("Profile updated.", "success")
            elif action == "password":
                users.change_password(g.user_id, request.form.get("current", ""), request.form.get("new", ""))
                flash("Password changed.", "success")
        except Exception as e:  # noqa: BLE001
            flash(friendly_error(e), "error")
        return redirect(url_for("auth.account"))
    user = users.get_by_id(g.user_id)
    recent = orders.list_orders(g.user_id)[:5]
    return render_template("auth/account.html", user=user, recent=recent)
