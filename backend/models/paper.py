from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.base import TimestampMixin


class Paper(Base, TimestampMixin):
    """Domain model for a battery electrolyte research paper.

    This is a structural placeholder: the columns describe the shape of the
    data literature search/ingestion will eventually populate. No ingestion
    logic exists yet.
    """

    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    authors: Mapped[str] = mapped_column(String(1024), default="")
    abstract: Mapped[str] = mapped_column(Text, default="")
    doi: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    source: Mapped[str] = mapped_column(String(100), default="")
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
