"""Unit tests for pdf_extract.py - the on-demand PDF download + section-
splitting used by the "자세히 분석" deep-analysis flow. The PDF download
(httpx) and parsing (pypdf.PdfReader) are both mocked - no network access,
no real PDF file needed - so these test only our own post-processing logic
(reference-section splitting, caption detection, scanned-PDF detection).
"""

import asyncio

import httpx
import pytest

from app.services import pdf_extract


class _FakePage:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakeReader:
    def __init__(self, pages_text: list[str]):
        self.pages = [_FakePage(t) for t in pages_text]


class _FakeAsyncClientCM:
    """Stands in for `async with httpx.AsyncClient(...) as client`."""

    def __init__(self, client):
        self._client = client

    async def __aenter__(self):
        return self._client

    async def __aexit__(self, *exc_info):
        return False


def _install_fake_download(monkeypatch, content: bytes = b"%PDF-fake-bytes%", raise_error: Exception | None = None):
    async def _fake_get(url, timeout=None):
        if raise_error is not None:
            raise raise_error
        return httpx.Response(200, content=content, request=httpx.Request("GET", url))

    fake_client = type("FakeClient", (), {"get": staticmethod(_fake_get)})()
    mock_client_cls = lambda *a, **kw: _FakeAsyncClientCM(fake_client)
    monkeypatch.setattr(pdf_extract.httpx, "AsyncClient", mock_client_cls)


def _install_fake_reader(monkeypatch, pages_text: list[str]):
    monkeypatch.setattr(pdf_extract, "PdfReader", lambda buf: _FakeReader(pages_text))


def test_download_and_extract_splits_body_from_references(monkeypatch):
    monkeypatch.setattr(pdf_extract, "_MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER", 10)
    _install_fake_download(monkeypatch)
    _install_fake_reader(
        monkeypatch,
        [
            "Introduction text.\nFigure 1. Cycling performance improves with FEC.\nMore body text.",
            "References\n[1] Some citation.\n[2] Another citation.",
        ],
    )

    result = asyncio.run(pdf_extract.download_and_extract("https://example.com/paper.pdf"))

    assert "Introduction text." in result.body_text
    assert "More body text." in result.body_text
    assert "[1] Some citation." not in result.body_text
    assert "References" not in result.body_text


def test_download_and_extract_finds_the_last_references_heading(monkeypatch):
    """An in-text mention like '... see references' must not be mistaken
    for the actual References section heading - only a standalone heading
    line counts, and the search goes from the end so the real section
    (always last) wins over any earlier false positive."""

    monkeypatch.setattr(pdf_extract, "_MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER", 10)
    _install_fake_download(monkeypatch)
    _install_fake_reader(
        monkeypatch,
        [
            "For more detail see references [3,4] discussed later.\nBody continues here.",
            "References\n[1] Citation one.",
        ],
    )

    result = asyncio.run(pdf_extract.download_and_extract("https://example.com/paper.pdf"))

    assert "see references [3,4]" in result.body_text
    assert "Body continues here." in result.body_text
    assert "[1] Citation one." not in result.body_text


def test_download_and_extract_collects_figure_and_table_captions(monkeypatch):
    monkeypatch.setattr(pdf_extract, "_MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER", 10)
    _install_fake_download(monkeypatch)
    _install_fake_reader(
        monkeypatch,
        [
            "Body text.\nFigure 1. Cycling performance.\nMore text.\nTable 2: Summary of results.\nEnd."
        ],
    )

    result = asyncio.run(pdf_extract.download_and_extract("https://example.com/paper.pdf"))

    assert result.candidate_figure_captions == [
        "Figure 1. Cycling performance.",
        "Table 2: Summary of results.",
    ]


def test_download_and_extract_raises_for_scanned_pdf_with_no_text_layer(monkeypatch):
    _install_fake_download(monkeypatch)
    _install_fake_reader(monkeypatch, ["", ""])

    with pytest.raises(pdf_extract.PdfExtractionError):
        asyncio.run(pdf_extract.download_and_extract("https://example.com/scanned.pdf"))


def test_download_and_extract_wraps_download_failure(monkeypatch):
    _install_fake_download(monkeypatch, raise_error=httpx.ConnectTimeout("timed out"))

    with pytest.raises(pdf_extract.PdfExtractionError):
        asyncio.run(pdf_extract.download_and_extract("https://example.com/unreachable.pdf"))


def test_download_and_extract_rejects_oversized_pdf(monkeypatch):
    _install_fake_download(monkeypatch, content=b"x" * (pdf_extract._MAX_PDF_BYTES + 1))

    with pytest.raises(pdf_extract.PdfExtractionError):
        asyncio.run(pdf_extract.download_and_extract("https://example.com/huge.pdf"))
