"""Topic, blacklist and SSCI whitelist filtering."""

from __future__ import annotations

import logging
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

from config import AppConfig
from utils import Paper, clean_text, normalize_issn, normalize_journal_name


INCLUDE_KEYWORDS: tuple[str, ...] = (
    "education",
    "educational technology",
    "mathematics education",
    "math education",
    "teacher education",
    "teacher professional development",
    "professional development",
    "teacher reflection",
    "reflective practice",
    "primary education",
    "elementary education",
    "primary school",
    "elementary school",
    "elementary mathematics",
    "primary mathematics",
    "digital competence",
    "digital literacy",
    "artificial intelligence in education",
    "ai in education",
    "generative ai",
    "large language model",
    "llm",
    "chatgpt",
    "copilot",
    "claude",
    "intelligent teaching",
    "lesson planning",
    "classroom teaching",
    "rural teacher",
    "智能教学",
    "智能备课",
    "课堂教学",
    "教师数字素养",
    "乡村教师",
    "小学数学",
)

STAGE_KEYWORDS: tuple[str, ...] = (
    "preschool",
    "pre-school",
    "early childhood",
    "kindergarten",
    "primary education",
    "primary school",
    "elementary education",
    "elementary school",
    "basic education",
    "k-12",
    "k12",
    "middle school",
    "junior high",
    "lower secondary",
    "secondary school",
    "school teacher",
    "school teachers",
    "school student",
    "school students",
    "children",
    "pupils",
)

AI_TEACHING_KEYWORDS: tuple[str, ...] = (
    "artificial intelligence",
    "ai in education",
    "generative ai",
    "genai",
    "large language model",
    "llm",
    "chatgpt",
    "copilot",
    "intelligent tutoring",
    "adaptive learning",
    "learning analytics",
    "educational data mining",
    "automated feedback",
    "ai-assisted",
    "ai supported",
    "lesson planning",
    "classroom assessment",
    "teaching analytics",
)

TEACHER_KEYWORDS: tuple[str, ...] = (
    "teacher digital literacy",
    "digital literacy",
    "digital competence",
    "ai literacy",
    "artificial intelligence literacy",
    "intelligent literacy",
    "data literacy",
    "teacher education",
    "pre-service teacher",
    "preservice teacher",
    "in-service teacher",
    "inservice teacher",
    "teacher training",
    "teacher professional development",
    "teacher role",
    "teacher agency",
    "technology integration",
    "digital transformation",
)

EMPIRICAL_KEYWORDS: tuple[str, ...] = (
    "empirical",
    "survey",
    "questionnaire",
    "interview",
    "focus group",
    "observation",
    "case study",
    "experiment",
    "quasi-experiment",
    "mixed methods",
    "qualitative",
    "quantitative",
    "regression",
    "structural equation",
    "sem",
    "pls-sem",
    "thematic analysis",
    "content analysis",
    "participants",
    "sample",
    "dataset",
    "data were collected",
    "we collected",
    "n =",
    "students",
    "teachers",
)

EXCLUDE_KEYWORDS: tuple[str, ...] = (
    "medicine",
    "medical",
    "clinical",
    "patient",
    "nursing",
    "pharmacology",
    "biomed",
    "biology",
    "biological",
    "cell",
    "genome",
    "protein",
    "materials",
    "material science",
    "mechanical",
    "manufacturing",
    "robot machining",
    "finance",
    "financial",
    "stock market",
    "portfolio",
    "vocational education",
    "technical and vocational",
    "tvet",
    "guest editorial",
    "editorial",
    "systematic review",
    "literature review",
    "bibliometric",
    "scoping review",
    "conceptual paper",
    "conceptual framework",
    "theoretical framework",
    "position paper",
    "higher education",  # handled with exception in _score_paper
    "higher education institution",
    "university student",
    "university students",
    "college student",
    "college students",
    "undergraduate student",
    "undergraduate students",
    "tertiary education",
    "材料",
    "医学",
    "生物",
    "机械",
    "金融",
)


