"""Small translation helpers backed by the same OpenAI-compatible API."""

from __future__ import annotations

from openai import OpenAI

from config import AppConfig
from summarizer import build_openai_client


def translate_title(title: str, config: AppConfig, client: OpenAI | None = None) -> str:
    """Translate an English paper title to Chinese.

    The main summarizer already translates titles; this helper is exposed for reuse
    and for users who want title-only workflows.
    """

    if not title.strip():
        return ""
    active_client = client or build_openai_client(config)
    response = active_client.chat.completions.create(
        model=config.openai_model,
        messages=[
            {"role": "system", "content": "你是学术标题翻译助手，只输出中文译名。"},
            {"role": "user", "content": f"请将以下英文论文标题翻译成准确、自然的中文：\n{title}"},
        ],
        temperature=0.1,
    )
    return (response.choices[0].message.content or title).strip()
