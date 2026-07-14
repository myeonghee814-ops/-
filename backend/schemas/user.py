from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Fields shared by every user schema variant. Not exposed by any
    endpoint yet -- see models/user.py and docs/ARCHITECTURE.md."""

    email: EmailStr


class UserCreate(UserBase):
    """Shape a future signup endpoint would accept."""

    password: str = Field(..., min_length=8)


class UserRead(UserBase):
    """Shape a future endpoint would return. Deliberately excludes
    hashed_password -- it should never leave the database layer."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
