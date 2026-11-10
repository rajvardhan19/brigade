import secrets

from app import clock
from app.models import Session
from app.passwords import hash_password, validate_password, verify_password


class AuthError(Exception):
    pass


def register(store, email, password):
    if not email or "@" not in email:
        raise AuthError("invalid email")
    if store.get_user_by_email(email):
        raise AuthError("email already registered")
    problem = validate_password(password)
    if problem:
        raise AuthError(f"weak password: {problem}")
    password_hash, salt = hash_password(password)
    return store.add_user(email, password_hash, salt, clock.now())


def login(store, email, password) -> str:
    user = store.get_user_by_email(email or "")
    if user is None or not verify_password(password or "", user.password_hash, user.salt):
        raise AuthError("invalid credentials")
    token = secrets.token_urlsafe(32)
    store.add_session(Session(token, user.id, clock.now()))
    return token


def logout(store, token):
    store.delete_session(token)


def require_user(store, token):
    session = store.get_session(token) if token else None
    if session is None:
        raise AuthError("not logged in")
    user = store.get_user(session.user_id)
    if user is None:
        raise AuthError("not logged in")
    return user
