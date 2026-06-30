"""Configuration loading for Academic Daily Scholar."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv


FilterMode = Literal["off", "prefer", "strict"]


class ConfigError(RuntimeError):
    """Raised when required runtime configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class AppConfig:
    openalex_api_key: str
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    smtp_server: str
    smtp_port: int
    smtp_user: str
    smtp_auth_code: str
    mail_to: str
    mail_from_name: str
    project_root: Path
    daily_dir: Path
    logs_dir: Path
    template_dir: Path
    ssci_whitelist_path: Path | None
    ssci_filter_mode: FilterMode
    max_papers: int
    search_months: int
    publication_years: int
    primary_search_days: int
    fallback_search_years: int
    seen_state_path: Path
    request_timeout_seconds: int
    request_retries: int
    openai_timeout_seconds: int
    timezone: str
    run_time: str
    mail_enabled: bool
    user_agent: str


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _normalize_openai_api_key(value: str) -> str:
    """Allow users to paste either a raw key or the URL-like key text from the prompt."""

    text = value.strip()
    if not text:
        return ""
    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        fragment = parsed.fragment or ""
        query = parse_qs(fragment)
        if "text" in query and query["text"]:
            return unquote(query["text"][0]).strip()
        match = re.search(r"sk(?:-|%2D)[A-Za-z0-9]+", text, flags=re.IGNORECASE)
        if match:
            return unquote(match.group(0)).strip()
    return text


def _normalize_openai_base_url(value: str) -> str:
    """Normalize OpenAI-compatible base URL for the OpenAI SDK.

    The OpenAI Python SDK expects base_url to point at the API root that owns
    /chat/completions. Many gateways show users the web root, so when only a
    scheme + host is provided we append /v1 automatically.
    """

    text = value.strip().rstrip("/")
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme and parsed.netloc and parsed.path in {"", "/"}:
        return text + "/v1"
    return text


def _normalize_mail_to(value: str) -> str:
    text = value.strip()
    match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
    return match.group(0) if match else text


def load_config(validate: bool = True) -> AppConfig:
    load_dotenv(encoding="utf-8-sig")

    root = Path(__file__).resolve().parent
    daily_dir = root / os.getenv("DAILY_DIR", "daily")
    logs_dir = root / os.getenv("LOGS_DIR", "logs")
    template_dir = root / os.getenv("TEMPLATE_DIR", "templates")

    whitelist_raw = os.getenv("SSCI_WHITELIST_PATH", "data/ssci_whitelist_2026-06.xlsx").strip()
    whitelist_path = Path(whitelist_raw) if whitelist_raw else None
    if whitelist_path and not whitelist_path.is_absolute():
        whitelist_path = root / whitelist_path

    mode = os.getenv("SSCI_FILTER_MODE", "strict").strip().lower()
    if mode not in {"off", "prefer", "strict"}:
        raise ConfigError("SSCI_FILTER_MODE must be one of: off, prefer, strict")

    config = AppConfig(
        openalex_api_key=os.getenv("OPENALEX_API_KEY", "").strip(),
        openai_api_key=_normalize_openai_api_key(os.getenv("OPENAI_API_KEY", "")),
        openai_base_url=_normalize_openai_base_url(os.getenv("OPENAI_BASE_URL", "")),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        smtp_server=(os.getenv("SMTP_SERVER") or "smtp.163.com").strip(),
        smtp_port=_env_int("SMTP_PORT", 465),
        smtp_user=(os.getenv("SMTP_EMAIL") or os.getenv("SMTP_USER") or "").strip(),
        smtp_auth_code=(os.getenv("SMTP_AUTH_CODE") or os.getenv("SMTP_PASSWORD") or "").strip(),
        mail_to=_normalize_mail_to(os.getenv("MAIL_TO") or "agony2023@qq.com"),
        mail_from_name=os.getenv("MAIL_FROM_NAME", "Academic Daily Scholar").strip(),
        project_root=root,
        daily_dir=daily_dir,
        logs_dir=logs_dir,
        template_dir=template_dir,
        ssci_whitelist_path=whitelist_path,
        ssci_filter_mode=mode,  # type: ignore[arg-type]
        max_papers=_env_int("MAX_PAPERS", 5),
        search_months=_env_int("SEARCH_MONTHS", 3),
        publication_years=_env_int("PUBLICATION_YEARS", 1),
        primary_search_days=_env_int("PRIMARY_SEARCH_DAYS", 3),
        fallback_search_years=_env_int("FALLBACK_SEARCH_YEARS", 3),
        seen_state_path=root / os.getenv("SEEN_STATE_PATH", "data/seen_papers.json"),
        request_timeout_seconds=_env_int("REQUEST_TIMEOUT_SECONDS", 30),
        request_retries=_env_int("REQUEST_RETRIES", 3),
        openai_timeout_seconds=_env_int("OPENAI_TIMEOUT_SECONDS", 90),
        timezone=os.getenv("TIMEZONE", "Asia/Shanghai").strip(),
        run_time=os.getenv("RUN_TIME", "08:00").strip(),
        mail_enabled=_env_bool("MAIL_ENABLED", True),
        user_agent=os.getenv(
            "USER_AGENT",
            "AcademicDailyScholar/1.0 (mailto:agony2023@qq.com)",
        ).strip(),
    )

    if validate:
        missing: list[str] = []
        if not config.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not config.openai_base_url:
            missing.append("OPENAI_BASE_URL")
        if config.mail_enabled:
            if not config.smtp_user:
                missing.append("SMTP_EMAIL")
            if not config.smtp_auth_code:
                missing.append("SMTP_AUTH_CODE")
            if not config.mail_to:
                missing.append("MAIL_TO")
        if missing:
            raise ConfigError("Missing required environment variables: " + ", ".join(missing))

    return config
