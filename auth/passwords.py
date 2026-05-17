from passlib.context import CryptContext

MIN_LENGTH = 8

_ctx = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return _ctx.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _ctx.verify(password, hashed)


def validate_password_policy(password: str) -> str | None:
    """Return error message or None if valid."""
    if len(password) < MIN_LENGTH:
        return f"Password must be at least {MIN_LENGTH} characters."
    if not password.strip():
        return "Password must contain at least one non-space character."
    return None
