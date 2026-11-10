import hashlib
import hmac
import secrets

ITERATIONS = 20_000


def hash_password(password, salt=None):
    """Return (hex digest, salt)."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS)
    return digest.hex(), salt


def verify_password(password, password_hash, salt) -> bool:
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, password_hash)


def validate_password(password):
    """Return None if the password meets the policy, otherwise the reason it fails."""
    if not isinstance(password, str) or len(password) < 8:
        return "must be at least 8 characters"
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        return "must contain a letter and a digit"
    return None
