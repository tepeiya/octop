"""社交媒体爬虫 · Phase 2 TODO stub。

当前是占位——让仓库骨架完整、能被 Octop 正常发现。
Phase 2 实现：
  - crawl_social_feed(ctx, platform, keyword) → 平台搜索结果页条目
  - crawl_social_comments(ctx, platform, note_url) → 评论列表
  - detect_anomaly(...) → 评论暴涨 / 热搜异动
"""
from __future__ import annotations
from typing import Any
from harness_agent.plugins import PluginContext


async def crawl_social_feed(
    ctx: PluginContext, platform: str, keyword: str, limit: int = 20
) -> dict[str, Any]:
    """爬取指定平台的搜索/热榜结果。"""
    return {
        "ok": False,
        "status": "stub",
        "message": "Phase 2 实现：social-scraper 插件。当前请用 competitor-crawler 的 crawl_competitor 作为参考。",
        "platform": platform,
        "keyword": keyword,
        "limit": limit,
    }


async def crawl_social_comments(
    ctx: PluginContext, platform: str, note_url: str
) -> dict[str, Any]:
    """爬取笔记/视频的评论区。"""
    return {
        "ok": False,
        "status": "stub",
        "message": "Phase 2 实现：social-scraper.crawl_social_comments。",
        "platform": platform,
        "note_url": note_url,
    }


def setup(ctx: PluginContext) -> None:
    ctx.tool(
        "crawl_social_feed",
        crawl_social_feed,
        description="Phase 2 · 爬取指定平台的搜索/热榜结果。参数 platform (xiaohongshu/douyin/bilibili/zhihu/weibo)，keyword 搜索词，limit 条数。",
    )
    ctx.tool(
        "crawl_social_comments",
        crawl_social_comments,
        description="Phase 2 · 爬取笔记/视频的评论区。参数 platform 和 note_url。",
    )
