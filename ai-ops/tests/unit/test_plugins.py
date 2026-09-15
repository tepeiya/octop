"""competitor-crawler 插件单元测试。

只测纯函数逻辑（平台检测、字段提取、快照异动），不发网络请求。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ── 动态加载插件模块（不在 sys.path 里） ──

_PLUGIN_PATH = Path(__file__).resolve().parent.parent.parent / "plugins" / "competitor-crawler" / "main.py"

_spec = importlib.util.spec_from_file_location("competitor_crawler_main", _PLUGIN_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
sys.modules["competitor_crawler_main"] = _mod

detect_platform = _mod._detect_platform
extract_generic_fields = _mod._extract_generic_fields
snapshot_diff = _mod.snapshot_diff
parse_int = _mod._parse_int


# ──────────────────────────────────────────────────────────────────────────
# _detect_platform
# ──────────────────────────────────────────────────────────────────────────

class TestDetectPlatform:
    """URL → 平台标识符自动检测。"""

    @pytest.mark.parametrize("url,expected", [
        ("https://item.taobao.com/item.htm?id=123", "taobao"),
        ("https://detail.tmall.com/item.htm?id=456", "tmall"),
        ("https://item.jd.com/100123.html", "jd"),
        ("https://mobile.yangkeduo.com/goods.html?id=789", "pdd"),
        ("https://www.xiaohongshu.com/explore/abc123", "xiaohongshu"),
        ("https://www.douyin.com/video/123", "douyin"),
        ("https://xhslink.com/abc", "xiaohongshu"),
    ])
    def test_known_platforms(self, url: str, expected: str) -> None:
        assert detect_platform(url) == expected

    def test_unknown_falls_back_to_generic(self) -> None:
        assert detect_platform("https://example.com/product/123") == "generic"


# ──────────────────────────────────────────────────────────────────────────
# _extract_generic_fields
# ──────────────────────────────────────────────────────────────────────────

class TestExtractGenericFields:
    """HTML → 标准化字段提取。"""

    def test_extracts_title_price_sales_rating_comments(self) -> None:
        html = """
        <html><head><title>XX品牌 YYY - 官方旗舰店</title></head>
        <body>
          <div>¥99.9</div>
          <div>月销 1,234 件</div>
          <div>评分：4.8</div>
          <div>评价(567)</div>
        </body></html>
        """
        result = extract_generic_fields(html, "taobao")

        assert "XX品牌 YYY" in result["title"]
        assert result["price"] == 99.9
        assert "1,234" in result["sales"]
        assert result["rating"] == 4.8
        assert result["comments"] == 567

    def test_missing_fields_return_defaults(self) -> None:
        html = "<html><body><p>no useful data</p></body></html>"
        result = extract_generic_fields(html, "generic")

        assert result["price"] is None
        assert result["sales"] == ""
        assert result["rating"] is None
        assert result["comments"] == 0

    def test_title_truncated_to_200_chars(self) -> None:
        long_title = "A" * 500
        html = f"<html><head><title>{long_title}</title></head><body></body></html>"
        result = extract_generic_fields(html, "generic")
        assert len(result["title"]) == 200


# ──────────────────────────────────────────────────────────────────────────
# _parse_int
# ──────────────────────────────────────────────────────────────────────────

class TestParseInt:
    """字符串 → 整数解析（处理千位分隔符、中文单位等）。"""

    @pytest.mark.parametrize("raw,expected", [
        ("1,234", 1234),
        ("5678件", 5678),
        ("12,345", 12345),
        ("0", 0),
        ("", 0),
        (None, 0),
        (999, 999),  # 已经是 int
    ])
    def test_various_formats(self, raw, expected) -> None:
        assert parse_int(raw) == expected


# ──────────────────────────────────────────────────────────────────────────
# snapshot_diff
# ──────────────────────────────────────────────────────────────────────────

class TestSnapshotDiff:
    """快照异动检测——核心业务逻辑。"""

    def _make_snapshot(
        self,
        url: str = "https://item.jd.com/100.html",
        price: float | None = 99.9,
        sales: str = "1,000件",
        title: str = "XX品牌 YYY",
        comments: int = 100,
        platform: str = "jd",
    ) -> dict:
        return {
            "url": url,
            "platform": platform,
            "price": price,
            "sales": sales,
            "title": title,
            "comments": comments,
        }

    # ── 无异动 ──

    def test_no_changes_when_within_threshold(self) -> None:
        """价格变动 < 10% 不算异动。"""
        baseline = self._make_snapshot(price=100.0)
        current = self._make_snapshot(price=105.0)  # +5%, 低于 10% 阈值
        result = snapshot_diff(current, baseline)

        assert result["is_anomaly"] is False
        assert result["change_count"] == 0
        assert "无明显异动" in result["summary"]

    def test_no_changes_when_identical(self) -> None:
        baseline = self._make_snapshot()
        current = self._make_snapshot()
        result = snapshot_diff(current, baseline)

        assert result["is_anomaly"] is False
        assert result["change_count"] == 0

    # ── 价格异动 ──

    def test_price_increase_above_threshold(self) -> None:
        """价格上涨 ≥ 10% = 异动。"""
        baseline = self._make_snapshot(price=100.0)
        current = self._make_snapshot(price=120.0)  # +20%
        result = snapshot_diff(current, baseline)

        assert result["is_anomaly"] is True
        assert result["change_count"] == 1
        change = result["changes"][0]
        assert change["field"] == "price"
        assert change["direction"] == "上涨"
        assert change["delta_pct"] == 20.0
        assert change["severity"] == "medium"  # < 25%

    def test_price_decrease_above_threshold(self) -> None:
        baseline = self._make_snapshot(price=100.0)
        current = self._make_snapshot(price=80.0)  # -20%
        result = snapshot_diff(current, baseline)

        assert result["is_anomaly"] is True
        change = result["changes"][0]
        assert change["direction"] == "下降"
        assert change["delta_pct"] == -20.0

    def test_price_change_25_percent_is_high_severity(self) -> None:
        """价格变动 ≥ 25% = high severity。"""
        baseline = self._make_snapshot(price=100.0)
        current = self._make_snapshot(price=130.0)  # +30%
        result = snapshot_diff(current, baseline)

        assert result["changes"][0]["severity"] == "high"

    def test_price_drop_10_percent_boundary(self) -> None:
        """恰好 10% 是异动边界。"""
        baseline = self._make_snapshot(price=100.0)
        current = self._make_snapshot(price=90.0)  # -10%
        result = snapshot_diff(current, baseline)

        assert result["is_anomaly"] is True

    def test_price_newly_appears(self) -> None:
        """baseline 无价格、current 有价格 → 新增价格。"""
        baseline = self._make_snapshot(price=None)
        current = self._make_snapshot(price=99.9)
        result = snapshot_diff(current, baseline)

        price_changes = [c for c in result["changes"] if c["field"] == "price"]
        assert len(price_changes) == 1
        assert price_changes[0]["direction"] == "新增价格"

    # ── 销量异动 ──

    def test_sales_increase_above_30_percent(self) -> None:
        baseline = self._make_snapshot(sales="1,000件")
        current = self._make_snapshot(sales="1,500件")  # +50%
        result = snapshot_diff(current, baseline)

        sales_changes = [c for c in result["changes"] if c["field"] == "sales"]
        assert len(sales_changes) == 1
        assert sales_changes[0]["direction"] == "上涨"
        assert sales_changes[0]["delta_pct"] == 50.0

    def test_sales_below_threshold_no_anomaly(self) -> None:
        baseline = self._make_snapshot(sales="1,000件")
        current = self._make_snapshot(sales="1,200件")  # +20%, 低于 30%
        result = snapshot_diff(current, baseline)

        sales_changes = [c for c in result["changes"] if c["field"] == "sales"]
        assert len(sales_changes) == 0

    # ── 新上架 ──

    def test_new_product_detection(self) -> None:
        """baseline title 为空、current 有 title → 新上架。"""
        baseline = self._make_snapshot(title="")
        current = self._make_snapshot(title="全新商品 ZZZ")
        result = snapshot_diff(current, baseline)

        new_changes = [c for c in result["changes"] if c["field"] == "new_product"]
        assert len(new_changes) == 1
        assert new_changes[0]["severity"] == "high"

    # ── 评论增长 ──

    def test_comments_growth_50_plus(self) -> None:
        """评论日增 ≥ 50 → 低 severity 异动。"""
        baseline = self._make_snapshot(comments=200)
        current = self._make_snapshot(comments=260)  # +60
        result = snapshot_diff(current, baseline)

        comment_changes = [c for c in result["changes"] if c["field"] == "comments"]
        assert len(comment_changes) == 1
        assert comment_changes[0]["severity"] == "low"

    def test_comments_below_100_no_anomaly(self) -> None:
        """评论数 < 100 不触发评论异动。"""
        baseline = self._make_snapshot(comments=50)
        current = self._make_snapshot(comments=110)  # +60 but base < 100
        result = snapshot_diff(current, baseline)

        comment_changes = [c for c in result["changes"] if c["field"] == "comments"]
        assert len(comment_changes) == 0

    # ── 多字段同时异动 ──

    def test_multiple_fields_change_simultaneously(self) -> None:
        """价格 + 销量 + 评论同时异动。"""
        baseline = self._make_snapshot(price=100.0, sales="1,000件", comments=200)
        current = self._make_snapshot(price=120.0, sales="2,000件", comments=300)
        result = snapshot_diff(current, baseline)

        assert result["is_anomaly"] is True
        assert result["change_count"] == 3
        fields = {c["field"] for c in result["changes"]}
        assert fields == {"price", "sales", "comments"}

    # ── summary 格式 ──

    def test_summary_contains_emoji_and_numbers(self) -> None:
        baseline = self._make_snapshot(price=100.0)
        current = self._make_snapshot(price=130.0)
        result = snapshot_diff(current, baseline)

        summary = result["summary"]
        assert "📈" in summary  # 上涨 emoji
        assert "30" in summary  # 百分比
        assert "100" in summary and "130" in summary  # 价格区间


# ──────────────────────────────────────────────────────────────────────────
# 插件 setup() 注册
# ──────────────────────────────────────────────────────────────────────────

class TestPluginSetup:
    """验证 setup() 注册了正确的工具。"""

    def test_setup_registers_two_tools(self) -> None:
        from unittest.mock import MagicMock

        ctx = MagicMock()
        _mod.setup(ctx)

        assert ctx.tool.call_count == 2
        names = [call.args[0] for call in ctx.tool.call_args_list]
        assert "crawl_competitor" in names
        assert "snapshot_diff" in names

    def test_tool_descriptions_contain_keywords(self) -> None:
        from unittest.mock import MagicMock

        ctx = MagicMock()
        _mod.setup(ctx)

        descriptions = [call.kwargs.get("description", "") for call in ctx.tool.call_args_list]
        all_text = " ".join(str(d) for d in descriptions)
        assert "爬取" in all_text
        assert "异动" in all_text
        assert "snapshot" in all_text.lower()