@dataclass(slots=True)
class SsciWhitelist:
    journal_names: set[str] = field(default_factory=set)
    issns: set[str] = field(default_factory=set)
    journal_categories: dict[str, list[str]] = field(default_factory=dict)
    issn_categories: dict[str, list[str]] = field(default_factory=dict)
    source_path: Path | None = None

    @property
    def available(self) -> bool:
        return bool(self.journal_names or self.issns)

    def is_match(self, paper: Paper) -> bool:
        paper_issns = {normalize_issn(value) for value in paper.issns}
        paper_issns.discard("")
        if paper_issns & self.issns:
            return True

        journal = normalize_journal_name(paper.journal)
        if not journal:
            return False
        if journal in self.journal_names:
            return True
        return any(
            len(name) >= 10 and (name in journal or journal in name)
            for name in self.journal_names
        )

    def categories_for(self, paper: Paper) -> list[str]:
        categories: list[str] = []
        for issn in {normalize_issn(value) for value in paper.issns}:
            if issn and issn in self.issn_categories:
                categories.extend(self.issn_categories[issn])
        journal = normalize_journal_name(paper.journal)
        if journal in self.journal_categories:
            categories.extend(self.journal_categories[journal])
        if not categories and journal:
            for name, values in self.journal_categories.items():
                if len(name) >= 10 and (name in journal or journal in name):
                    categories.extend(values)
                    break
        return sorted(set(categories))


def load_ssci_whitelist(path: Path | None, logger: logging.Logger | None = None) -> SsciWhitelist:
    whitelist = SsciWhitelist(source_path=path)
    if not path:
        return whitelist
    if not path.exists():
        if logger:
            logger.warning("SSCI whitelist not found: %s", path)
        return whitelist
    if path.suffix.lower() != ".xlsx":
        if logger:
            logger.warning("Only .xlsx whitelist is supported by the built-in reader: %s", path)
        return whitelist

    try:
        rows = _read_xlsx_rows(path)
        names, issns, journal_categories, issn_categories = _extract_whitelist_values(rows)
        whitelist.journal_names = names
        whitelist.issns = issns
        whitelist.journal_categories = journal_categories
        whitelist.issn_categories = issn_categories
        if logger:
            logger.info("SSCI白名单加载成功 path=%s journals=%s issns=%s", path, len(names), len(issns))
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.exception("SSCI whitelist read failed: %s", exc)
    return whitelist


def filter_papers(
    papers: list[Paper],
    config: AppConfig,
    logger: logging.Logger,
    whitelist: SsciWhitelist | None = None,
) -> list[Paper]:
    whitelist = whitelist or load_ssci_whitelist(config.ssci_whitelist_path, logger)
    filtered: list[Paper] = []
    seen = _load_seen_identities(config.seen_state_path)

    for paper in papers:
        ok, score, reasons = _score_paper(paper, whitelist, config.ssci_filter_mode)
        paper.ssci_matched = whitelist.is_match(paper) if whitelist.available else False
        paper.ssci_categories = whitelist.categories_for(paper) if whitelist.available else []
        paper.filter_score = score
        paper.filter_reasons = reasons
        if ok and paper.identity not in seen:
            filtered.append(paper)

    filtered.sort(
        key=lambda p: (
            _quartile_rank(p.quartile),
            _recent_rank(p.published_date, config.search_months),
            p.ssci_matched,
            p.filter_score,
            p.published_date.toordinal() if p.published_date else 0,
        ),
        reverse=True,
    )
    selected = _select_common_theme(filtered, config.max_papers)
    logger.info(
        "筛选完成 input=%s kept=%s selected=%s whitelist_available=%s mode=%s",
        len(papers),
        len(filtered),
        len(selected),
        whitelist.available,
        config.ssci_filter_mode,
    )
    return selected


def mark_papers_seen(path: Path, papers: list[Paper]) -> None:
    seen = _load_seen_identities(path)
    seen.update(paper.identity for paper in papers)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")


