from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from config import AppConfig
from filter import SsciWhitelist, filter_papers
from utils import Paper


def _config(mode: str = "strict") -> AppConfig:
    return AppConfig(
        openalex_api_key="oa-test",
        openai_api_key="sk-test",
        openai_base_url="http://localhost:8080",
        openai_model="test",
        smtp_server="smtp.163.com",
        smtp_port=465,
        smtp_user="sender@example.com",
        smtp_password="secret",
        mail_to="to@example.com",
        mail_from_name="Academic Daily Scholar",
        project_root=Path("."),
        daily_dir=Path("daily"),
        logs_dir=Path("logs"),
        template_dir=Path("templates"),
        ssci_whitelist_path=None,
        ssci_filter_mode=mode,  # type: ignore[arg-type]
        max_papers=5,
        search_months=3,
        publication_years=1,
        primary_search_days=3,
        fallback_search_years=3,
        seen_state_path=Path("data/seen_papers_test.json"),
        request_timeout_seconds=30,
        request_retries=3,
        openai_timeout_seconds=90,
        timezone="Asia/Shanghai",
        run_time="08:00",
        mail_enabled=False,
        user_agent="test",
    )


def test_ssci_whitelist_matches_issn() -> None:
    whitelist = SsciWhitelist(issns={"1234-567X"})
    paper = Paper(title="Teacher learning in elementary mathematics", journal="Example", issns=["1234567X"])
    assert whitelist.is_match(paper)


def test_filter_keeps_relevant_ssci_paper() -> None:
    paper = Paper(
        title="Generative AI for elementary school teacher professional development",
        abstract="This empirical mixed methods study investigates teacher reflection, digital competence, classroom teaching and data collected from teachers through interviews and questionnaires.",
        published_date=date(2026, 6, 29),
        journal="Journal of Teacher Education",
        issns=["0022-4871"],
    )
    whitelist = SsciWhitelist(journal_names={"journal of teacher education"})
    kept = filter_papers([paper], _config(), logging.getLogger("test"), whitelist)
    assert len(kept) == 1
    assert kept[0].ssci_matched


def test_filter_excludes_medical_topic() -> None:
    paper = Paper(
        title="Clinical medicine education for patient biology",
        abstract="A medical patient study.",
        journal="Medical Education",
        issns=["0000-0000"],
    )
    kept = filter_papers([paper], _config(mode="off"), logging.getLogger("test"), SsciWhitelist())
    assert kept == []
