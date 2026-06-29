"""Literature retrieval using OpenAlex, Crossref and ERIC.

Semantic Scholar is intentionally not used.
"""

from __future__ import annotations

import logging
import html
from datetime import date, datetime
from typing import Any

import requests

from config import AppConfig
from utils import (
    Paper,
    clean_text,
    html_to_text,
    parse_date,
    request_json,
    unique_by_identity,
)


OPENALEX_ENDPOINT = "https://api.openalex.org/works"
CROSSREF_ENDPOINT = "https://api.crossref.org/works"
ERIC_ENDPOINT = "https://api.ies.ed.gov/eric/"


SEARCH_QUERIES: tuple[str, ...] = (
    "artificial intelligence teaching preschool education empirical",
    "artificial intelligence teaching primary education empirical",
    "artificial intelligence teaching elementary education empirical",
    "artificial intelligence teaching secondary education empirical",
    "digital technology teaching primary education empirical",
    "educational technology teacher professional development school",
    "learning analytics teacher education school empirical",
    "AI assessment primary education teacher empirical",
    "teacher beliefs AI education school empirical",
    "teacher digital competence primary school empirical",
    "teacher digital literacy elementary school empirical",
    "data literacy teachers school education empirical",
    "technology integration elementary teachers empirical",
    "digital transformation basic education teacher role empirical",
    "AI supported learning elementary education teacher empirical",
    "intelligent tutoring primary education teacher empirical",
    "adaptive learning basic education teacher empirical",
    "generative AI lesson planning teachers school",
    "ChatGPT teacher education preservice teachers empirical",
    "generative AI classroom teaching school teachers empirical",
    "ChatGPT school education teacher empirical study",
    "teacher digital literacy artificial intelligence school education",
    "teacher AI literacy K-12 education empirical",
    "teacher data literacy digital education empirical",
    "teacher education artificial intelligence integration preservice teachers",
    "pre-service teacher training artificial intelligence education",
    "in-service teacher professional development AI digital transformation",
    "educational digital transformation teacher role school education",
    "AI lesson planning classroom assessment teacher education empirical",
)


def search_recent_papers(
    config: AppConfig,
    window_start: datetime,
    window_end: datetime,
    logger: logging.Logger,
) -> list[Paper]:
    """Fetch recent English journal articles from OpenAlex and Crossref."""

    session = requests.Session()
    headers = {"User-Agent": config.user_agent}
    papers: list[Paper] = []

    for query in SEARCH_QUERIES:
        try:
            papers.extend(_search_openalex(config, session, headers, query, window_start, window_end, logger))
        except Exception as exc:  # noqa: BLE001 - keep daily job alive
            logger.exception("OpenAlex search failed for query=%s: %s", query, exc)
        try:
            papers.extend(_search_crossref(config, session, headers, query, window_start, window_end, logger))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Crossref search failed for query=%s: %s", query, exc)
        try:
            papers.extend(_search_eric(config, session, headers, query, window_start, window_end, logger))
        except Exception as exc:  # noqa: BLE001
            logger.exception("ERIC search failed for query=%s: %s", query, exc)

    unique = unique_by_identity(papers)
    unique.sort(key=lambda p: p.published_date or date.min, reverse=True)
    logger.info("检索数量 total=%s unique=%s", len(papers), len(unique))
    return unique[: max(config.max_papers * 80, 200)]


def _search_openalex(
    config: AppConfig,
    session: requests.Session,
    headers: dict[str, str],
    query: str,
    window_start: datetime,
    window_end: datetime,
    logger: logging.Logger,
) -> list[Paper]:
    params = {
        "search": query,
        "filter": ",".join(
            [
                "type:article",
                "language:en",
                f"from_publication_date:{window_start.date().isoformat()}",
                f"to_publication_date:{window_end.date().isoformat()}",
            ]
        ),
        "sort": "publication_date:desc",
        "per-page": min(50, max(25, config.max_papers * 10)),
        "mailto": "agony2023@qq.com",
    }
    if config.openalex_api_key:
        params["api_key"] = config.openalex_api_key
    data = request_json(
        session,
        OPENALEX_ENDPOINT,
        params=params,
        headers=headers,
        timeout=config.request_timeout_seconds,
        retries=config.request_retries,
    )
    results = data.get("results", [])
    papers = [_openalex_to_paper(item) for item in results if isinstance(item, dict)]
    papers = [paper for paper in papers if _within_window_by_date(paper.published_date, window_start, window_end)]
    logger.info("OpenAlex query=%r count=%s", query, len(papers))
    return papers


