from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.base import TimestampMixin


class User(Base, TimestampMixin):
    """Placeholder account model for future authentication.

    Structural only: nothing writes to this table yet. It exists so
    core/security.py's token helpers and api/deps.py's get_current_user
    stub have a concrete shape to eventually load against once real
    signup/login is implemented — see docs/ARCHITECTURE.md.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
