"""电商自动化插件 · Phase 3 模块 3.3

功能：
  - 自动改价：根据竞品价格 + 库存 + 销量策略自动调价（强制 HITL）
  - 自动上新：根据竞品动态推荐上新方向
  - 库存同步：跨平台库存查询和预警

设计原则：
  - 所有写操作强制 require_approval=true
  - 改价幅度有硬限制（±20%），超出需人工确认
  - 依赖 ecom_backend Connector 做实际 API 调用
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 安全限制
MAX_PRICE_CHANGE_PCT = 20  # 单次改价最大幅度 ±20%
LOW_STOCK_THRESHOLD = 10   # 库存预警阈值


async def auto_adjust_price(
    ctx: Any,
    platform: str,
    product_id: str,
    product_name: str,
    current_price: float,
    competitor_price: float,
    our_stock: int,
    our_daily_sales: int,
) -> dict[str, Any]:
    """根据竞品价格 + 库存 + 销量策略自动建议改价。

    策略逻辑：
      1. 竞品比我便宜 > 5% → 建议降价（但不超过 MAX_PRICE_CHANGE_PCT）
      2. 竞品比我贵 > 5% → 建议涨价（抓利润）
      3. 我的库存 > 阈值 + 日销量低 → 建议降价（去库存）
      4. 我的库存 < 阈值 + 日销量高 → 建议涨价（控量）

    Args:
        platform: 平台名称
        product_id: 商品 ID
        product_name: 商品名称
        current_price: 当前价格
        competitor_price: 竞品价格
        our_stock: 我们的库存
        our_daily_sales: 我们昨日销量
    """
    # 计算建议
    price_diff_pct = (
        (current_price - competitor_price) / competitor_price * 100
        if competitor_price > 0
        else 0
    )

    suggestion = None
    reason = ""

    if price_diff_pct > 5 and our_stock < LOW_STOCK_THRESHOLD:
        # 我贵 + 库存低 → 涨价
        change_pct = min(price_diff_pct / 2, MAX_PRICE_CHANGE_PCT)
        new_price = round(current_price * (1 - change_pct / 100), 2)
        suggestion = "raise"
        reason = f"竞品 ¥{competitor_price}，我方 ¥{current_price}（贵 {price_diff_pct:.1f}%），库存 {our_stock} 偏低 → 建议涨价"
    elif price_diff_pct < -5 and our_stock > LOW_STOCK_THRESHOLD:
        # 我便宜但库存高 → 保持，不跟降
        suggestion = "hold"
        reason = f"我方已比竞品便宜 {-price_diff_pct:.1f}%，库存 {our_stock} 充足 → 建议保持"
    elif our_stock > LOW_STOCK_THRESHOLD * 3 and our_daily_sales < 5:
        # 库存高 + 销量低 → 降价去库存
        change_pct = min(10, MAX_PRICE_CHANGE_PCT)
        new_price = round(current_price * (1 - change_pct / 100), 2)
        suggestion = "lower"
        reason = f"库存 {our_stock} 偏高，日销 {our_daily_sales} 偏低 → 建议降价去库存"
    else:
        suggestion = "hold"
        new_price = current_price
        reason = "当前价格在合理区间，建议保持"

    # 安全检查：改价幅度不超过限制
    if suggestion in ("raise", "lower"):
        actual_change = abs(new_price - current_price) / current_price * 100
        if actual_change > MAX_PRICE_CHANGE_PCT:
            new_price = round(
                current_price * (1 + (MAX_PRICE_CHANGE_PCT / 100) * (1 if suggestion == "raise" else -1)),
                2,
            )
            reason += f"（改价幅度已限制在 ±{MAX_PRICE_CHANGE_PCT}%）"

    result = {
        "product_name": product_name,
        "platform": platform,
        "current_price": current_price,
        "competitor_price": competitor_price,
        "suggestion": suggestion,
        "suggested_price": new_price if suggestion != "hold" else current_price,
        "change_pct": round(
            (new_price - current_price) / current_price * 100, 2
        ) if suggestion != "hold" else 0,
        "reason": reason,
        "require_approval": True,  # 强制审批
        "stock": our_stock,
        "daily_sales": our_daily_sales,
    }

    logger.info(
        "price suggestion for %s: %s %s -> %s (%s)",
        product_name, suggestion, current_price, new_price, reason,
    )
    return result


async def recommend_new_listing(
    ctx: Any,
    competitor_trends: list[dict[str, Any]],
    our_categories: list[str],
) -> dict[str, Any]:
    """根据竞品上新趋势推荐上新方向。

    Args:
        competitor_trends: 竞品上新趋势列表（从 crawl_competitor 获取）
        our_categories: 我方已有品类列表
    """
    recommendations = []

    for trend in competitor_trends:
        product_name = trend.get("product_name", "")
        category = trend.get("category", "")
        competitor_sales = trend.get("sales", 0)
        our_coverage = category in our_categories if category else False

        # 如果竞品这个品类卖得好，我们还没覆盖 → 推荐
        if competitor_sales and competitor_sales > 100 and not our_coverage:
            recommendations.append({
                "product_name": product_name,
                "category": category,
                "competitor": trend.get("competitor", ""),
                "estimated_demand": "high" if competitor_sales > 500 else "medium",
                "reason": f"竞品 {trend.get('competitor', '')} 此品类月销 {competitor_sales}+，我方未覆盖",
                "priority": "high" if competitor_sales > 500 else "medium",
            })

    # 按优先级排序
    recommendations.sort(
        key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["priority"], 3)
    )

    return {
        "recommendations": recommendations[:10],  # 最多推荐 10 个
        "total_found": len(recommendations),
        "require_approval": False,  # 只是建议，不需审批
    }


async def check_low_stock(
    ctx: Any,
    platform: str,
    product_list: list[dict[str, Any]],
) -> dict[str, Any]:
    """检查库存预警。

    Args:
        platform: 平台名称
        product_list: 商品列表（含 stock 字段）
    """
    low_stock_items = [
        {
            "product_name": p.get("product_name", ""),
            "product_id": p.get("product_id", ""),
            "stock": p.get("stock", 0),
            "daily_sales": p.get("daily_sales", 0),
            "days_remaining": (
                p.get("stock", 0) / p.get("daily_sales", 1)
                if p.get("daily_sales", 0) > 0
                else None
            ),
        }
        for p in product_list
        if p.get("stock", 0) < LOW_STOCK_THRESHOLD
    ]

    # 按剩余天数排序（最紧急的在前）
    low_stock_items.sort(
        key=lambda x: x["days_remaining"] if x["days_remaining"] else 999
    )

    return {
        "platform": platform,
        "total_checked": len(product_list),
        "low_stock_count": len(low_stock_items),
        "low_stock_items": low_stock_items,
        "alert_level": "urgent" if len(low_stock_items) > 5 else "watch",
        "require_approval": False,
    }


TOOLS = [
    auto_adjust_price,
    recommend_new_listing,
    check_low_stock,
]
