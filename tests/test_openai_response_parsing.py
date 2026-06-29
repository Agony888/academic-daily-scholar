from __future__ import annotations

from types import SimpleNamespace

from summarizer import _completion_content
from utils import safe_json_loads


def test_completion_content_parses_string_response() -> None:
    assert _completion_content("plain text") == "plain text"


def test_completion_content_parses_dict_chat_response() -> None:
    response = {"choices": [{"message": {"content": "{\"ok\": true}"}}]}
    assert _completion_content(response) == '{"ok": true}'


def test_completion_content_parses_object_chat_response() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="object content"),
            )
        ]
    )
    assert _completion_content(response) == "object content"


def test_safe_json_loads_parses_fenced_json() -> None:
    text = """```json\n{\"chinese_title\": \"中文标题\", \"methods\": \"混合方法\"}\n```"""
    assert safe_json_loads(text) == {"chinese_title": "中文标题", "methods": "混合方法"}
