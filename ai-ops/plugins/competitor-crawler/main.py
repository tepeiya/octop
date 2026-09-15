"""竞品情报爬虫插件 · Phase 1 MVP

核心工具（harness-agent 插件协议）：
  - crawl_competitor()  爬取单个竞品 URL，返回标准化快照
  - snapshot_diff()     对比两个快照，标记异动字段

每个工具返回 dict，Agent 可以直接消费或写入 workspace 文件。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from bs4 import BeautifulSoup
from harness_agent.plugins import PluginContext

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

_PLATFORM_PATTERNS: dict[str, re.Pattern[str]] = {
    "taobao": re.compile(r"(?:item|detail)\.taobao\.com|taobao\.com"),
    "tmall": re.compile(r"detail\.tmall\.com|tmall\.com"),
    "jd": re.compile(r"item\.jd\.com|jd\.com/product"),
    "pdd": re.compile(r"mobile\.yangkeduo\.com|yangkeduo\.com"),
    "xiaohongshu": re.compile(r"xiaohongshu\.com|xhslink\.com"),
    "douyin": re.compile(r"douyin\.com|iesdouyin\.com"),
    "generic": re.compile(r""),
}


def _detect_platform(url: str) -> str:
    for platform, pattern in _PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return "generic"


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=20.0,
        follow_redirects=True,
        headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"},
    )


# ---------------------------------------------------------------------------
# 主工具：crawl_competitor
# ---------------------------------------------------------------------------

async def crawl_competitor(
    ctx: PluginContext,
    url: str,
    platform: str | None = None,
    mode: Literal["http", "browser"] = "http",
    product_name: str = "",
) -> dict[str, Any]:
    """爬取单个竞品页面，返回标准化快照。

    Args:
        ctx: harness-agent 插件上下文（提供 browser / workspace 等）。
        url: 竞品页面 URL。
        platform: 平台标识，自动检测时传 None（可选值见 _PLATFORM_PATTERNS）。
        mode: 爬取方式。"http" 用 httpx 直接请求，"browser" 走 Chromium。
        product_name: 可选，Agent 提供的商品名（用于结果展示）。

    Returns:
        标准化快照字典，包含 url / platform / product_name / price /
        title / sales / rating / comments / fetched_at / snapshot_hash / raw_html。
    """
    platform = platform or _detect_platform(url)
    snapshot: dict[str, Any] = {
        "url": url,
        "platform": platform,
        "product_name": product_name,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "price": None,
        "title": "",
        "sales": "",
        "rating": None,
        "comments": 0,
        "snapshot_hash": "",
    }

    raw_html = ""

    if mode == "browser":
        raw_html = await _crawl_via_browser(ctx, url)
    else:
        raw_html = await _crawl_via_http(url)

    if not raw_html:
        snapshot["error"] = "failed to fetch page content"
        return snapshot

    # 从 HTML 中提取通用字段（BeautifulSoup 解析）
    parsed = _extract_generic_fields(raw_html, platform)
    snapshot.update(parsed)
    snapshot["raw_html"] = raw_html[:2000]  # 仅保留前 2KB（token 保护）
    snapshot["snapshot_hash"] = hashlib.sha256(raw_html.encode()).hexdigest()[:16]

    return snapshot


# ---------------------------------------------------------------------------
# 辅助：两种爬取实现
# ---------------------------------------------------------------------------

async def _crawl_via_http(url: str) -> str:
    """用 httpx 请求页面 HTML。"""
    try:
        with _client() as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
    except httpx.HTTPError as exc:
        return ""


async def _crawl_via_browser(ctx: PluginContext, url: str) -> str:
    """用 harness-browser 控制 Chromium 获取页面 HTML。

    PluginContext.browser 由 harness-agent 注入，实际类型是 harness-browser
    的 BrowserSession，支持 goto() / evaluate() / screenshot() 等 CDP 操作。
    """
    try:
        browser = ctx.browser
        page = await browser.goto(url)
        # 等待一下让 JS 渲染
        await browser.evaluate("() => document.readyState === 'complete'")
        html = await browser.evaluate("() => document.documentElement.outerHTML")
        return html or ""
    except Exception:
        # harness-browser 未启用或 Chromium 启动失败时静默返回空
        return ""


# ---------------------------------------------------------------------------
# 通用字段提取（启发式，够用就行——详细正则放到各平台的 profile 里）
# ---------------------------------------------------------------------------

_PRICE_RE = re.compile(
    r"¥?\s*(\d{1,6}(?:[.,]\d{1,2})?)\s*(?:元|块|rmb|RMB|CNY)?",
    re.IGNORECASE,
)
_SALES_RE = re.compile(r"月销?\s*([\d.,]+)\s*(?:\+?\s*(?:件|单))?")
_RATING_RE = re.compile(r"评分[：:]\s*(\d\.\d)")
_COMMENTS_RE = re.compile(r"评价[（(]?\s*([\d.,]+)")


def _extract_generic_fields(html: str, platform: str) -> dict[str, Any]:
    """从 HTML 中提取通用字段。各平台 profile 后续会覆盖更精确的提取逻辑。"""
    soup = BeautifulSoup(html, "html.parser")

    # title: <title> 标签
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # 价格：遍历所有文本节点找价格模式
    all_text = soup.get_text(separator="\n")
    price_match = _PRICE_RE.search(all_text)
    price: float | None = None
    if price_match:
        try:
            price = float(price_match.group(1).replace(",", ""))
        except ValueError:
            price = None

    # 销量
    sales_match = _SALES_RE.search(all_text)
    sales = sales_match.group(1) if sales_match else ""

    # 评分
    rating_match = _RATING_RE.search(all_text)
    rating = float(rating_match.group(1)) if rating_match else None

    # 评价数
    comments_match = _COMMENTS_RE.search(all_text)
    comments = 0
    if comments_match:
        try:
            comments = int(comments_match.group(1).replace(",", ""))
        except ValueError:
            comments = 0

    return {
        "title": title[:200],  # 截断保护
        "price": price,
        "sales": sales,
        "rating": rating,
        "comments": comments,
    }


# ---------------------------------------------------------------------------
# 主工具：snapshot_diff
# ---------------------------------------------------------------------------

_ANOMALY_THRESHOLD_PRICE = 0.10   # ±10% 价格变动 = 异动
_ANOMALY_THRESHOLD_SALES = 0.30   # ±30% 销量变动 = 异动
_ANOMALY_NEW = "new"              # 新上架


def snapshot_diff(
    current: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    """对比两个快照，返回异动摘要。

    Args:
        current: 新的 crawl_competitor() 结果。
        baseline: 上一次 crawl_competitor() 结果（来自 workspace 文件或知识库）。

    Returns:
        包含 is_anomaly / changes / summary 的异动报告。
    """
    changes: list[dict[str, Any]] = []

    # 价格变动
    cur_price = current.get("price")
    base_price = baseline.get("price")
    if cur_price is not None and base_price is not None and base_price != 0:
        delta = (cur_price - base_price) / base_price
        if abs(delta) >= _ANOMALY_THRESHOLD_PRICE:
            direction = "上涨" if delta > 0 else "下降"
            changes.append({
                "field": "price",
                "direction": direction,
                "delta_pct": round(delta * 100, 1),
                "from": base_price,
                "to": cur_price,
                "severity": "high" if abs(delta) >= 0.25 else "medium",
            })
    elif cur_price is not None and base_price is None:
        changes.append({
            "field": "price",
            "direction": "新增价格",
            "delta_pct": None,
            "from": None,
            "to": cur_price,
            "severity": "medium",
        })

    # 销量变动
    cur_sales = _parse_int(current.get("sales", ""))
    base_sales = _parse_int(baseline.get("sales", ""))
    if cur_sales and base_sales and base_sales != 0:
        delta = (cur_sales - base_sales) / base_sales
        if abs(delta) >= _ANOMALY_THRESHOLD_SALES:
            direction = "上涨" if delta > 0 else "下降"
            changes.append({
                "field": "sales",
                "direction": direction,
                "delta_pct": round(delta * 100, 1),
                "from": base_sales,
                "to": cur_sales,
                "severity": "high" if abs(delta) >= 0.50 else "medium",
            })

    # 新上架
    if baseline.get("title") in (None, "") and current.get("title"):
        changes.append({
            "field": "new_product",
            "direction": _ANOMALY_NEW,
            "delta_pct": None,
            "from": None,
            "to": current.get("title"),
            "severity": "high",
        })

    # 评价数显著增长
    cur_comments = current.get("comments", 0)
    base_comments = baseline.get("comments", 0)
    if cur_comments >= 100 and base_comments >= 100:
        growth = cur_comments - base_comments
        if growth >= 50:
            changes.append({
                "field": "comments",
                "direction": "增长",
                "delta_pct": round(growth / max(base_comments, 1) * 100, 1),
                "from": base_comments,
                "to": cur_comments,
                "severity": "low",
            })

    summary = _build_summary(current, changes)

    return {
        "url": current.get("url"),
        "platform": current.get("platform"),
        "product_name": current.get("product_name") or current.get("title", "")[:50],
        "is_anomaly": len(changes) > 0,
        "change_count": len(changes),
        "changes": changes,
        "summary": summary,
    }


def _parse_int(raw: str | int | None) -> int:
    if raw is None:
        return 0
    if isinstance(raw, int):
        return raw
    return int(re.sub(r"[^\d]", "", str(raw)) or 0)


def _build_summary(current: dict[str, Any], changes: list[dict[str, Any]]) -> str:
    if not changes:
        return "无明显异动。"
    parts: list[str] = []
    for ch in changes:
        if ch["field"] == "new_product":
            parts.append(f"🆕 新上架：{ch['to']}")
        elif ch["field"] == "price":
            arrow = "📈" if ch["direction"] == "上涨" else "📉"
            parts.append(f"{arrow} 价格{ch['direction']} {ch['delta_pct']}%（¥{ch['from']}→¥{ch['to']}）")
        elif ch["field"] == "sales":
            arrow = "🔥" if ch["direction"] == "上涨" else "❄️"
            parts.append(f"{arrow} 销量{ch['direction']} {ch['delta_pct']}%")
        elif ch["field"] == "comments":
            parts.append(f"💬 评论增长 {ch['delta_pct']}%（+{ch['to'] - ch['from']} 条）")
    return "；".join(parts)


# ---------------------------------------------------------------------------
# harness-agent 插件入口：注册工具
# ---------------------------------------------------------------------------

def setup(ctx: PluginContext) -> None:
    ctx.tool(
        "crawl_competitor",
        crawl_competitor,
        description=(
            "爬取单个竞品页面并返回标准化快照。"
            "参数 url 必填；platform 可选（taobao/tmall/jd/pdd/xiaohongshu/douyin，不传自动检测）；"
            "mode 可选（http=默认走 httpx，browser=走 Chromium 用于绕过简单反爬）；"
            "product_name 可选，用于结果展示。"
            "返回字段：price/title/sales/rating/comments/fetched_at/snapshot_hash。"
        ),
    )
    ctx.tool(
        "snapshot_diff",
        snapshot_diff,
        description=(
            "对比两个竞品快照，返回异动报告。"
            "参数 current 是 crawl_competitor 新结果；baseline 是上一次结果（通常来自 workspace 文件）。"
            "识别的异动类型：价格 ±10%、销量 ±30%、新上架、评论日增 ≥50。"
            "返回字段：is_anomaly/change_count/changes/summary。"
        ),
    )