def _score_paper(paper: Paper, whitelist: SsciWhitelist, mode: str) -> tuple[bool, int, list[str]]:
    text = " ".join(
        [
            paper.title,
            paper.abstract,
            paper.journal,
            " ".join(paper.concepts),
            " ".join(paper.keywords),
        ]
    ).lower()

    ssci_match = whitelist.is_match(paper) if whitelist.available else False
    if whitelist.available and not ssci_match:
        return False, -50, ["not_in_ssci_whitelist"]

    excluded = [kw for kw in EXCLUDE_KEYWORDS if kw.lower() in text]
    teacher_education_exception = any(
        allowed in text
        for allowed in (
            "teacher education",
            "pre-service teacher",
            "preservice teacher",
            "in-service teacher",
            "inservice teacher",
            "teacher training",
            "teacher professional development",
            "teacher educator",
        )
    )
    if teacher_education_exception:
        excluded = [
            kw
            for kw in excluded
            if kw
            not in {
                "higher education",
                "higher education institution",
                "tertiary education",
                "university student",
                "university students",
                "college student",
                "college students",
                "undergraduate student",
                "undergraduate students",
            }
        ]
    if excluded:
        return False, -100, [f"excluded:{kw}" for kw in excluded[:5]]

    reasons: list[str] = []
    score = 0
    matched_keywords = [kw for kw in INCLUDE_KEYWORDS if kw.lower() in text]
    if matched_keywords:
        score += min(20, len(matched_keywords) * 3)
        reasons.extend(f"keyword:{kw}" for kw in matched_keywords[:8])

    stage_hits = [kw for kw in STAGE_KEYWORDS if kw in text]
    ai_hits = [kw for kw in AI_TEACHING_KEYWORDS if kw in text]
    teacher_hits = [kw for kw in TEACHER_KEYWORDS if kw in text]
    empirical_hits = [kw for kw in EMPIRICAL_KEYWORDS if kw in text]

    if not stage_hits and not teacher_education_exception:
        return False, score, reasons + ["no_preschool_or_basic_education_stage"]
    if not ai_hits and not teacher_hits:
        return False, score, reasons + ["no_ai_or_teacher_literacy_theme"]
    if not empirical_hits:
        return False, score, reasons + ["no_empirical_data_signal"]

    score += 10 + min(15, len(stage_hits) * 3)
    score += min(20, len(ai_hits) * 4)
    score += min(20, len(teacher_hits) * 4)
    score += min(15, len(empirical_hits) * 3)

    if ssci_match:
        score += 30
        reasons.append("ssci_whitelist")
    reasons.extend(f"stage:{kw}" for kw in stage_hits[:4])
    reasons.extend(f"ai_theme:{kw}" for kw in ai_hits[:4])
    reasons.extend(f"teacher_theme:{kw}" for kw in teacher_hits[:4])
    reasons.extend(f"empirical:{kw}" for kw in empirical_hits[:4])

    if paper.language and paper.language.lower() not in {"en", "eng", "english"}:
        return False, score, reasons + [f"language:{paper.language}"]

    return True, score, reasons


def _read_xlsx_rows(path: Path) -> list[list[str]]:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: list[list[str]] = []

    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", ns):
                pieces = [t.text or "" for t in si.findall(".//a:t", ns)]
                shared_strings.append("".join(pieces))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rels = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels_root}
        for sheet in workbook.findall(".//a:sheet", ns):
            rid = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = rels.get(rid or "")
            if not target:
                continue
            sheet_path = _resolve_xlsx_target(target)
            if sheet_path not in names:
                continue
            sheet_root = ET.fromstring(archive.read(sheet_path))
            for row in sheet_root.findall(".//a:sheetData/a:row", ns):
                values: list[str] = []
                for cell in row.findall("a:c", ns):
                    values.append(_cell_value(cell, shared_strings, ns))
                if any(values):
                    rows.append(values)
    return rows


def _resolve_xlsx_target(target: str) -> str:
    normalized = target.replace("\\", "/")
    if normalized.startswith("/"):
        return normalized.lstrip("/")
    if normalized.startswith("xl/"):
        return normalized
    return "xl/" + normalized.lstrip("/")


def _cell_value(cell: ET.Element, shared_strings: list[str], ns: dict[str, str]) -> str:
    value_node = cell.find("a:v", ns)
    if value_node is None or value_node.text is None:
        inline = cell.find("a:is", ns)
        if inline is not None:
            return clean_text("".join(t.text or "" for t in inline.findall(".//a:t", ns)))
        return ""
    raw = value_node.text
    if cell.attrib.get("t") == "s":
        try:
            return clean_text(shared_strings[int(raw)])
        except (IndexError, ValueError):
            return ""
    return clean_text(raw)


