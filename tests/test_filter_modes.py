from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from config import AppConfig
from filter import SsciWhitelist, filter_papers
from utils import Paper


def make_config(tmp_path: Path, mode: str) -> AppConfig:
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
        template_dir=Path("templates"),
        ssci_whitelist_path=None,
        ssci_filter_mode=mode,  # type: ignore[arg-type]
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


def relevant_paper(title: str, journal: str, issn: str) -> Paper:
    return Paper(
        title=title,
        abstract=(
            "This empirical mixed methods study examines elementary school teachers, "
            "artificial intelligence classroom teaching, digital competence, interviews, "
            "questionnaires, students and teachers."
        ),
        journal=journal,
        issns=[issn],
        language="en",
    )


def test_strict_mode_keeps_only_whitelist_matches(tmp_path: Path) -> None:
    whitelist = SsciWhitelist(journal_names={"journal of teacher education"})
    matched = relevant_paper("AI for elementary teachers", "Journal of Teacher Education", "1111-1111")
    other = relevant_paper("AI for primary classroom teaching", "Education Technology Review", "2222-2222")

    kept = filter_papers([matched, other], make_config(tmp_path, "strict"), logging.getLogger("test"), whitelist)

    assert [paper.journal for paper in kept] == ["Journal of Teacher Education"]
    assert kept[0].ssci_matched is True
    assert "ssci_whitelist" in kept[0].filter_reasons


def test_prefer_mode_boosts_whitelist_but_does_not_exclude_non_whitelist(tmp_path: Path) -> None:
    whitelist = SsciWhitelist(journal_names={"journal of teacher education"})
    matched = relevant_paper("AI for elementary teachers", "Journal of Teacher Education", "1111-1111")
    other = relevant_paper("AI for primary classroom teaching", "Education Technology Review", "2222-2222")

    kept = filter_papers([other, matched], make_config(tmp_path, "prefer"), logging.getLogger("test"), whitelist)

    assert {paper.journal for paper in kept} == {"Journal of Teacher Education", "Education Technology Review"}
    matched_kept = next(p for p in kept if p.journal == "Journal of Teacher Education")
    other_kept = next(p for p in kept if p.journal == "Education Technology Review")
    assert matched_kept.ssci_matched is True
    assert other_kept.ssci_matched is False
    assert matched_kept.filter_score > other_kept.filter_score


def test_off_mode_ignores_whitelist_matching_and_boost(tmp_path: Path) -> None:
    whitelist = SsciWhitelist(journal_names={"journal of teacher education"})
    matched = relevant_paper("AI for elementary teachers", "Journal of Teacher Education", "1111-1111")
    other = relevant_paper("AI for primary classroom teaching", "Education Technology Review", "2222-2222")

    kept = filter_papers([matched, other], make_config(tmp_path, "off"), logging.getLogger("test"), whitelist)

    assert {paper.journal for paper in kept} == {"Journal of Teacher Education", "Education Technology Review"}
    assert all(not paper.ssci_matched for paper in kept)
    assert all("ssci_whitelist" not in paper.filter_reasons for paper in kept)