def _openalex_to_paper(item: dict[str, Any]) -> Paper:
    primary_location = item.get("primary_location") or {}
    source = primary_location.get("source") or {}
    best_oa = item.get("best_oa_location") or {}

    doi = clean_text(item.get("doi", ""))
    landing_url = clean_text(primary_location.get("landing_page_url") or best_oa.get("landing_page_url") or item.get("id") or "")
    journal = clean_text(source.get("display_name", ""))
    issns = [clean_text(x) for x in (source.get("issn") or []) if clean_text(x)]
    if source.get("issn_l"):
        issns.append(clean_text(source["issn_l"]))

    authors: list[str] = []
    for authorship in item.get("authorships") or []:
        author = authorship.get("author") or {}
        name = clean_text(author.get("display_name"))
        if name:
            authors.append(name)

    concepts = [clean_text(c.get("display_name")) for c in item.get("concepts") or [] if clean_text(c.get("display_name"))]
    keywords = [clean_text(k.get("display_name")) for k in item.get("keywords") or [] if clean_text(k.get("display_name"))]

    return Paper(
        title=clean_text(item.get("display_name", "")),
        abstract=_reconstruct_openalex_abstract(item.get("abstract_inverted_index")),
        authors=authors,
        published_date=parse_date(item.get("publication_date")),
        journal=journal,
        doi=doi,
        url=landing_url,
        source="OpenAlex",
        language=clean_text(item.get("language", "en")) or "en",
        issns=issns,
        concepts=concepts,
        keywords=keywords,
        raw={"openalex_id": item.get("id"), "publication_year": item.get("publication_year")},
    )


