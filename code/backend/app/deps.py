"""FastAPI dependencies: БД и текущий пользователь."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth import decode_access_token
from app.db import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=True)


def get_current_user_ws(token: str, db: Session) -> User:
    """
    Текущий пользователь по JWT (для WebSocket: token из query param).
    При невалидном токене или отсутствии пользователя бросает WebSocketException.
    """
    from fastapi import WebSocketException

    try:
        payload = decode_access_token(token)
        sub = payload.get("sub")
        if sub is None:
            raise ValueError("no sub")
        user_id = int(sub)
    except (JWTError, ValueError, TypeError):
        raise WebSocketException(code=1008, reason="Invalid or missing token")
    user = db.get(User, user_id)
    if user is None:
        raise WebSocketException(code=1008, reason="User not found")
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Текущий пользователь по JWT. При невалидном токене или отсутствии пользователя — 401."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id = int(sub)
    except (JWTError, ValueError):
        raise credentials_exception
    user = db.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user
