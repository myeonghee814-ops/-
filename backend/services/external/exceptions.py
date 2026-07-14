class ExternalSearchError(Exception):
    """Base exception for literature-search provider failures."""


class SemanticScholarError(ExternalSearchError):
    """Raised when the Semantic Scholar API request fails or returns unusable data."""


class OpenAlexError(ExternalSearchError):
    """Raised when the OpenAlex API request fails or returns unusable data."""


class OpenAIAnalysisError(Exception):
    """Raised when the OpenAI Responses API request fails or returns unusable data.

    Deliberately not part of the ExternalSearchError hierarchy above — AI
    analysis and literature search are unrelated features that happen to
    both call third-party APIs from services/external/.
    """