def _reconstruct_openalex_abstract(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    positions: dict[int, str] = {}
    for word, indexes in index.items():
        for idx in indexes:
            positions[int(idx)] = word
    return clean_text(" ".join(positions[i] for i in sorted(positions)))


def _search_crossref(
    config: AppConfig,
    session: requests.Session,
    headers: dict[str, str],
    query: str,
    window_start: datetime,
    window_end: datetime,
    logger: logging.Logger,
) -> list[Paper]:
    params = {
        "query.bibliographic": query,
        "filter": ",".join(
            [
                "type:journal-article",
                f"from-pub-date:{window_start.date().isoformat()}",
                f"until-pub-date:{window_end.date().isoformat()}",
            ]
        ),
        "sort": "published",
        "order": "desc",
        "rows": min(50, max(25, config.max_papers * 10)),
        "mailto": "agony2023@qq.com",
    }
    data = request_json(
        session,
        CROSSREF_ENDPOINT,
        params=params,
        headers=headers,
        timeout=config.request_timeout_seconds,
        retries=config.request_retries,
    )
    items = (data.get("message") or {}).get("items") or []
    papers = [_crossref_to_paper(item) for item in items if isinstance(item, dict)]
    papers = [paper for paper in papers if _within_window_by_date(paper.published_date, window_start, window_end)]
    logger.info("Crossref query=%r count=%s", query, len(papers))
    return papers


def _crossref_to_paper(item: dict[str, Any]) -> Paper:
    title = clean_text(" ".join(item.get("title") or []))
    abstract = html_to_text(item.get("abstract", ""))
    journal = clean_text(" ".join(item.get("container-title") or []))
    url = clean_text(item.get("URL", ""))
    doi = clean_text(item.get("DOI", ""))
    date_parts = (
        (item.get("published-print") or {}).get("date-parts")
        or (item.get("published-online") or {}).get("date-parts")
        or (item.get("published") or {}).get("date-parts")
        or []
    )


def _search_eric(
    config: AppConfig,
    session: requests.Session,
    headers: dict[str, str],
    query: str,
    window_start: datetime,
    window_end: datetime,
    logger: logging.Logger,
) -> list[Paper]:
    params = {
        "search": query,
        "format": "json",
        "start": 0,
        "rows": min(50, max(25, config.max_papers * 10)),
    }
    data = request_json(
        session,
        ERIC_ENDPOINT,
        params=params,
        headers=headers,
        timeout=config.request_timeout_seconds,
        retries=config.request_retries,
    )
    docs = _extract_eric_docs(data)
    papers = [_eric_to_paper(item) for item in docs if isinstance(item, dict)]
    papers = [paper for paper in papers if _within_window_by_date(paper.published_date, window_start, window_end)]
    logger.info("ERIC query=%r count=%s", query, len(papers))
    return papers


def _extract_eric_docs(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("docs", "results", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    response = data.get("response")
    if isinstance(response, dict) and isinstance(response.get("docs"), list):
        return response["docs"]
    return []


def _eric_to_paper(item: dict[str, Any]) -> Paper:
    title = _first_text(item, "title", "title_s", "title_display")
    abstract = _first_text(item, "description", "abstract", "abstract_s")
    journal = _first_text(item, "source", "source_s", "journal", "publication")
    doi = _first_text(item, "doi", "doi_s")
    url = _first_text(item, "url", "url_s", "eric_url")
    eric_id = _first_text(item, "id", "ericNumber", "eric_number")
    if not url and eric_id:
        url = f"https://eric.ed.gov/?id={eric_id}"
    published = parse_date(
        _first_text(item, "publicationdateyear", "publicationDate", "publication_date", "year", "date")
    )
    authors_raw = item.get("author") or item.get("authors") or item.get("author_s") or []
    if isinstance(authors_raw, str):
        authors = [clean_text(part) for part in authors_raw.split(";") if clean_text(part)]
    elif isinstance(authors_raw, list):
        authors = [clean_text(str(part)) for part in authors_raw if clean_text(str(part))]
    else:
        authors = []
    descriptors = item.get("descriptor") or item.get("descriptors") or item.get("subject") or []
    if isinstance(descriptors, str):
        keywords = [clean_text(part) for part in descriptors.split(";") if clean_text(part)]
    elif isinstance(descriptors, list):
        keywords = [clean_text(str(part)) for part in descriptors if clean_text(str(part))]
    else:
        keywords = []
    issn = _first_text(item, "issn", "issn_s")
    return Paper(
        title=title,
        abstract=abstract,
        authors=authors,
        published_date=published,
        journal=journal,
        doi=doi,
        url=url,
        source="ERIC",
        language="en",
        issns=[issn] if issn else [],
        concepts=keywords,
        keywords=keywords,
        raw={"eric_id": eric_id},
    )


def _first_text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, list) and value:
            return clean_text(html.unescape(str(value[0])))
        if value:
            return clean_text(html.unescape(str(value)))
    return ""
    published = parse_date(date_parts[0] if date_parts else None)
    authors: list[str] = []
    for author in item.get("author") or []:
        given = clean_text(author.get("given"))
        family = clean_text(author.get("family"))
        name = clean_text(" ".join([given, family]))
        if name:
            authors.append(name)

    issns = [clean_text(x) for x in item.get("ISSN") or [] if clean_text(x)]
    subjects = [clean_text(x) for x in item.get("subject") or [] if clean_text(x)]

    return Paper(
        title=title,
        abstract=abstract,
        authors=authors,
        published_date=published,
        journal=journal,
        doi=doi,
        url=url,
        source="Crossref",
        language=clean_text(item.get("language", "en")) or "en",
        issns=issns,
        concepts=subjects,
        keywords=subjects,
        raw={"publisher": item.get("publisher"), "type": item.get("type")},
    )


def _within_window_by_date(published: date | None, window_start: datetime, window_end: datetime) -> bool:
    """Publisher APIs often expose publication date without time; enforce the daily date window."""

    if published is None:
        return True
    return window_start.date() <= published <= window_end.date()


def _within_publication_years(published: date | None, window_end: datetime, years: int) -> bool:
    if published is None:
        return True
    start = window_end.replace(year=window_end.year - years).date()
    return start <= published <= window_end.date()
