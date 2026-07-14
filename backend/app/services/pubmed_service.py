"""Literature search against PubMed via NCBI E-utilities.

This is the first stage of the pipeline: cast a reasonably wide net
(``pubmed_candidate_count`` candidates, sorted by PubMed's own relevance
ranking) so the AI re-ranking stage in ``ai_service`` has enough material
to do real comparative ranking instead of just re-sorting a top-10.
"""

from dataclasses import dataclass, field

import httpx

from app.core.config import settings

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


@dataclass
class Candidate:
    pubmed_id: str
    title: str
    authors: str
    journal: str
    year: int | None
    doi: str
    abstract: str
    keywords: list[str] = field(default_factory=list)


async def _esearch(client: httpx.AsyncClient, keyword: str, max_results: int) -> list[str]:
    params = {
        "db": "pubmed",
        "term": keyword,
        "retmax": max_results,
        "sort": "relevance",
        "retmode": "json",
        "email": settings.ncbi_email,
    }
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    resp = await client.get(ESEARCH_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("esearchresult", {}).get("idlist", [])


def _text(node, path: str) -> str:
    el = node.find(path)
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


async def _efetch(client: httpx.AsyncClient, ids: list[str]) -> list[Candidate]:
    if not ids:
        return []
    import xml.etree.ElementTree as ET

    params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "rettype": "abstract",
        "retmode": "xml",
        "email": settings.ncbi_email,
    }
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    resp = await client.get(EFETCH_URL, params=params, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    candidates: list[Candidate] = []
    for art in root.findall(".//PubmedArticle"):
        pmid_el = art.find(".//PMID")
        pmid = pmid_el.text.strip() if pmid_el is not None and pmid_el.text else ""
        if not pmid:
            continue

        title = _text(art, ".//ArticleTitle")

        authors = []
        for au in art.findall(".//Author"):
            last = au.find("LastName")
            initials = au.find("Initials")
            if last is not None and last.text:
                name = last.text
                if initials is not None and initials.text:
                    name += f" {initials.text}"
                authors.append(name)

        journal = _text(art, ".//Journal/Title")

        year = None
        year_el = art.find(".//JournalIssue/PubDate/Year")
        if year_el is None:
            year_el = art.find(".//JournalIssue/PubDate/MedlineDate")
        if year_el is not None and year_el.text:
            digits = "".join(c for c in year_el.text[:4] if c.isdigit())
            if len(digits) == 4:
                year = int(digits)

        doi = ""
        for id_el in art.findall(".//ArticleIdList/ArticleId"):
            if id_el.get("IdType") == "doi" and id_el.text:
                doi = id_el.text.strip()
                break

        abstract_parts = [
            "".join(a.itertext()).strip() for a in art.findall(".//AbstractText")
        ]
        abstract = " ".join(p for p in abstract_parts if p)

        keywords = [
            "".join(k.itertext()).strip()
            for k in art.findall(".//KeywordList/Keyword")
            if k is not None
        ]

        candidates.append(
            Candidate(
                pubmed_id=pmid,
                title=title,
                authors=", ".join(authors),
                journal=journal,
                year=year,
                doi=doi,
                abstract=abstract,
                keywords=[k for k in keywords if k],
            )
        )
    return candidates


async def search_candidates(keyword: str, max_results: int | None = None) -> list[Candidate]:
    """Search PubMed and return full bibliographic candidates for a keyword."""

    max_results = max_results or settings.pubmed_candidate_count
    async with httpx.AsyncClient() as client:
        ids = await _esearch(client, keyword, max_results)
        return await _efetch(client, ids)
