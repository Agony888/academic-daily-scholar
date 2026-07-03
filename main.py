"""Academic Daily Scholar entrypoint."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import schedule

from config import ConfigError, load_config
from daily_selection import configure_daily_search_queries, select_daily_papers as filter_papers
from filter import load_ssci_whitelist, mark_papers_seen
from html_generator import generate_html
from logger import setup_logger
from mailer import send_daily_email
from markdown_generator import generate_markdown, generate_word
from search import search_recent_papers
from summarizer import summarize_papers
from utils import DailyReport


def run_daily_job(*, send_email: bool | None = None) -> DailyReport:
    config = load_config(validate=True)
    logger = setup_logger(config.logs_dir)
    tz = ZoneInfo(config.timezone)
    now = datetime.now(tz)
    window_end = now
    report_window_start = now - timedelta(days=365 * config.fallback_search_years)

    configure_daily_search_queries()
    logger.info(
        "Academic Daily Scholar started report_window_start=%s window_end=%s selection_strategy=2_latest_plus_3_ai_teaching_relevance",
        report_window_start,
        window_end,
    )
    whitelist = load_ssci_whitelist(config.ssci_whitelist_path, logger)
    all_papers = search_recent_papers(config, report_window_start, window_end, logger)
    selected = filter_papers(all_papers, config, logger, whitelist)

    notice = ""
    if len(selected) < config.max_papers:
        notice = f"今日不足{config.max_papers}篇，未重复推荐；实际筛选{len(selected)}篇。"
        logger.warning("%s 可用候选不足，请检查SSCI白名单、主题规则或检索源状态。", notice)
    elif config.max_papers >= 5:
        notice = "本期采用混合推荐策略：2篇近三年内最新候选文献 + 3篇近三年内AI教学相关度最高文献；已排除历史重复推荐。"

    items, hotspot, api_elapsed, failures = summarize_papers(selected, config, logger)

    report = DailyReport(
        report_date=now.date(),
        generated_at=now,
        window_start=report_window_start,
        window_end=window_end,
        total_found=len(all_papers),
        total_filtered=len(selected),
        total_success=sum(1 for item in items if not item.summary.one_sentence.startswith("摘要生成失败")),
        total_failed=failures,
        api_elapsed_seconds=api_elapsed,
        hotspot_summary=hotspot,
        items=items,
        notice=notice,
    )

    md_path = generate_markdown(report, config)
    word_path = generate_word(report, config)
    logger.info(
        "日报附件生成完成 markdown=%s exists=%s word=%s exists=%s",
        md_path,
        md_path.exists(),
        word_path,
        word_path.exists(),
    )
    html = generate_html(report, config)

    should_send = config.mail_enabled if send_email is None else send_email
    sent_success = False
    if should_send:
        sent_success = send_daily_email(report, html, config, logger)
        if not sent_success:
            report.total_failed += 1
    else:
        logger.info("命令行参数要求跳过邮件发送")

    logger.info(
        "任务完成 md=%s word=%s 检索数量=%s 成功数量=%s 失败数量=%s API耗时=%.2f",
        md_path,
        word_path,
        report.total_found,
        report.total_success,
        report.total_failed,
        report.api_elapsed_seconds,
    )
    if sent_success or not config.mail_enabled:
        mark_papers_seen(config.seen_state_path, selected)
    return report


def serve_scheduler() -> None:
    config = load_config(validate=True)
    logger = setup_logger(config.logs_dir)
    schedule.every().day.at(config.run_time).do(run_daily_job)
    logger.info("本地定时器已启动 timezone=%s run_time=%s", config.timezone, config.run_time)
    while True:
        schedule.run_pending()
        time.sleep(30)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Academic Daily Scholar")
    subparsers = parser.add_subparsers(dest="command")

    run_once = subparsers.add_parser("run-once", help="Run the daily workflow once")
    run_once.add_argument("--no-email", action="store_true", help="Generate reports but do not send email")

    subparsers.add_parser("serve", help="Run local schedule loop")
    subparsers.add_parser("check-config", help="Validate environment configuration")
    rebuild_docx = subparsers.add_parser("rebuild-docx", help="Rebuild native DOCX from a generated UTF-8 markdown report")
    rebuild_docx.add_argument("markdown_path", help="Markdown file path, for example daily/2026-06-29.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    command = args.command or "run-once"
    try:
        if command == "run-once":
            run_daily_job(send_email=not getattr(args, "no_email", False))
        elif command == "serve":
            serve_scheduler()
        elif command == "check-config":
            config = load_config(validate=True)
            logger = setup_logger(config.logs_dir)
            logger.info("配置检查通过 openai_base_url=%s model=%s mail_to=%s", config.openai_base_url, config.openai_model, config.mail_to)
        elif command == "rebuild-docx":
            from markdown_generator import generate_docx_from_markdown

            config = load_config(validate=False)
            output = generate_docx_from_markdown(getattr(args, "markdown_path"), config)
            print(output)
        else:
            raise ConfigError(f"Unknown command: {command}")
        return 0
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"Runtime error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
