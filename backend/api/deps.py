from typing import Annotated, NoReturn

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from database.session import get_db

# Shared dependency alias so route signatures stay short:
# async def handler(db: DBSession): ...
DBSession = Annotated[AsyncSession, Depends(get_db)]

# --- Authentication placeholder -- not applied to any route yet ---
#
# tokenUrl points at the /auth/token stub in api/routes/auth.py, which
# itself returns 501. Defining the scheme now means the eventual real
# implementation is a matter of filling in get_current_user's body and
# adding `Depends(get_current_user)` to routes that need it -- no route
# currently does, so nothing today requires a caller to be authenticated.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{get_settings().API_V1_PREFIX}/auth/token", auto_error=False)


async def get_current_user(token: Annotated[str | None, Depends(_oauth2_scheme)] = None) -> NoReturn:
    """Placeholder for a future `Depends(get_current_user)` route guard.

    Deliberately unconditional: real login isn't implemented, so there is
    no valid token this could ever accept. Once a User model-backed login
    flow exists, this should decode the token (core/security.py), load the
    user, and raise 401 on anything invalid instead of 501 on everything.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Authentication is not implemented yet")
