from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import AppConfig
from html_generator import generate_html
from markdown_generator import build_markdown, generate_markdown, generate_word
from utils import DailyReport, Paper, PaperSummary, ReportItem


def make_report_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        openalex_api_key="oa-test",
        openai_api_key="sk-test",
        openai_base_url="http://localhost:8080/v1",
        openai_model="test",
        smtp_server="smtp.163.com",
        smtp_port=465,
        smtp_user="sender@example.com",
        smtp_password="secret",
        mail_to="to@example.com",
        mail_from_name="Academic Daily Scholar",
        project_root=tmp_path,
        daily_dir=tmp_path / "daily",
        logs_dir=tmp_path / "logs",
        template_dir=Path("templates").resolve(),
        ssci_whitelist_path=None,
        ssci_filter_mode="prefer",
        max_papers=5,
        search_months=3,
        publication_years=1,
        primary_search_days=3,
        fallback_search_years=3,
        seen_state_path=tmp_path / "seen.json",
        request_timeout_seconds=30,
        request_retries=3,
        openai_timeout_seconds=90,
        timezone="Asia/Shanghai",
        run_time="08:00",
        mail_enabled=False,
        user_agent="test",
    )


def sample_report() -> DailyReport:
    tz = ZoneInfo("Asia/Shanghai")
    paper = Paper(
        title="Artificial intelligence for elementary mathematics teacher learning",
        journal="Learning and Instruction",
        doi="10.1234/example",
        published_date=date(2026, 6, 29),
        authors=["Alice Smith", "Bob Wang"],
        ssci_matched=True,
        ssci_categories=["Education & Educational Research"],
        impact_factor="6.2",
        quartile="Q1",
        citescore="9.1",
        publisher="Elsevier",
    )
    summary = PaperSummary(
        chinese_title="人工智能支持小学数学教师学习",
        authors_text="Alice Smith; Bob Wang",
        journal_impact="",
        volume_issue_doi="10.1234/example",
        online_date="2026-06-29",
        research_abstract="本研究报告了实证数据。",
        main_content="关注小学数学教师学习。",
        argument="AI可支持教师专业发展。",
        research_question="AI如何支持教师学习？",
        methods="混合方法，访谈与问卷。",
        findings="教师数字素养有所提升。",
        implications_teacher_education="教师教育可融入AI备课任务。",
        apa_citation="Smith, A., & Wang, B. (2026). Artificial intelligence for elementary mathematics teacher learning.",
    )
    return DailyReport(
        report_date=date(2026, 6, 29),
        generated_at=datetime(2026, 6, 29, 8, 0, tzinfo=tz),
        window_start=datetime(2026, 6, 26, 8, 0, tzinfo=tz),
        window_end=datetime(2026, 6, 29, 8, 0, tzinfo=tz),
        total_found=12,
        total_filtered=1,
        total_success=1,
        total_failed=0,
        api_elapsed_seconds=1.2,
        hotspot_summary="今日关注AI支持小学数学教师专业发展。",
        items=[ReportItem(paper=paper, summary=summary)],
        notice="今日不足5篇，未重复推荐；实际筛选1篇。",
    )


def test_markdown_report_contains_notice_and_whitelist_metadata() -> None:
    markdown = build_markdown(sample_report())
    assert "今日不足5篇，未重复推荐" in markdown
    assert "JIF/影响因子：6.2" in markdown
    assert "JCR分区：Q1" in markdown
    assert "CiteScore：9.1" in markdown
    assert "出版社：Elsevier" in markdown


def test_generate_markdown_word_and_html(tmp_path: Path) -> None:
    config = make_report_config(tmp_path)
    report = sample_report()

    md_path = generate_markdown(report, config)
    word_path = generate_word(report, config)
    html = generate_html(report, config)

    assert md_path.exists()
    assert word_path.exists()
    assert word_path.suffix == ".docx"
    assert "今日不足5篇，未重复推荐" in html
    assert "6.2" in html
    assert "Q1" in html

