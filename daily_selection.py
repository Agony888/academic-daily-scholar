"""Selection strategy for the main Academic Daily Scholar workflow.

The main daily report should contain a fixed mix:
- 2 newest eligible papers from the three-year search pool.
- 3 papers from the same three-year pool that are closest to AI-assisted teaching,
  subject teaching with AI, and teacher digital/AI/data literacy.

This module intentionally keeps publication date as the primary criterion only
for the first two slots. The remaining slots are ranked by topic relevance.
"""

from __future__ import annotations

import logging

import filter as paper_filter
import search as search_module
from config import AppConfig
from utils import Paper

LATEST_TARGET = 2
RELEVANCE_TARGET = 3

SUBJECT_AI_SEARCH_QUERIES: tuple[str, ...] = (
    "AI assisted teaching education",
    "AI supported classroom teaching",
    "generative AI teaching education",
    "ChatGPT teaching education",
    "large language models teaching education",
    "AI assisted learning education",
    "AI assisted assessment education",
    "automated feedback education",
    "intelligent tutoring education",
    "adaptive learning education",
    "learning analytics education",
    "educational data mining education",
    "AI lesson planning teacher",
    "AI teaching design education",
    "AI curriculum education",
    "mathematics education artificial intelligence",
    "mathematics teaching artificial intelligence",
    "mathematics learning artificial intelligence",
    "math education generative AI school",
    "AI assisted mathematics teaching",
    "Chinese language education artificial intelligence",
    "Chinese language teaching artificial intelligence school",
    "Chinese writing instruction artificial intelligence",
    "language arts education artificial intelligence school",
    "native language education artificial intelligence",
    "first language writing instruction artificial intelligence",
    "reading education artificial intelligence school",
    "writing instruction artificial intelligence school",
    "English education artificial intelligence school",
    "English language teaching artificial intelligence",
    "EFL teaching artificial intelligence",
    "ESL teaching artificial intelligence",
    "AI assisted English learning school",
    "teacher digital literacy education",
    "teacher digital competence education",
    "teacher AI literacy education",
    "teacher data literacy education",
    "teacher education artificial intelligence integration",
    "preservice teachers artificial intelligence education",
    "in-service teachers artificial intelligence training",
    "teacher professional development artificial intelligence",
    "educational digital transformation teaching change",
    "artificial intelligence teacher role school education",
)

AI_TERMS: tuple[str, ...] = (
    "artificial intelligence",
    "ai in education",
    "generative ai",
    "genai",
    "chatgpt",
    "large language model",
    "large language models",
    "llm",
    "llms",
    "ai-assisted",
    "ai assisted",
    "ai-supported",
    "ai supported",
    "intelligent tutoring",
    "adaptive learning",
    "learning analytics",
    "educational data mining",
    "automated feedback",
)

TEACHING_TERMS: tuple[str, ...] = (
    "teaching",
    "instruction",
    "classroom",
    "lesson planning",
    "instructional design",
    "teaching design",
    "curriculum",
    "learning",
    "assessment",
    "feedback",
    "tutoring",
    "pedagogy",
    "pedagogical",
)

SUBJECT_TERMS: tuple[str, ...] = (
    "mathematics",
    "math",
    "english",
    "efl",
    "esl",
    "reading",
    "writing",
    "literacy",
    "language arts",
    "language education",
    "chinese language",
    "chinese writing",
    "native language",
    "first language",
    "mother tongue",
    "science",
    "stem",
    "subject teaching",
    "disciplinary",
)

TEACHER_LITERACY_TERMS: tuple[str, ...] = (
    "teacher digital literacy",
    "teacher digital competence",
    "teacher ai literacy",
    "teacher artificial intelligence literacy",
    "teacher intelligent literacy",
    "teacher data literacy",
    "digital literacy",
    "digital competence",
    "ai literacy",
    "artificial intelligence literacy",
    "intelligent literacy",
    "data literacy",
)

STAGE_TERMS: tuple[str, ...] = (
    "preschool",
    "early childhood",
    "kindergarten",
    "primary school",
    "primary education",
    "elementary school",
    "elementary education",
    "junior high",
    "middle school",
    "lower secondary",
    "basic education",
    "compulsory education",
    "k-12",
    "k12",
    "school education",
)


def configure_daily_search_queries() -> None:
    """Prepend subject-AI teaching queries to the shared search query list."""

    search_module.SEARCH_QUERIES = tuple(
        dict.fromkeys(SUBJECT_AI_SEARCH_QUERIES + search_module.SEARCH_QUERIES)
    )


def select_daily_papers(
    papers: list[Paper],
    config: AppConfig,
    logger: logging.Logger,
    whitelist: paper_filter.SsciWhitelist | None = None,
    exclude_identities: set[str] | None = None,
    ignore_seen: bool = False,
) -> list[Paper]:
    """Select 2 newest papers and 3 most AI-teaching-relevant papers."""

    whitelist = whitelist or paper_filter.load_ssci_whitelist(config.ssci_whitelist_path, logger)
    candidates = _eligible_candidates(
        papers,
        config,
        logger,
        whitelist,
        exclude_identities=exclude_identities,
        ignore_seen=ignore_seen,
    )

    latest_target = min(LATEST_TARGET, config.max_papers)
    relevance_target = min(RELEVANCE_TARGET, max(0, config.max_papers - latest_target))

    latest = sorted(candidates, key=_latest_sort_key, reverse=True)[:latest_target]
    latest_ids = {paper.identity for paper in latest}

    relevance_pool = [paper for paper in candidates if paper.identity not in latest_ids]
    relevance = sorted(relevance_pool, key=_ai_teaching_relevance_key, reverse=True)[:relevance_target]

    selected = latest + relevance
    selected_ids = {paper.identity for paper in selected}
    if len(selected) < config.max_papers:
        filler = [paper for paper in candidates if paper.identity not in selected_ids]
        filler.sort(key=_ai_teaching_relevance_key, reverse=True)
        selected.extend(filler[: config.max_papers - len(selected)])

    logger.info(
        "主日报混合筛选完成 input=%s kept=%s latest=%s relevance=%s selected=%s strategy=2_latest_plus_3_ai_teaching_relevance",
        len(papers),
        len(candidates),
        len(latest),
        len(relevance),
        len(selected),
    )
    return selected[: config.max_papers]


def _eligible_candidates(
    papers: list[Paper],
    config: AppConfig,
    logger: logging.Logger,
    whitelist: paper_filter.SsciWhitelist,
    *,
    exclude_identities: set[str] | None,
    ignore_seen: bool,
) -> list[Paper]:
    candidates: list[Paper] = []
    seen = set() if ignore_seen else paper_filter.load_seen_identities(config.seen_state_path)
    if exclude_identities:
        seen.update(exclude_identities)

    for paper in papers:
        ok, score, reasons = paper_filter._score_paper(paper, whitelist, config.ssci_filter_mode)  # type: ignore[attr-defined]
        use_whitelist = config.ssci_filter_mode != "off" and whitelist.available
        paper.ssci_matched = whitelist.is_match(paper) if use_whitelist else False
        if paper.ssci_matched:
            whitelist.apply_metadata(paper)
        elif not use_whitelist:
            paper.ssci_matched = False
            paper.ssci_categories = []
            paper.impact_factor = ""
            paper.quartile = ""
            paper.citescore = ""
            paper.publisher = ""
        paper.filter_score = score
        paper.filter_reasons = reasons
        if ok and paper.identity not in seen:
            candidates.append(paper)

    if not candidates:
        logger.warning("主日报混合筛选无候选，可能是SSCI白名单、主题规则或去重状态过严。")
    return candidates


def _latest_sort_key(paper: Paper) -> tuple[int, int, int, int]:
    return (
        paper.published_date.toordinal() if paper.published_date else 0,
        paper_filter._quartile_rank(paper.quartile),  # type: ignore[attr-defined]
        int(paper.ssci_matched),
        paper.filter_score,
    )


def _ai_teaching_relevance_key(paper: Paper) -> tuple[int, int, int, int, int, int, int, int]:
    text = _paper_text(paper)
    ai_hits = _count_hits(text, AI_TERMS)
    teaching_hits = _count_hits(text, TEACHING_TERMS)
    subject_hits = _count_hits(text, SUBJECT_TERMS)
    teacher_literacy_hits = _count_hits(text, TEACHER_LITERACY_TERMS)
    stage_hits = _count_hits(text, STAGE_TERMS)
    ai_teaching_synergy = int(ai_hits > 0 and teaching_hits > 0)
    subject_ai_synergy = int(ai_hits > 0 and subject_hits > 0)

    relevance_score = (
        ai_hits * 8
        + teaching_hits * 7
        + subject_hits * 6
        + teacher_literacy_hits * 5
        + stage_hits * 3
        + ai_teaching_synergy * 25
        + subject_ai_synergy * 20
        + paper.filter_score
    )
    return (
        relevance_score,
        subject_ai_synergy,
        ai_teaching_synergy,
        teacher_literacy_hits,
        stage_hits,
        int(paper.ssci_matched),
        paper_filter._quartile_rank(paper.quartile),  # type: ignore[attr-defined]
        paper.published_date.toordinal() if paper.published_date else 0,
    )


def _count_hits(text: str, terms: tuple[str, ...]) -> int:
    return sum(1 for term in terms if term in text)


def _paper_text(paper: Paper) -> str:
    return " ".join(
        [
            paper.title,
            paper.abstract,
            paper.journal,
            " ".join(paper.concepts),
            " ".join(paper.keywords),
        ]
    ).lower()
