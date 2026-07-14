from pydantic import BaseModel, ConfigDict


class PaperBase(BaseModel):
    """Fields shared by every paper schema variant."""

    title: str
    authors: str = ""
    abstract: str = ""
    doi: str | None = None
    source: str = ""
    url: str | None = None


class PaperCreate(PaperBase):
    """Shape accepted when creating a paper record."""

    pass


class PaperRead(PaperBase):
    """Shape returned to API clients. Separated from PaperCreate so the API
    contract can evolve independently of what's required to write a record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
