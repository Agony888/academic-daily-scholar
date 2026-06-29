"""HTML email generation with Jinja2 templates."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import AppConfig
from utils import DailyReport, format_date_cn


def generate_html(report: DailyReport, config: AppConfig) -> str:
    env = Environment(
        loader=FileSystemLoader(str(config.template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["date_cn"] = format_date_cn
    template = env.get_template("email.html.j2")
    return template.render(report=report, subject=email_subject(report.report_date), Path=Path)


def email_subject(report_date: date) -> str:
    return f"【每日SSCI文献简报】{report_date.isoformat()} AI与教师教育实证研究"
