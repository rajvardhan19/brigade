"""Password reset: issue single-use, expiring tokens by email and redeem them."""
import hashlib
import secrets

from app import clock
from app.models import ResetToken
from app.passwords import hash_password, validate_password

TOKEN_TTL_SECONDS = 30 * 60


class ResetError(Exception):
    pass


def _hash_token(token: str) -> str:
    # Tokens are 256-bit random values, so a fast unsalted hash is enough to
    # keep the raw value out of storage while still allowing lookup.
    return hashlib.sha256(token.encode()).hexdigest()


def request_reset(store, outbox, email):
    """Email a reset token if the account exists. Silent either way."""
    if not isinstance(email, str) or not email:
        return
    user = store.get_user_by_email(email)
    if user is None:
        return
    token = secrets.token_urlsafe(32)
    now = clock.now()
    # A new request supersedes any earlier unused token for this user.
    store.delete_reset_tokens_for_user(user.id)
    store.add_reset_token(ResetToken(_hash_token(token), user.id, now, now + TOKEN_TTL_SECONDS))
    outbox.send(
        user.email,
        "Password reset",
        "Someone asked to reset the password for your notes account.\n"
        "If it was you, use this token within 30 minutes:\n"
        f"token: {token}\n",
    )


def confirm_reset(store, token, new_password):
    """Set a new password using a reset token. Raises ResetError on failure."""
    if not isinstance(token, str) or not token:
        raise ResetError("invalid token")
    token_hash = _hash_token(token)
    record = store.get_reset_token(token_hash)
    if record is None:
        raise ResetError("invalid token")
    if clock.now() >= record.expires_at:
        store.delete_reset_token(token_hash)
        raise ResetError("invalid token")
    user = store.get_user(record.user_id)
    if user is None:
        store.delete_reset_token(token_hash)
        raise ResetError("invalid token")
    # Check the policy before consuming the token so the user can retry.
    if validate_password(new_password):
        raise ResetError("weak password")
    store.delete_reset_tokens_for_user(user.id)
    user.password_hash, user.salt = hash_password(new_password)
    store.delete_sessions_for_user(user.id)
    return user
