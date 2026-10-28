import uuid
from datetime import timedelta

import bcrypt
import jwt

from app.core.config import settings
from app.db.models import utcnow

ALGO = "HS256"


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def _encode(sub: int, typ: str, ttl: timedelta):
    jti = uuid.uuid4().hex
    exp = utcnow() + ttl
    token = jwt.encode({"sub": str(sub), "type": typ, "jti": jti, "exp": exp}, settings.SECRET_KEY, algorithm=ALGO)
    return token, jti, exp


def create_access_token(user_id: int) -> str:
    return _encode(user_id, "access", timedelta(minutes=settings.ACCESS_TOKEN_MINUTES))[0]


def create_refresh_token(user_id: int):
    """Returns (token, jti, expires_at)."""
    return _encode(user_id, "refresh", timedelta(days=settings.REFRESH_TOKEN_DAYS))


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])
