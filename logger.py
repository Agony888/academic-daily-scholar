"""Logging setup for Academic Daily Scholar."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def setup_logger(logs_dir: Path, *, name: str = "academic_daily_scholar") -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    today_handler = logging.FileHandler(logs_dir / "today.log", encoding="utf-8", mode="a")
    today_handler.setFormatter(formatter)
    logger.addHandler(today_handler)

    dated_handler = logging.FileHandler(
        logs_dir / f"{datetime.now().date().isoformat()}.log",
        encoding="utf-8",
        mode="a",
    )
    dated_handler.setFormatter(formatter)
    logger.addHandler(dated_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger
