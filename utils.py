"""Shared data models and utility helpers for Academic Daily Scholar."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence, TypeVar
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


T = TypeVar("T")


@dataclass(slots=True)
class Paper:
    """Normalized scholarly paper metadata."""

    title: str
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    published_date: date | None = None
    journal: str = ""
    doi: str = ""
    url: str = ""
    source: str = ""
    language: str = "en"
    issns: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    ssci_matched: bool = False
    ssci_categories: list[str] = field(default_factory=list)
    quartile: str = ""
    impact_factor: str = ""
    filter_score: int = 0
    filter_reasons: list[str] = field(default_factory=list)

    @property
    def identity(self) -> str:
        if self.doi:
            return normalize_doi(self.doi)
        basis = "|".join([self.title, self.journal, self.url])
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["published_date"] = self.published_date.isoformat() if self.published_date else ""
        return data


@dataclass(slots=True)
class PaperSummary:
    """Chinese AI-generated summary for one paper."""

    chinese_title: str
    authors_text: str = ""
    journal_impact: str = ""
    volume_issue_doi: str = ""
    online_date: str = ""
    research_abstract: str = ""
    main_content: str = ""
    argument: str = ""
    research_question: str = ""
    methods: str = ""
    findings: str = ""
    implications_teacher_education: str = ""
    apa_citation: str = ""
    one_sentence: str = ""
    background: str = ""
    participants: str = ""
    novelty: str = ""
    limitations: str = ""
    implications_primary_math: str = ""
    thesis_relevance: str = ""
    raw_text: str = ""

    @classmethod
    def empty(cls, title: str, reason: str) -> "PaperSummary":
        return cls(
            chinese_title=title,
            authors_text="未生成。",
            journal_impact="未生成。",
            volume_issue_doi="未生成。",
            online_date="未生成。",
            research_abstract=f"摘要生成失败：{reason}",
            main_content="未生成。",
            argument="未生成。",
            research_question="未生成。",
            methods="未生成。",
            findings="未生成。",
            implications_teacher_education="未生成。",
            apa_citation="未生成。",
            one_sentence=f"摘要生成失败：{reason}",
            raw_text=reason,
        )


@dataclass(slots=True)
class ReportItem:
    paper: Paper
    summary: PaperSummary


@dataclass(slots=True)
class DailyReport:
    report_date: date
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    total_found: int
    total_filtered: int
    total_success: int
    total_failed: int
    api_elapsed_seconds: float
    hotspot_summary: str
    items: list[ReportItem]
    markdown_path: Path | None = None
    word_path: Path | None = None


def clean_text(value: str | None) -> str:
    """Normalize whitespace and remove control characters."""

    if not value:
        return ""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def html_to_text(value: str | None) -> str:
    """Convert publisher/Crossref abstract HTML or JATS snippets to plain text."""

    if not value:
        return ""
    soup = BeautifulSoup(value, "lxml")
    return clean_text(soup.get_text(" ", strip=True))


def normalize_doi(value: str | None) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text)
    text = re.sub(r"^doi:\s*", "", text)
    return text.strip()


def normalize_issn(value: str | None) -> str:
    text = clean_text(value).upper()
    match = re.search(r"\b\d{4}-?\d{3}[\dX]\b", text)
    if not match:
        return ""
    raw = match.group(0).replace("-", "")
    return f"{raw[:4]}-{raw[4:]}"


def normalize_journal_name(value: str | None) -> str:
    text = clean_text(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b(the|and)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(value: Any) -> date | None:
    """Parse common API date formats into a date."""

    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        try:
            parts = [int(x) for x in value if x is not None]
        except (TypeError, ValueError):
            return None
        if len(parts) >= 3:
            return date(parts[0], parts[1], parts[2])
        if len(parts) == 2:
            return date(parts[0], parts[1], 1)
        if len(parts) == 1:
            return date(parts[0], 1, 1)
        return None
    text = clean_text(str(value))
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y/%m", "%Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date()
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(text).date()
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def request_json(
    session: requests.Session,
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: int = 30,
    retries: int = 3,
    backoff_seconds: float = 2.0,
) -> dict[str, Any]:
    """GET JSON with retry, timeout and polite headers."""

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(backoff_seconds * attempt)
    raise RuntimeError(f"Failed to fetch JSON from {url}: {last_error}") from last_error


def retry_call(
    func: Callable[[], T],
    *,
    retries: int = 3,
    backoff_seconds: float = 2.0,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Run a callable with simple linear backoff."""

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return func()
        except retry_exceptions as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(backoff_seconds * attempt)
    assert last_error is not None
    raise last_error


def truncate_text(text: str, max_chars: int) -> str:
    text = clean_text(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def unique_by_identity(papers: Iterable[Paper]) -> list[Paper]:
    seen: set[str] = set()
    unique: list[Paper] = []
    for paper in papers:
        key = paper.identity
        if key in seen:
            continue
        seen.add(key)
        unique.append(paper)
    return unique


def write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def safe_json_loads(text: str) -> dict[str, Any] | None:
    """Parse direct or fenced JSON emitted by an LLM."""

    cleaned = clean_text(text)
    if not cleaned:
        return None
    candidates = [cleaned]
    fenced = re.search(r"\x60\x60\x60(?:json)?\s*(\{.*?\})\s*\x60\x60\x60", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.insert(0, fenced.group(1))
    object_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if object_match:
        candidates.append(object_match.group(0))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return None


def format_date_cn(value: date | None) -> str:
    return value.isoformat() if value else "未知日期"


def doi_url(doi: str | None) -> str:
    normalized = normalize_doi(doi)
    return f"https://doi.org/{normalized}" if normalized else ""


def google_scholar_url(title: str) -> str:
    return "https://scholar.google.com/scholar?q=" + quote_plus(clean_text(title))


def researchgate_url(title: str) -> str:
    return "https://www.researchgate.net/search/publication?q=" + quote_plus(clean_text(title))
