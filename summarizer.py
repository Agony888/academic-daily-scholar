"""OpenAI-compatible summarization pipeline."""

from __future__ import annotations

import logging
import time
from typing import Any

from openai import OpenAI

from config import AppConfig
from utils import Paper, PaperSummary, ReportItem, retry_call, safe_json_loads, truncate_text


SUMMARY_KEYS: dict[str, str] = {
    "chinese_title": "中文标题",
    "authors_text": "作者",
    "journal_impact": "期刊及影响因子",
    "volume_issue_doi": "卷期/DOI",
    "online_date": "在线发表时间",
    "research_abstract": "研究摘要",
    "main_content": "研究主要内容",
    "argument": "研究论点",
    "research_question": "研究问题",
    "methods": "研究方法",
    "findings": "主要发现",
    "implications_teacher_education": "对教师教育研究的启示",
    "apa_citation": "APA引用格式",
}


def build_openai_client(config: AppConfig) -> OpenAI:
    return OpenAI(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        timeout=config.openai_timeout_seconds,
        max_retries=0,
    )


def summarize_papers(
    papers: list[Paper],
    config: AppConfig,
    logger: logging.Logger,
) -> tuple[list[ReportItem], str, float, int]:
    client = build_openai_client(config)
    items: list[ReportItem] = []
    failures = 0
    start = time.perf_counter()

    for index, paper in enumerate(papers, start=1):
        try:
            logger.info("AI摘要开始 %s/%s title=%s", index, len(papers), paper.title[:120])
            summary = retry_call(
                lambda p=paper: summarize_one_paper(client, config, p),
                retries=3,
                backoff_seconds=3.0,
            )
            items.append(ReportItem(paper=paper, summary=summary))
            logger.info("AI摘要成功 %s/%s title=%s", index, len(papers), paper.title[:120])
        except Exception as exc:  # noqa: BLE001
            failures += 1
            logger.exception("AI摘要失败 title=%s error=%s", paper.title, exc)
            items.append(ReportItem(paper=paper, summary=PaperSummary.empty(paper.title, str(exc))))

    hotspot = ""
    if items:
        try:
            hotspot = retry_call(
                lambda: summarize_hotspots(client, config, items),
                retries=3,
                backoff_seconds=3.0,
            )
        except Exception as exc:  # noqa: BLE001
            failures += 1
            logger.exception("今日文献亮点总结失败: %s", exc)
            hotspot = "今日文献亮点总结生成失败，请查看日志。"
    else:
        hotspot = "今日未筛选到符合条件的SSCI实证论文。"

    elapsed = time.perf_counter() - start
    logger.info("API耗时 seconds=%.2f failures=%s", elapsed, failures)
    return items, hotspot, elapsed, failures


