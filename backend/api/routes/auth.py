from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> None:
    """Placeholder token endpoint. Login is not implemented yet.

    Exists so the future endpoint's shape (OAuth2 password grant, matching
    api/deps.py's oauth2_scheme tokenUrl) is visible in the OpenAPI schema
    ahead of time, without accepting or checking real credentials.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Login is not implemented yet")
