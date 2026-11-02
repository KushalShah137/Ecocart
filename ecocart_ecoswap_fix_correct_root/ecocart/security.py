"""Password hashing, CSRF protection and login/authorisation decorators."""
import hmac
import re
import secrets
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def hash_password(pw: str) -> str:
    return generate_password_hash(pw, method="scrypt")


def verify_password(pw_hash: str, pw: str) -> bool:
    try:
        return check_password_hash(pw_hash, pw)
    except (ValueError, TypeError):
        return False


def validate_password(pw: str):
    if len(pw) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Password must contain letters and numbers."
    return None


def validate_email(email: str):
    return None if EMAIL_RE.match(email or "") else "Enter a valid e-mail address."


# ---- CSRF ---------------------------------------------------------------------
def csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def csrf_protect():
    """before_request hook: every state-changing request must carry a valid token."""
    if request.method in SAFE_METHODS or request.endpoint in ("static",):
        return None
    if request.blueprint and request.blueprint.startswith("api_public"):
        return None
    sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token") or (request.get_json(silent=True) or {}).get("_csrf")
    expected = session.get("_csrf")
    if not sent or not expected or not hmac.compare_digest(sent, expected):
        abort(400, description="Invalid or missing CSRF token. Please reload the page and try again.")
    return None


# ---- Auth ---------------------------------------------------------------------
def login_user(user: dict):
    session.clear()
    session.permanent = True
    session["user_id"] = user["user_id"]
    session["user_name"] = user["full_name"]
    session["role"] = user.get("role", "CUSTOMER")
    csrf_token()


def logout_user():
    session.clear()


def current_user_id():
    return session.get("user_id")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            if request.accept_mimetypes.best == "application/json" or request.is_json:
                abort(401)
            flash("Please sign in to continue.", "info")
            return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "ADMIN":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def load_current_user():
    g.user_id = session.get("user_id")
    g.user_name = session.get("user_name")
    g.role = session.get("role")