def _extract_whitelist_values(rows: list[list[str]]) -> tuple[set[str], set[str], dict[str, list[str]], dict[str, list[str]]]:
    journal_names: set[str] = set()
    issns: set[str] = set()
    journal_categories: dict[str, list[str]] = {}
    issn_categories: dict[str, list[str]] = {}

    header: list[str] | None = None
    header_index = -1
    for idx, row in enumerate(rows[:20]):
        lowered = [cell.lower() for cell in row]
        if any(_is_journal_header(cell) or _is_issn_header(cell) for cell in lowered):
            header = lowered
            header_index = idx
            break

    if header:
        journal_cols = [i for i, cell in enumerate(header) if _is_journal_header(cell)]
        issn_cols = [i for i, cell in enumerate(header) if _is_issn_header(cell)]
        category_cols = [i for i, cell in enumerate(header) if "categor" in cell or "学科" in cell or "类别" in cell]
        for row in rows[header_index + 1 :]:
            row_categories: list[str] = []
            for idx in category_cols:
                if idx < len(row):
                    row_categories.extend(_split_categories(row[idx]))
            row_journals: list[str] = []
            row_issns: list[str] = []
            for idx in journal_cols:
                if idx < len(row):
                    name = _add_journal_name(row[idx], journal_names)
                    if name:
                        row_journals.append(name)
            for idx in issn_cols:
                if idx < len(row):
                    row_issns.extend(_add_issns(row[idx], issns))
            for name in row_journals:
                if row_categories:
                    journal_categories[name] = row_categories
            for issn in row_issns:
                if row_categories:
                    issn_categories[issn] = row_categories
    else:
        for row in rows:
            for cell in row:
                _add_issns(cell, issns)
                _add_journal_name(cell, journal_names)

    return journal_names, issns, journal_categories, issn_categories


def _is_journal_header(cell: str) -> bool:
    return any(term in cell for term in ("journal", "source title", "刊名", "期刊", "title"))


def _is_issn_header(cell: str) -> bool:
    return "issn" in cell


def _add_issns(value: str, target: set[str]) -> list[str]:
    added: list[str] = []
    for match in re.findall(r"\b\d{4}-?\d{3}[\dXx]\b", value):
        normalized = normalize_issn(match)
        if normalized:
            target.add(normalized)
            added.append(normalized)
    return added


def _add_journal_name(value: str, target: set[str]) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return ""
    if len(text) < 4 or len(text) > 180:
        return ""
    lowered = text.lower()
    blocked = {
        "issn",
        "eissn",
        "journal",
        "source title",
        "title",
        "category",
        "quartile",
        "year",
        "publisher",
        "ssci",
        "sci",
    }
    if lowered in blocked:
        return ""
    if re.search(r"\b\d{4}-?\d{3}[\dXx]\b", text):
        return ""
    normalized = normalize_journal_name(text)
    if normalized and len(normalized) >= 4:
        target.add(normalized)
        return normalized
    return ""


def _split_categories(value: str) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"\s*\|\s*|;\s*|,\s*", text) if part.strip()]


def _load_seen_identities(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if isinstance(data, list):
        return {str(item) for item in data}
    if isinstance(data, dict):
        return {str(item) for item in data.get("seen", [])}
    return set()


def _quartile_rank(quartile: str) -> int:
    value = quartile.strip().upper()
    if value == "Q1":
        return 4
    if value == "Q2":
        return 3
    if value == "Q3":
        return 2
    if value == "Q4":
        return 1
    return 0


def _recent_rank(published: date | None, months: int) -> int:
    if not published:
        return 0
    return 1 if published >= date.today() - timedelta(days=max(1, months) * 31) else 0


def _theme_bucket(paper: Paper) -> str:
    text = " ".join([paper.title, paper.abstract, " ".join(paper.keywords), " ".join(paper.concepts)]).lower()
    if any(term in text for term in ("generative ai", "chatgpt", "large language model", "llm")):
        return "generative_ai"
    if any(term in text for term in ("digital literacy", "digital competence", "data literacy", "ai literacy")):
        return "teacher_literacy"
    if any(term in text for term in ("teacher education", "pre-service", "preservice", "in-service", "teacher training")):
        return "teacher_education"
    if any(term in text for term in ("learning analytics", "educational data mining", "adaptive learning")):
        return "data_ai_learning"
    return "ai_teaching"


def _select_common_theme(papers: list[Paper], max_papers: int) -> list[Paper]:
    if len(papers) <= max_papers:
        return papers
    buckets: dict[str, list[Paper]] = {}
    for paper in papers:
        buckets.setdefault(_theme_bucket(paper), []).append(paper)
    dominant = max(buckets.values(), key=len)
    selected = dominant[:max_papers]
    if len(selected) < max_papers:
        selected_ids = {paper.identity for paper in selected}
        selected.extend(paper for paper in papers if paper.identity not in selected_ids)
    return selected[:max_papers]
