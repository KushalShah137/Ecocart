"""Registration, login lookup and profile updates."""
from ..db import DBError, execute, query_one, transaction
from ..security import hash_password, validate_email, validate_password, verify_password


def get_by_email(email):
    return query_one("SELECT * FROM app_user WHERE LOWER(email) = LOWER(:e)", e=email.strip())


def get_by_id(user_id):
    return query_one("""SELECT user_id, full_name, email, phone, address_line, city, state, pincode, role, is_demo,
                        data_origin, created_at FROM app_user WHERE user_id = :u""", u=user_id)


def register(full_name, email, password, phone=None, city=None):
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    if len(full_name) < 2 or len(full_name) > 120:
        raise DBError("Please enter your name.")
    err = validate_email(email) or validate_password(password or "")
    if err:
        raise DBError(err)
    with transaction():
        if get_by_email(email):
            raise DBError("An account with this e-mail already exists. Try signing in.")
        execute("""INSERT INTO app_user (full_name, email, password_hash, phone, city, role, is_demo, data_origin)
                   VALUES (:n, :e, :p, :ph, :c, 'CUSTOMER', 0, 'LIVE')""",
                n=full_name, e=email, p=hash_password(password), ph=(phone or None), c=(city or None))
    return get_by_email(email)


def authenticate(email, password):
    user = get_by_email(email or "")
    if not user or not verify_password(user["password_hash"], password or ""):
        return None
    if str(user["password_hash"]).startswith("!unusable"):
        return None   # imported analytics-only customers can't log in
    return user


def update_profile(user_id, full_name, phone, address_line, city, state, pincode):
    full_name = (full_name or "").strip()
    if len(full_name) < 2:
        raise DBError("Please enter your name.")
    with transaction():
        execute("""UPDATE app_user SET full_name = :n, phone = :ph, address_line = :a, city = :c, state = :s, pincode = :z
                   WHERE user_id = :u""",
                n=full_name[:120], ph=(phone or None), a=(address_line or None), c=(city or None), s=(state or None),
                z=(pincode or None), u=user_id)


def change_password(user_id, current, new):
    user = query_one("SELECT password_hash FROM app_user WHERE user_id = :u", u=user_id)
    if not user or not verify_password(user["password_hash"], current or ""):
        raise DBError("Current password is incorrect.")
    err = validate_password(new or "")
    if err:
        raise DBError(err)
    with transaction():
        execute("UPDATE app_user SET password_hash = :p WHERE user_id = :u", p=hash_password(new), u=user_id)
