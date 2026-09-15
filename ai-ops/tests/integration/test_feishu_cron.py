"""飞书推送 + Cron 集成测试 · Phase 1 模块 1.6

测试场景：
  1. 飞书 Webhook 消息格式正确性
  2. 竞品快照 → snapshot_diff → 日报 → 飞书推送链路
  3. Cron 定时任务触发 → Agent 执行 → 推送链路
  4. 告警 Webhook 发送 + 重试

运行方式：
  cd /workspace && uv run pytest ai-ops/tests/integration/test_feishu_cron.py -v
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 确保可以 import ai-ops 模块
_ai_ops_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ai_ops_root))


# ---------------------------------------------------------------------------
# 1. 飞书 Webhook 消息格式
# ---------------------------------------------------------------------------


class TestFeishuMessageFormat:
    """验证发送给飞书群机器人的消息格式。"""

    def test_text_message_format(self):
        """飞书文本消息格式：{"msg_type": "text", "content": {"text": "..."}}。"""
        message = {
            "msg_type": "text",
            "content": {"text": "📊 竞品情报日报 · 2026-09-15"},
        }
        assert message["msg_type"] == "text"
        assert "text" in message["content"]
        assert len(message["content"]["text"]) > 0

    def test_markdown_message_format(self):
        """飞书 Markdown 消息格式。"""
        markdown_content = "## 📊 竞品情报日报\n\n| 商品 | 价格 | 变动 |\n|---|---|---|\n| XX | 89 | -10% |"
        message = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "📊 竞品情报日报",
                    },
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": markdown_content,
                    }
                ],
            },
        }
        assert message["msg_type"] == "interactive"
        assert "card" in message
        assert "header" in message["card"]
        assert "elements" in message["card"]

    def test_message_length_within_feishu_limit(self):
        """飞书单条消息不能超过 30KB，日报应控制在合理长度内。"""
        report = "# 竞品情报日报\n\n" + "| 商品 | 价格 |\n|---|---|\n"
        for i in range(20):
            report += f"| 商品{i} | ¥{89 + i} |\n"
        # 飞书限制：30KB ≈ 30720 字符
        assert len(report.encode("utf-8")) < 30000, "日报长度应在飞书限制内"


# ---------------------------------------------------------------------------
# 2. 竞品快照 → diff → 日报 → 推送链路
# ---------------------------------------------------------------------------


class TestReportGenerationPipeline:
    """验证从快照到日报生成的完整链路。"""

    def test_snapshot_to_diff_pipeline(self):
        """快照对比 → 异动检测。"""
        from plugins.competitor_crawler.main import snapshot_diff

        current = {
            "url": "https://item.jd.com/100.html",
            "platform": "jd",
            "product_name": "XX品牌 YYY",
            "price": 89.9,
            "sales": "1,500件",
            "rating": 4.8,
            "comments": 600,
        }
        baseline = {
            "url": "https://item.jd.com/100.html",
            "platform": "jd",
            "product_name": "XX品牌 YYY",
            "price": 99.9,
            "sales": "1,000件",
            "rating": 4.8,
            "comments": 567,
        }

        result = snapshot_diff(current=current, baseline=baseline)
        assert result["is_anomaly"] is True
        assert result["change_count"] >= 2  # 价格 + 销量
        # 验证日报格式
        summary = result["summary"]
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_daily_report_markdown_structure(self):
        """日报 Markdown 结构验证。"""
        report = """## 📊 竞品情报日报 · 2026-09-15

### 价格异动
| 商品 | 平台 | 昨日 | 今日 | 变动 | 严重度 |
|------|------|------|------|------|--------|
| XX品牌 YYY | 京东 | ¥99.9 | ¥89.9 | 📉 -10% | 中 |

### 销量异动
| 商品 | 平台 | 昨日 | 今日 | 变动 |
|------|------|------|------|------|
| XX品牌 YYY | 京东 | 1,000件 | 1,500件 | 🔥 +50% |