def summarize_one_paper(client: OpenAI, config: AppConfig, paper: Paper) -> PaperSummary:
    prompt = f"""
你是一名严谨的教育学研究助手。请阅读下面英文SSCI论文元数据和摘要，生成“每日SSCI文献简报”所需的中文结构化摘要。

要求：
1. 不要编造摘要和元数据中没有的信息；无法判断时写“摘要未说明”。
2. 重点判断并呈现论文的实证数据、研究设计、数据收集与分析方法。
3. 聚焦学前教育及基础教育（小学、初中）阶段，主题包括AI教学应用、教师数字素养/智能素养/数据素养、教师教育与教师培训中的AI整合、教育数字化背景下教学变革与教师角色。
4. “研究方法”必须说明研究类型（定量/定性/混合）、样本或参与者、数据来源、分析方法；若摘要未说明，要明确写出缺失。
5. “主要发现”请写3点左右，尽量具体。
6. “对教师教育研究的启示”要服务于用户了解前沿主题、研究设计、数据收集与分析方法。
7. APA引用格式尽量根据元数据生成；卷期缺失可省略，但DOI应保留。
8. 输出严格 JSON，不要添加 Markdown。
9. JSON 字段必须包含：
   chinese_title, authors_text, journal_impact, volume_issue_doi, online_date,
   research_abstract, main_content, argument, research_question, methods,
   findings, implications_teacher_education, apa_citation

论文信息：
原标题：{paper.title}
期刊：{paper.journal}
SSCI分类：{", ".join(paper.ssci_categories)}
影响因子/分区：{paper.impact_factor or "白名单未提供影响因子"} / {paper.quartile or "白名单未提供JCR分区"}
发表日期：{paper.published_date}
作者：{", ".join(paper.authors[:8])}
DOI：{paper.doi}
链接：{paper.url}
主题/关键词：{", ".join((paper.concepts + paper.keywords)[:20])}
摘要：{truncate_text(paper.abstract or "摘要未提供。", 6000)}
""".strip()

    response = client.chat.completions.create(
        model=config.openai_model,
        messages=[
            {"role": "system", "content": "你是资深教育研究方法专家，擅长将英文教育论文摘要转化为中文研究综述。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    content = _completion_content(response)
    data = safe_json_loads(content) or _fallback_parse_summary(content)
    return PaperSummary(
        chinese_title=_value(data, "chinese_title", paper.title),
        authors_text=_value(data, "authors_text", ", ".join(paper.authors) or "摘要未说明"),
        journal_impact=_value(data, "journal_impact", f"{paper.journal or '摘要未说明'}；影响因子/分区：白名单未提供"),
        volume_issue_doi=_value(data, "volume_issue_doi", paper.doi or "摘要未说明"),
        online_date=_value(data, "online_date", str(paper.published_date or "摘要未说明")),
        research_abstract=_value(data, "research_abstract", "摘要未说明"),
        main_content=_value(data, "main_content", "摘要未说明"),
        argument=_value(data, "argument", "摘要未说明"),
        research_question=_value(data, "research_question", "摘要未说明"),
        methods=_value(data, "methods", "摘要未说明"),
        findings=_value(data, "findings", "摘要未说明"),
        implications_teacher_education=_value(data, "implications_teacher_education", "摘要未说明"),
        apa_citation=_value(data, "apa_citation", "摘要未说明"),
        raw_text=content,
    )


def summarize_hotspots(client: OpenAI, config: AppConfig, items: list[ReportItem]) -> str:
    paper_blocks = []
    for idx, item in enumerate(items, start=1):
        paper_blocks.append(
            f"{idx}. {item.summary.chinese_title}\n"
            f"原题：{item.paper.title}\n"
            f"研究摘要：{item.summary.research_abstract}\n"
            f"研究方法：{item.summary.methods}\n"
            f"主要发现：{item.summary.findings}\n"
            f"关键词：{', '.join(item.paper.keywords[:8] or item.paper.concepts[:8])}"
        )
    prompt = """
请基于以下今日筛选出的5篇SSCI教育实证论文，生成一段100字以内的“今日文献亮点总结”。
要求：
1. 不超过100字。
2. 概括今日文献共同关注的议题或方法特征。
3. 优先提炼最具创新性或最贴近中国语境的研究趋势。
4. 不要编造具体数据。

论文列表：
""".strip() + "\n\n" + "\n\n".join(paper_blocks)

    response = client.chat.completions.create(
        model=config.openai_model,
        messages=[
            {"role": "system", "content": "你是教育研究综述写作专家。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.25,
    )
    return _completion_content(response).strip()


def _value(data: dict[str, Any], key: str, default: str) -> str:
    value = data.get(key)
    if value is None:
        value = data.get(SUMMARY_KEYS.get(key, ""))
    text = str(value).strip() if value is not None else ""
    return text or default


def _fallback_parse_summary(content: str) -> dict[str, str]:
    return {"research_abstract": content.strip() or "模型未返回有效内容。"}


def _completion_content(response: Any) -> str:
    """Extract content from standard and mildly non-standard compatible APIs."""

    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            return str(message.get("content") or choices[0].get("text") or "")
        return str(response)
    choices = getattr(response, "choices", None) or []
    if choices:
        first = choices[0]
        message = getattr(first, "message", None)
        if message is not None:
            return str(getattr(message, "content", "") or "")
        return str(getattr(first, "text", "") or "")
    return str(response)
