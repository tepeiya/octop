"""情感分析追踪 · Phase 2 TODO stub。"""
from __future__ import annotations
from typing import Any
from harness_agent.plugins import PluginContext


async def analyze_sentiment(ctx: PluginContext, text: str | list[str]) -> dict[str, Any]:
    """对文本做情感分类。"""
    return {
        "ok": False,
        "status": "stub",
        "message": "Phase 2 实现：调用 LLM 或本地模型做 sentiment 分类。",
        "input_type": type(text).__name__,
    }


async def classify_crisis(
    ctx: PluginContext, items: list[dict[str, Any]]
) -> dict[str, Any]:
    """从一批评论/笔记里识别危机条目并分级。"""
    return {
        "ok": False,
        "status": "stub",
        "message": "Phase 2 实现：按热度+负面程度分 3 级（观察/关注/紧急）。",
        "items_received": len(items),
    }


def setup(ctx: PluginContext) -> None:
    ctx.tool(
        "analyze_sentiment",
        analyze_sentiment,
        description="Phase 2 · 情感分类。参数 text 可以是单条 str 或 list[str]。返回正面/中性/负面 + 置信度。",
    )
    ctx.tool(
        "classify_crisis",
        classify_crisis,
        description="Phase 2 · 危机分级。参数 items 是评论/笔记 dict 列表。",
    )
