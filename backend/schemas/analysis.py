from pydantic import BaseModel, Field, model_validator


class AnalyzeRequest(BaseModel):
    """Input for AI paper analysis: a title plus either an abstract or full PDF text."""

    title: str = Field(..., min_length=1)
    abstract: str | None = Field(default=None, description="Paper abstract")
    pdf_text: str | None = Field(
        default=None, description="Full extracted PDF text, used when no abstract is available"
    )

    @model_validator(mode="after")
    def _require_content(self) -> "AnalyzeRequest":
        if not self.abstract and not self.pdf_text:
            raise ValueError("Provide either 'abstract' or 'pdf_text'")
        return self


class PaperAnalysis(BaseModel):
    """Structured battery-research metadata extracted by the AI analysis pipeline.

    Every field mirrors the requested JSON schema exactly. Descriptive
    fields are nullable (the model reports null rather than guessing when
    the source text doesn't mention something); list fields default to
    empty rather than null for easier consumption by callers.
    """

    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    battery_system: str | None = Field(
        default=None, description="Battery chemistry class, e.g. Li-ion, Li-metal, Na-ion, solid-state"
    )
    electrolyte: str | None = None
    salt: str | None = None
    solvent: str | None = None
    additive: str | None = None
    cathode: str | None = None
    anode: str | None = None
    separator: str | None = None
    cell_type: str | None = None
    voltage_window: str | None = None
    temperature: str | None = None
    formation_protocol: str | None = None
    cycle_condition: str | None = None
    rate_capability: str | None = None
    main_findings: list[str] = Field(default_factory=list)
    innovation: str | None = None
    advantages: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    future_work: list[str] = Field(default_factory=list)
