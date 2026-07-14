class ExternalSearchError(Exception):
    """Base exception for literature-search provider failures."""


class SemanticScholarError(ExternalSearchError):
    """Raised when the Semantic Scholar API request fails or returns unusable data."""


class OpenAlexError(ExternalSearchError):
    """Raised when the OpenAlex API request fails or returns unusable data."""
