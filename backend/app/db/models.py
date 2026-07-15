from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Paper(Base):
    """Bibliographic + battery-domain data for one paper.

    Keyed by external_paper_id (the Semantic Scholar paper ID) so battery-
    metadata extraction (a Gemini call) is reused across searches instead
    of being re-run every time the same paper resurfaces.
    """

    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_paper_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[str] = mapped_column(Text, default="")
    journal: Mapped[str] = mapped_column(String, default="")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doi: Mapped[str] = mapped_column(String, default="")
    abstract: Mapped[str] = mapped_column(Text, default="")

    # Battery snapshot
    cathode: Mapped[str] = mapped_column(String, default="")
    anode: Mapped[str] = mapped_column(String, default="")
    electrolyte: Mapped[str] = mapped_column(String, default="")
    voltage_window: Mapped[str] = mapped_column(String, default="")
    cell_type: Mapped[str] = mapped_column(String, default="")

    # Research analysis
    experimental_conditions: Mapped[str] = mapped_column(Text, default="")
    performance_summary: Mapped[str] = mapped_column(Text, default="")
    innovation: Mapped[str] = mapped_column(Text, default="")
    advantages: Mapped[str] = mapped_column(Text, default="")
    limitations: Mapped[str] = mapped_column(Text, default="")

    extracted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    search_results: Mapped[list["SearchResult"]] = relationship(back_populates="paper")

    @property
    def is_extracted(self) -> bool:
        return self.extracted_at is not None


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keyword: Mapped[str] = mapped_column(String, index=True)
    expanded_query: Mapped[str] = mapped_column(String, default="")
    ai_degraded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    results: Mapped[list["SearchResult"]] = relationship(
        back_populates="search_query", order_by="SearchResult.rank"
    )


class SearchResult(Base):
    """One ranked paper within one search (query-specific relevance)."""

    __tablename__ = "search_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_query_id: Mapped[int] = mapped_column(ForeignKey("search_queries.id"), index=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)

    rank: Mapped[int] = mapped_column(Integer)
    relevance_score: Mapped[float] = mapped_column(Float)
    why_selected: Mapped[str] = mapped_column(Text, default="")

    search_query: Mapped["SearchQuery"] = relationship(back_populates="results")
    paper: Mapped["Paper"] = relationship(back_populates="search_results")
