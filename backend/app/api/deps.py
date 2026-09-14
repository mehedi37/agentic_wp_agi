import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_session
from app.schemas.auth import CurrentUser
from app.schemas.enums import Role
from app.services.users import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> CurrentUser:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_access_token(token)
        user_id = uuid.UUID(claims["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise credentials_error from exc

    user = get_user_by_id(session, user_id)
    if user is None:
        raise credentials_error
    return CurrentUser.model_validate(user)


def require_role(*roles: Role) -> Callable[[CurrentUser], CurrentUser]:
    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role in {roles}, got {current_user.role!r}",
            )
        return current_user

    return _dependency
