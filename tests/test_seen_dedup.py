from __future__ import annotations

import json
import logging
from pathlib import Path

from filter import SsciWhitelist, filter_papers
from tests.test_filter_modes import make_config, relevant_paper


def test_seen_papers_are_not_recommended_again(tmp_path: Path) -> None:
    paper = relevant_paper("AI and elementary mathematics teacher learning", "Journal of Teacher Education", "1111-1111")
    config = make_config(tmp_path, "prefer")
    config.seen_state_path.write_text(json.dumps([paper.identity]), encoding="utf-8")

    kept = filter_papers([paper], config, logging.getLogger("test"), SsciWhitelist())

    assert kept == []


def test_filter_can_ignore_seen_only_when_explicitly_requested(tmp_path: Path) -> None:
    paper = relevant_paper("AI and elementary mathematics teacher learning", "Journal of Teacher Education", "1111-1111")
    config = make_config(tmp_path, "prefer")
    config.seen_state_path.write_text(json.dumps([paper.identity]), encoding="utf-8")

    kept = filter_papers([paper], config, logging.getLogger("test"), SsciWhitelist(), ignore_seen=True)

    assert kept == [paper]


def test_main_does_not_use_seen_repeat_supplement() -> None:
    source = Path("main.py").read_text(encoding="utf-8")
    assert "ignore_seen=True" not in source
    assert "fallback_repeat_allowed_to_keep_daily_5" not in source

