"""Dedicated AI-prioritized education literature push.

This entrypoint reuses the main Academic Daily Scholar pipeline, but gives
priority to papers that combine AI with education, subject teaching, AI-assisted
instruction, AI-assisted learning, AI-supported assessment, or teacher
development. AI + education is preferred, not required. It keeps a three-year
search window, a separate seen-state file, and standardized output file names.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import filter as paper_filter
import html_generator
import mailer
import main as daily_main
import markdown_generator
import search as search_module
from config import ConfigError
from utils import DailyReport, Paper, write_text_file

AI_TITLE = "AI教育优先专题文献推送"
AI_FILE_SUFFIX = "AI教育专题文献推送"
AI_SUBJECT = "【AI教育优先专题文献推送】"

AI_PRIORITY_SEARCH_QUERIES: tuple[str, ...] = (
    "artificial intelligence education",
    "AI education",
    "generative AI education",
    "ChatGPT education",
    "large language models education",
    "AI assisted teaching",
    "AI assisted learning",
    "AI supported teaching",
    "AI supported learning",
    "AI assisted assessment education",
    "automated feedback education",
    "intelligent tutoring education",
    "adaptive learning education",
    "learning analytics education",
    "educational data mining",
    "teacher artificial intelligence education",
    "teacher AI literacy",
    "teacher education artificial intelligence",
    "teacher professional development artificial intelligence",
    "AI lesson planning teacher",
    "AI classroom assessment teacher",
    "AI teaching design education",
    "AI curriculum education",
    "mathematics education artificial intelligence",
    "mathematics teaching artificial intelligence",
    "mathematics learning artificial intelligence",
    "science education artificial intelligence",
    "science teaching artificial intelligence",
    "language education artificial intelligence",
    "English education artificial intelligence",
    "reading education artificial intelligence",
    "writing instruction artificial intelligence",
    "STEM education artificial intelligence",
    "K-12 artificial intelligence education",
    "primary education artificial intelligence",
    "elementary education artificial intelligence",
    "school education artificial intelligence",
    "classroom teaching artificial intelligence",
    "digital education artificial intelligence",
    "educational technology artificial intelligence",
)

_ORIGINAL_SCORE_PAPER = paper_filter._score_paper  # type: ignore[attr-defined]
_ORIGINAL_BUILD_MARKDOWN = markdown_generator.build_markdown
_ORIGINAL_GENERATE_DOCX_FROM_MARKDOWN = markdown_generator.generate_docx_from_markdown
_ORIGINAL_GENERATE_HTML = html_generator.generate_html
_ORIGINAL_SEARCH_QUERIES = search_module.SEARCH_QUERIES


def configure_ai_education_defaults() -> None:
    """Set runtime defaults for the dedicated AI-prioritized education push."""

    os.environ.setdefault("PRIMARY_SEARCH_DAYS", "1095")
    os.environ.setdefault("FALLBACK_SEARCH_YEARS", "3")
    os.environ.setdefault("SEARCH_MONTHS", "36")
    os.environ.setdefault("PUBLICATION_YEARS", "3")
    os.environ.setdefault("SEEN_STATE_PATH", "data/seen_ai_education_papers.json")
    os.environ.setdefault("MAX_PAPERS", "5")
    os.environ.setdefault("TIMEZONE", "Asia/Shanghai")


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


def _has_ai_theme(text: str) -> bool:
    patterns = [
        r"\bartificial intelligence\b",
        r"\bgenerative ai\b",
        r"\bgenai\b",
        r"\bchatgpt\b",
        r"\blarge language model(s)?\b",
        r"\bllm(s)?\b",
        r"\bai\b",
        r"\bai-assisted\b",
        r"\bai supported\b",
        r"\bintelligent tutor(ing|s)?\b",
        r"\badaptive learning\b",
        r"\blearning analytics\b",
        r"\beducational data mining\b",
        r"\bautomated feedback\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _has_education_theme(text: str) -> bool:
    education_terms = (
        "education",
        "educational",
        "teaching",
        "instruction",
        "learning",
        "teacher",
        "teachers",
        "student",
        "students",
        "school",
        "classroom",
        "curriculum",
        "assessment",
        "feedback",
        "mathematics education",
        "science education",
        "language education",
        "english education",
        "stem education",
        "teacher education",
        "professional development",
    )
    return any(term in text for term in education_terms)


def _has_subject_ai_theme(text: str) -> bool:
    subject_terms = (
        "mathematics",
        "math",
        "science",
        "stem",
        "language",
        "english",
        "reading",
        "writing",
        "literacy",
        "curriculum",
        "subject teaching",
        "disciplinary",
    )
    return _has_ai_theme(text) and any(term in text for term in subject_terms)


def _prefer_ai_education_score(paper: Paper, whitelist, mode: str):  # noqa: ANN001
    ok, score, reasons = _ORIGINAL_SCORE_PAPER(paper, whitelist, mode)
    if not ok:
        return ok, score, reasons

    text = _paper_text(paper)
    has_ai = _has_ai_theme(text)
    has_education = _has_education_theme(text)
    has_subject_ai = _has_subject_ai_theme(text)

    if has_subject_ai:
        return True, score + 45, reasons + ["ai_education_priority:subject_ai_integration"]
    if has_ai and has_education:
        return True, score + 38, reasons + ["ai_education_priority:ai_plus_education"]
    if has_ai:
        return True, score + 22, reasons + ["ai_education_priority:ai_assisted_teaching_or_learning"]
    if has_education:
        return True, score + 8, reasons + ["ai_education_priority:education_related_fallback"]
    return True, score, reasons + ["ai_education_priority:general_fallback"]


def _report_stem(report: DailyReport) -> str:
    return f"{report.report_date.isoformat()}_{AI_FILE_SUFFIX}"


def _special_markdown_content(report: DailyReport) -> str:
    content = _ORIGINAL_BUILD_MARKDOWN(report)
    date_text = report.report_date.isoformat()
    content = content.replace(
        f"# 每日SSCI文献简报（{date_text}）",
        f"# {AI_TITLE}（{date_text}）",
        1,
    )
    content = content.replace(
        "## 一、今日研究亮点总结",
        "## 一、AI教育优先研究亮点总结",
        1,
    )
    marker = "（北京时间）"
    if marker in content:
        content = content.replace(
            marker,
            f"{marker}\n> 专题范围：教育研究为基础，优先推荐AI+教育、学科融合AI、AI辅助教学/学习/评价、教师AI素养与教师专业发展；检索窗口：近三年；去重策略：跨次推送不重复推荐。",
            1,
        )
    return content


def generate_ai_education_markdown(report: DailyReport, config) -> Path:  # noqa: ANN001
    path = config.daily_dir / f"{_report_stem(report)}.md"
    write_text_file(path, _special_markdown_content(report))
    report.markdown_path = path
    return path


def generate_ai_education_word(report: DailyReport, config) -> Path:  # noqa: ANN001
    if not report.markdown_path:
        generate_ai_education_markdown(report, config)
    assert report.markdown_path is not None
    output = _ORIGINAL_GENERATE_DOCX_FROM_MARKDOWN(report.markdown_path, config)
    report.word_path = output
    return output


def generate_ai_education_html(report: DailyReport, config) -> str:  # noqa: ANN001
    html = _ORIGINAL_GENERATE_HTML(report, config)
    html = html.replace("每日SSCI文献简报", AI_TITLE)
    html = html.replace("今日研究亮点总结", "AI教育优先研究亮点总结")
    return html


def ai_education_subject(report_date) -> str:  # noqa: ANN001
    return f"{AI_SUBJECT}{report_date.isoformat()} 近三年教育/学科融合AI研究"


def patch_pipeline() -> None:
    paper_filter._score_paper = _prefer_ai_education_score  # type: ignore[attr-defined]
    search_module.SEARCH_QUERIES = tuple(dict.fromkeys(AI_PRIORITY_SEARCH_QUERIES + _ORIGINAL_SEARCH_QUERIES))
    daily_main.generate_markdown = generate_ai_education_markdown
    daily_main.generate_word = generate_ai_education_word
    daily_main.generate_html = generate_ai_education_html
    html_generator.email_subject = ai_education_subject
    mailer.email_subject = ai_education_subject


def main() -> int:
    configure_ai_education_defaults()
    patch_pipeline()
    try:
        daily_main.run_daily_job(send_email=True)
        return 0
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"Runtime error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
