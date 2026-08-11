import secrets
from datetime import datetime, timezone, timedelta
import bcrypt


def hash_password(plain_password: str) -> str:
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def check_password(plain_password: str, hashed: str) -> bool:
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def create_expiry_timestamp(days=15):
    return datetime.now(timezone.utc) + timedelta(days=days)


def compare_session_data(stored: dict, new: dict):
    time_now = datetime.now(timezone.utc)
    if (
        (stored["session_id"] != new["session_id"])
        or (stored["csrf_token"] != new["csrf_token"])
        or (stored["expires_at"] < time_now)
    ):
        return False
    return True
