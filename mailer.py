"""HTML email sender using NetEase SMTP."""

from __future__ import annotations

import logging
import smtplib
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

from config import AppConfig
from html_generator import email_subject
from utils import DailyReport, retry_call


def send_daily_email(
    report: DailyReport,
    html: str,
    config: AppConfig,
    logger: logging.Logger,
) -> bool:
    if not config.mail_enabled:
        logger.info("MAIL_ENABLED=false，跳过邮件发送")
        return False

    message = MIMEMultipart("mixed")
    message["Subject"] = str(Header(email_subject(report.report_date), "utf-8"))
    message["From"] = formataddr((str(Header(config.mail_from_name, "utf-8")), config.smtp_user))
    message["To"] = config.mail_to

    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(_plain_text_fallback(report), "plain", "utf-8"))
    alternative.attach(MIMEText(html, "html", "utf-8"))
    message.attach(alternative)

    for attachment_path in _attachment_paths(report):
        try:
            message.attach(_build_attachment(attachment_path))
            logger.info("邮件附件已添加 path=%s size=%s", attachment_path, attachment_path.stat().st_size)
        except Exception as exc:  # noqa: BLE001
            logger.exception("邮件附件添加失败 path=%s error=%s", attachment_path, exc)

    def _send() -> bool:
        with smtplib.SMTP_SSL(config.smtp_server, config.smtp_port, timeout=30) as smtp:
            smtp.login(config.smtp_user, config.smtp_password)
            smtp.sendmail(config.smtp_user, [config.mail_to], message.as_string())
        return True

    try:
        retry_call(_send, retries=3, backoff_seconds=5.0, retry_exceptions=(smtplib.SMTPException, OSError))
        logger.info("发送邮件状态 success to=%s", config.mail_to)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("发送邮件状态 failed to=%s error=%s", config.mail_to, exc)
        return False


def _attachment_paths(report: DailyReport) -> list[Path]:
    paths: list[Path] = []
    if report.markdown_path and report.markdown_path.exists():
        paths.append(report.markdown_path)
    if report.word_path and report.word_path.exists():
        paths.append(report.word_path)
    return paths


def _build_attachment(path: Path) -> MIMEApplication:
    data = path.read_bytes()
    if path.suffix.lower() == ".docx":
        subtype = "vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        subtype = "octet-stream"
    part = MIMEApplication(data, _subtype=subtype)
    filename = path.name
    part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", filename))
    return part


def _plain_text_fallback(report: DailyReport) -> str:
    lines = [
        f"每日SSCI文献简报 {report.report_date.isoformat()}",
        "",
        "本邮件包含 HTML 正文，并附带 Markdown 与 Word 文档附件。",
        "",
        f"检索数量：{report.total_found}",
        f"筛选数量：{report.total_filtered}",
        f"AI成功数量：{report.total_success}",
        f"失败数量：{report.total_failed}",
    ]
    if report.markdown_path:
        lines.append(f"Markdown：{report.markdown_path.name}")
    if report.word_path:
        lines.append(f"Word：{report.word_path.name}")
    return "\n".join(lines)
