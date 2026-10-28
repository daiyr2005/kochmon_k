import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.database import get_db
from app.db.models import Role, User

bearer = HTTPBearer(auto_error=False)


def _user_from(creds: HTTPAuthorizationCredentials | None, db: Session) -> User | None:
    if not creds:
        return None
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(401, "Invalid token type")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")
    return user


def get_current_user(creds=Depends(bearer), db: Session = Depends(get_db)) -> User:
    user = _user_from(creds, db)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def get_optional_user(creds=Depends(bearer), db: Session = Depends(get_db)) -> User | None:
    return _user_from(creds, db)


def require_role(*roles: Role):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Forbidden")
        return user
    return checker


require_admin = require_role(Role.admin)
