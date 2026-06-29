"""HTML email sender using NetEase SMTP."""

from __future__ import annotations

import logging
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

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

    message = MIMEMultipart("alternative")
    message["Subject"] = str(Header(email_subject(report.report_date), "utf-8"))
    message["From"] = formataddr((str(Header(config.mail_from_name, "utf-8")), config.smtp_user))
    message["To"] = config.mail_to
    message.attach(MIMEText(html, "html", "utf-8"))

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
