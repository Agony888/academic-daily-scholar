"""Dedicated AI-prioritized preschool and basic education literature push.

This entrypoint reuses the main Academic Daily Scholar pipeline, but narrows the
special push toward preschool education and basic education, especially primary
and lower-secondary contexts. It prioritizes AI use in teaching, subject-specific
AI integration, teacher digital/AI/data literacy, AI integration in preservice
and in-service teacher education, and teaching change or teacher role change
under educational digital transformation. The search window is three years, with
a separate seen-state file and standardized output file names.
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

AI_TITLE = "学前与基础教育AI专题文献推送"
AI_FILE_SUFFIX = "AI教育专题文献推送"
AI_SUBJECT = "【学前与基础教育AI专题文献推送】"

AI_PRIORITY_SEARCH_QUERIES: tuple[str, ...] = (
    # Preschool and basic education + AI teaching application.
    "artificial intelligence preschool education teaching",
    "AI early childhood education teaching",
    "generative AI early childhood education",
    "artificial intelligence kindergarten teaching",
    "AI kindergarten education",
    "artificial intelligence primary education teaching",
    "AI primary school teaching",
    "AI elementary education teaching",
    "AI elementary school learning",
    "artificial intelligence basic education teaching",
    "AI compulsory education teaching",
    "AI K-12 education teaching",
    "artificial intelligence junior high school teaching",
    "AI middle school teaching",
    "AI lower secondary education",
    "school education artificial intelligence teaching",
    "classroom teaching artificial intelligence school",
    "AI assisted teaching basic education",
    "AI assisted learning basic education",
    "AI supported classroom teaching",
    "AI assisted assessment school education",
    "automated feedback school education",
    "intelligent tutoring K-12 education",
    "adaptive learning primary education",
    "learning analytics basic education",
    "educational data mining K-12 education",
    # Subject-specific AI integration.
    "mathematics education artificial intelligence primary school",
    "mathematics teaching artificial intelligence elementary school",
    "mathematics learning artificial intelligence K-12",
    "science education artificial intelligence primary school",
    "science teaching artificial intelligence middle school",
    "STEM education artificial intelligence school",
    "language education artificial intelligence primary school",
    "English education artificial intelligence school",
    "reading education artificial intelligence school",
    "writing instruction artificial intelligence school",
    "subject teaching artificial intelligence school education",
    "curriculum artificial intelligence basic education",
    # Teacher digital, AI, intelligent and data literacy.
    "teacher digital literacy preschool education",
    "teacher digital literacy primary education",
    "teacher digital competence basic education",
    "teacher AI literacy school education",
    "teacher artificial intelligence literacy basic education",
    "teacher intelligent literacy education",
    "teacher data literacy basic education",
    "primary school teacher digital literacy",
    "elementary teacher AI literacy",
    "middle school teacher data literacy",
    "preschool teacher digital competence",
    # Preservice and in-service teacher education/training + AI.
    "teacher education artificial intelligence integration",
    "preservice teachers artificial intelligence education",
    "pre-service teachers AI integration teacher education",
    "in-service teachers artificial intelligence training",
    "teacher professional development artificial intelligence school",
    "teacher training generative AI education",
    "AI integration preservice teacher education",
    "AI integration in-service teacher professional development",
    "AI lesson planning teacher education",
    "AI classroom assessment teacher training",
    # Educational digital transformation, teaching change and teacher role.
    "educational digital transformation basic education teacher role",
    "digital transformation school education teacher role",
    "educational digitalization teaching reform school teachers",
    "AI teaching reform basic education",
    "artificial intelligence teacher role school education",
    "digital education teacher role primary school",
    "technology integration teacher role basic education",
    "teacher agency artificial intelligence school education",
)

_ORIGINAL_SCORE_PAPER = paper_filter._score_paper  # type: ignore[attr-defined]
_ORIGINAL_BUILD_MARKDOWN = markdown_generator.build_markdown
_ORIGINAL_GENERATE_DOCX_FROM_MARKDOWN = markdown_generator.generate_docx_from_markdown
_ORIGINAL_GENERATE_HTML = html_generator.generate_html
_ORIGINAL_SEARCH_QUERIES = search_module.SEARCH_QUERIES


def configure_ai_education_defaults() -> None:
    """Set runtime defaults for the dedicated topic push."""

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


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


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


def _has_preschool_or_basic_stage(text: str) -> bool:
    stage_terms = (
        "preschool",
        "pre-school",
        "early childhood",
        "kindergarten",
        "primary education",
        "primary school",
        "elementary education",
        "elementary school",
        "basic education",
        "compulsory education",
        "k-12",
        "k12",
        "school education",
        "school teacher",
        "school teachers",
        "school student",
        "school students",
        "junior high",
        "middle school",
        "lower secondary",
        "children",
        "pupils",
    )
    return _contains_any(text, stage_terms)


def _has_ai_teaching_application(text: str) -> bool:
    teaching_terms = (
        "teaching",
        "instruction",
        "learning",
        "classroom",
        "lesson planning",
        "instructional design",
        "teaching design",
        "curriculum",
        "assessment",
        "feedback",
        "tutoring",
        "adaptive learning",
        "learning analytics",
        "educational data mining",
    )
    return _has_ai_theme(text) and _contains_any(text, teaching_terms)


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
    return _has_ai_theme(text) and _contains_any(text, subject_terms)


def _has_teacher_literacy_theme(text: str) -> bool:
    literacy_terms = (
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
    teacher_terms = ("teacher", "teachers", "educator", "educators")
    return _contains_any(text, literacy_terms) and _contains_any(text, teacher_terms)


def _has_teacher_education_ai_integration(text: str) -> bool:
    teacher_training_terms = (
        "teacher education",
        "preservice teacher",
        "pre-service teacher",
        "preservice teachers",
        "pre-service teachers",
        "in-service teacher",
        "inservice teacher",
        "in-service teachers",
        "inservice teachers",
        "teacher training",
        "teacher professional development",
        "professional development",
        "initial teacher education",
    )
    return _has_ai_theme(text) and _contains_any(text, teacher_training_terms)


def _has_digital_transformation_teacher_role(text: str) -> bool:
    transformation_terms = (
        "digital transformation",
        "educational digital transformation",
        "digitalization",
        "digitalisation",
        "digital education",
        "technology integration",
        "teaching reform",
        "teaching change",
        "pedagogical change",
        "teacher role",
        "teacher agency",
        "teacher identity",
    )
    teacher_or_teaching_terms = ("teacher", "teachers", "teaching", "classroom", "school")
    return _contains_any(text, transformation_terms) and _contains_any(text, teacher_or_teaching_terms)


def _is_high_school_only(text: str) -> bool:
    high_school_terms = (
        "high school",
        "senior high",
        "upper secondary",
    )
    lower_stage_terms = (
        "middle school",
        "junior high",
        "lower secondary",
        "primary",
        "elementary",
        "preschool",
        "kindergarten",
        "k-12",
        "k12",
        "basic education",
        "compulsory education",
    )
    return _contains_any(text, high_school_terms) and not _contains_any(text, lower_stage_terms)


def _prioritize_defined_scope(paper: Paper, whitelist, mode: str):  # noqa: ANN001
    ok, score, reasons = _ORIGINAL_SCORE_PAPER(paper, whitelist, mode)
    if not ok:
        return ok, score, reasons

    text = _paper_text(paper)
    stage_hit = _has_preschool_or_basic_stage(text)
    ai_teaching = _has_ai_teaching_application(text)
    subject_ai = _has_subject_ai_theme(text)
    teacher_literacy = _has_teacher_literacy_theme(text)
    teacher_education_ai = _has_teacher_education_ai_integration(text)
    digital_transform = _has_digital_transformation_teacher_role(text)

    if _is_high_school_only(text) and not teacher_education_ai:
        return False, score - 20, reasons + ["scope:high_school_only"]

    if not stage_hit and not teacher_education_ai:
        return False, score - 20, reasons + ["scope:not_preschool_or_basic_education"]

    topic_hits: list[str] = []
    if subject_ai:
        score += 45
        topic_hits.append("subject_ai_integration")
    if ai_teaching:
        score += 40
        topic_hits.append("ai_teaching_application")
    if teacher_literacy:
        score += 36
        topic_hits.append("teacher_digital_ai_data_literacy")
    if teacher_education_ai:
        score += 38
        topic_hits.append("teacher_education_ai_integration")
    if digital_transform:
        score += 28
        topic_hits.append("digital_transformation_teacher_role")
    if stage_hit:
        score += 20
        topic_hits.append("preschool_or_basic_education_stage")

    if not topic_hits:
        return False, score, reasons + ["scope:no_defined_topic"]

    return True, score, reasons + [f"defined_scope:{hit}" for hit in topic_hits]


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
        "## 一、专题研究亮点总结",
        1,
    )
    marker = "（北京时间）"
    if marker in content:
        content = content.replace(
            marker,
            f"{marker}\n> 专题范围：聚焦学前教育及基础教育阶段，尤其是小学、初中；主题涵盖AI在教学中的应用、学科融合AI、教师数字/智能/数据素养、职前与在职教师培训中的AI整合、教育数字化背景下的教学变革与教师角色；检索窗口：近三年；去重策略：跨次推送不重复推荐。",
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
    html = html.replace("今日研究亮点总结", "专题研究亮点总结")
    return html


def ai_education_subject(report_date) -> str:  # noqa: ANN001
    return f"{AI_SUBJECT}{report_date.isoformat()} 近三年学前/基础教育AI与教师发展研究"


def patch_pipeline() -> None:
    paper_filter._score_paper = _prioritize_defined_scope  # type: ignore[attr-defined]
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
