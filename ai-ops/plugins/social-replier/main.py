"""自动评论回复 · Phase 2 TODO stub。

Phase 2 实现要点：
  - 走 harness-browser Chromium，需要 Agent 预先登录目标平台
  - 所有回复必须标记 require_approval=true，HITL 队列里人工批准后才真的发
  - 话术库走知识库 RAG 匹配（不允许 Agent 自由生成，避免违规）
"""
from __future__ import annotations
from typing import Any
from harness_agent.plugins import PluginContext


async def draft_reply(
    ctx: PluginContext,
    platform: str,
    comment_url: str,
    reply_text: str,
) -> dict[str, Any]:
    """起草一条回复（不实际发送，必须经 HITL 审批后再执行）。"""
    return {
        "ok": False,
        "status": "stub",
        "message": "Phase 2 实现：draft_reply + 浏览器 AI+ 自动发送 + 强制 HITL 审批。",
        "platform": platform,
        "comment_url": comment_url,
        "reply_text": reply_text,
        "require_approval": True,  # ← 强默认，绝不放行
    }


def setup(ctx: PluginContext) -> None:
    ctx.tool(
        "draft_reply",
        draft_reply,
        description=(
            "Phase 2 · 起草一条回复。参数 platform、comment_url、reply_text。"
            "始终返回 require_approval=true——真实发送需要 HITL 人工审批后再执行。"
        ),
    )