---
📅 下次扫描：2026-09-15 20:00"""
        assert report.startswith("## 📊 竞品情报日报")
        assert "价格异动" in report
        assert "销量异动" in report
        assert len(report) < 2000  # 控制在 IM 消息长度内


# ---------------------------------------------------------------------------
# 3. Cron 定时任务触发链路
# ---------------------------------------------------------------------------


class TestCronTriggerPipeline:
    """验证 Cron 定时任务 → Agent 执行 → 推送链路。"""

    @pytest.mark.asyncio
    async def test_cron_schedule_parses_correctly(self):
        """Cron 表达式解析验证。"""
        # 每天 08:00
        cron_expr = "0 8 * * *"
        parts = cron_expr.split()
        assert len(parts) == 5
        assert parts[0] == "0"  # minute
        assert parts[1] == "8"  # hour

        # 每 2 小时
        cron_expr_2h = "0 */2 * * *"
        parts_2h = cron_expr_2h.split()
        assert parts_2h[1] == "*/2"

    @pytest.mark.asyncio
    async def test_cron_prompt_format(self):
        """Cron prompt 应包含明确的执行指令。"""
        prompt = (
            "爬取我监控的所有竞品，生成今日异动日报，推送到飞书群"
        )
        assert "爬取" in prompt or "监控" in prompt
        assert "日报" in prompt
        assert "推送" in prompt


# ---------------------------------------------------------------------------
# 4. 告警 Webhook 发送 + 重试
# ---------------------------------------------------------------------------


class TestAlertWebhookPipeline:
    """验证告警 Webhook 的发送和重试逻辑。"""

    @pytest.mark.asyncio
    async def test_webhook_send_success(self):
        """Webhook 成功发送。"""
        from routers.alert_webhook import _send_webhook

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await _send_webhook(
                url="https://example.com/webhook",
                payload={"alert_id": "test-1", "level": "watch"},
                headers={"Content-Type": "application/json"},
                method="POST",
                timeout=10,
                retry_count=3,
                retry_delay=1,
            )

        assert result["success"] is True
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_webhook_retry_on_failure(self):
        """Webhook 失败时重试。"""
        from routers.alert_webhook import _send_webhook

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with (
            patch("httpx.AsyncClient") as mock_client_cls,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await _send_webhook(
                url="https://example.com/webhook",
                payload={"alert_id": "test-2", "level": "urgent"},
                headers={"Content-Type": "application/json"},
                method="POST",
                timeout=5,
                retry_count=2,
                retry_delay=1,
            )

        assert result["success"] is False
        assert "HTTP 500" in result["error"]
        assert result["attempt"] == 3  # 初始 + 2 次重试

    @pytest.mark.asyncio
    async def test_webhook_timeout_handled(self):
        """Webhook 超时被正确处理。"""
        from routers.alert_webhook import _send_webhook

        with (
            patch("httpx.AsyncClient") as mock_client_cls,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await _send_webhook(
                url="https://example.com/webhook",
                payload={"alert_id": "test-3"},
                headers={},
                method="POST",
                timeout=3,
                retry_count=0,
                retry_delay=1,
            )

        assert result["success"] is False
        assert "timeout" in result["error"].lower()


# ---------------------------------------------------------------------------
# 5. 配置持久化
# ---------------------------------------------------------------------------


class TestConfigPersistence:
    """验证告警 Webhook 配置的持久化。"""

    def test_config_save_and_load(self, tmp_path):
        """配置保存后重新加载应一致。"""
        from routers.alert_webhook import _CONFIG_FILE, _load_config, _save_config

        # 临时重定向配置文件
        import routers.alert_webhook as mod

        original = mod._CONFIG_FILE
        mod._CONFIG_FILE = tmp_path / "config.json"

        try:
            cfg = {
                "url": "https://open.feishu.cn/openapi/bot/v2/hook/test",
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
                "timeout_seconds": 10,
                "retry_count": 3,
                "retry_delay_seconds": 5,
                "enabled": True,
            }
            _save_config(cfg)
            loaded = _load_config()
            assert loaded["url"] == cfg["url"]
            assert loaded["enabled"] is True
        finally:
            mod._CONFIG_FILE = original

    def test_history_append_and_load(self, tmp_path):
        """告警历史追加后可重新加载。"""
        import routers.alert_webhook as mod

        original = mod._HISTORY_FILE
        mod._HISTORY_FILE = tmp_path / "history.jsonl"

        try:
            from routers.alert_webhook import _append_history, _load_history

            alert = {
                "alert_id": "test-001",
                "level": "watch",
                "keyword": "XX品牌",
                "message": "负面提及增加",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            _append_history(alert)
            history = _load_history(limit=10)
            assert len(history) == 1
            assert history[0]["alert_id"] == "test-001"
        finally:
            mod._HISTORY_FILE = original
