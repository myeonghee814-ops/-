"""Downloads an open-access PDF and extracts structured text from it, for the
on-demand "자세히 분석" deep-analysis flow. Abstract-only extraction
(ai_service.extract_battery_analysis) can't recover experiment-level detail
that only lives in the paper's body (exact electrolyte composition, voltage
window, cell type) - this fetches the actual PDF text so Gemini has that
detail to work with.

The section-splitting heuristics below (references-heading detection,
figure/table caption detection, scanned-PDF detection) are ported from the
battery-paper-summarizer sibling project's pdfExtract.ts, which already
solved this exact problem for locally-uploaded PDFs. Only the input source
(a remote URL here, vs. a browser File there) and the extraction library
(pypdf, not pdfjs-dist - this runs server-side, not in a browser) differ.
"""

import re
from dataclasses import dataclass
from io import BytesIO

import httpx
from pypdf import PdfReader

# Below this many characters per page, assume the PDF has no real text layer
# (a scanned image) - matches pdfExtract.ts's MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER.
_MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER = 200

# Heading line marking the start of the References/Bibliography section.
_REFERENCES_HEADING_RE = re.compile(r"^\s*(references|bibliography|works cited)\s*$", re.IGNORECASE)

# Candidate figure/table caption lines, e.g. "Figure 2.", "Fig. 3:", "Table 1."
_CAPTION_LINE_RE = re.compile(r"^\s*(fig(?:ure)?|table)\.?\s*[sS]?\d+[a-z]?\s*[:.]", re.IGNORECASE)

_DOWNLOAD_TIMEOUT_SECONDS = 30.0
# A generous cap against an unexpectedly huge or non-PDF response.
_MAX_PDF_BYTES = 30 * 1024 * 1024

# Some open-access hosts (arXiv, institutional repositories) 403 a request
# with no User-Agent at all, treating it as an obvious bot - a normal
# browser UA avoids that specific case. It does NOT get through
# Cloudflare-style bot-detection some publishers (Wiley, MDPI, ...) put in
# front of their own "open access" PDF links - that's a hard 403 either way,
# which is why PdfExtractionError below is a normal, expected outcome for a
# meaningful fraction of real openAccessPdf.url values, not a bug.
_DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


class PdfExtractionError(RuntimeError):
    """Raised when the PDF can't be downloaded, isn't a PDF, or has no
    extractable text (e.g. a scanned paper with no text layer)."""


@dataclass
class ExtractedPaper:
    body_text: str
    candidate_figure_captions: list[str]


async def download_and_extract(pdf_url: str) -> ExtractedPaper:
    try:
        async with httpx.AsyncClient(follow_redirects=True, headers=_DOWNLOAD_HEADERS) as client:
            resp = await client.get(pdf_url, timeout=_DOWNLOAD_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise PdfExtractionError(f"PDF를 다운로드할 수 없습니다: {exc}") from exc

    content = resp.content
    if len(content) > _MAX_PDF_BYTES:
        raise PdfExtractionError("PDF 파일이 너무 큽니다 (30MB 초과).")

    try:
        reader = PdfReader(BytesIO(content))
        page_texts = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pypdf raises a variety of its own error types
        raise PdfExtractionError(f"PDF를 읽을 수 없습니다: {exc}") from exc

    num_pages = len(page_texts) or 1
    full_text = "\n".join(page_texts)
    avg_chars_per_page = len(full_text) / num_pages
    if avg_chars_per_page < _MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER:
        raise PdfExtractionError("PDF에서 텍스트를 추출할 수 없습니다 (스캔본으로 추정됩니다).")

    lines = full_text.split("\n")

    # Search from the end: the references heading should be the *last*
    # standalone occurrence (avoids matching an in-text citation like
    # "... see references").
    split_at = -1
    for i in range(len(lines) - 1, -1, -1):
        if _REFERENCES_HEADING_RE.match(lines[i]):
            split_at = i
            break

    body_lines = lines[:split_at] if split_at >= 0 else lines
    candidate_captions = [line.strip() for line in body_lines if _CAPTION_LINE_RE.match(line)]

    return ExtractedPaper(
        body_text="\n".join(body_lines).strip(),
        candidate_figure_captions=candidate_captions,
    )
