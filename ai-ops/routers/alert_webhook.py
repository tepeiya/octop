"""危机告警 Webhook API · Phase 2 模块 2.8

功能：
  - GET  /alerts/config    → 读取告警 Webhook 配置
  - PUT  /alerts/config    → 更新告警 Webhook 配置（URL + Headers + 重试策略）
  - POST /alerts/test      → 发送测试告警到配置的 Webhook
  - GET  /alerts/history   → 查看告警历史
  - POST /alerts/acknowledge → 确认告警已处理

设计原则（遵循 AGENTS.md §5）:
  - 路由层只做 HTTP 校验 → 调 infra → 映射错误
  - 不在路由里写业务规则
  - Webhook 发送逻辑放在 plugins/ 里（Agent 调工具触发），此路由只管理配置

注意：此文件是扩展层的一部分，安装方式：
  cp routers/alert_webhook.py → ~/.octop/extensions/routers/
  Octop 启动时自动发现（需在 app.py 中 mount）
  或作为独立 FastAPI 微服务运行
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# 存储：配置存 JSON 文件，历史存 JSONL（Phase 3 迁移到 DB）
# ---------------------------------------------------------------------------

_CONFIG_DIR = Path.home() / ".octop" / "alerts"
_CONFIG_FILE = _CONFIG_DIR / "config.json"
_HISTORY_FILE = _CONFIG_DIR / "history.jsonl"


def _ensure_dirs() -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Pydantic 请求/响应模型
# ---------------------------------------------------------------------------


class WebhookConfigBody(BaseModel):
    """告警 Webhook 配置请求体。"""

    url: str = Field(..., description="Webhook 目标 URL，告警将 POST 到此地址")
    method: str = Field(default="POST", description="HTTP 方法")
    headers: dict[str, str] = Field(
        default_factory=lambda: {"Content-Type": "application/json"},
        description="自定义请求头",
    )
    timeout_seconds: int = Field(default=10, ge=1, le=60, description="请求超时")
    retry_count: int = Field(default=3, ge=0, le=10, description="失败重试次数")
    retry_delay_seconds: int = Field(
        default=5, ge=1, le=300, description="重试间隔（指数退避基数）"
    )
    enabled: bool = Field(default=True, description="是否启用")


class AlertPayload(BaseModel):
    """告警数据结构。"""

    alert_id: str = Field(..., description="告警唯一 ID")
    level: str = Field(..., description="级别: urgent / watch / observe")
    keyword: str = Field(..., description="触发关键词")
    platform: str = Field(..., description="平台")
    message: str = Field(..., description="告警摘要")
    details: dict[str, Any] = Field(default_factory=dict, description="详情")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="触发时间",
    )


class AlertTestBody(BaseModel):
    """测试告警请求体。"""

    level: str = Field(default="watch", description="测试级别")
    keyword: str = Field(default="测试关键词", description="测试关键词")


# ---------------------------------------------------------------------------
# 配置读写
# ---------------------------------------------------------------------------


def _load_config() -> dict[str, Any]:
    _ensure_dirs()
    if _CONFIG_FILE.exists():
        return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
    return {"url": "", "method": "POST", "headers": {}, "enabled": False}


def _save_config(cfg: dict[str, Any]) -> None:
    _ensure_dirs()
    _CONFIG_FILE.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _append_history(alert: dict[str, Any]) -> None:
    _ensure_dirs()
    with _HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(alert, ensure_ascii=False) + "\n")


def _load_history(limit: int = 50) -> list[dict[str, Any]]:
    if not _HISTORY_FILE.exists():
        return []
    lines = _HISTORY_FILE.read_text(encoding="utf-8").strip().split("\n")
    records = []
    for line in reversed(lines[-limit:]):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


# ---------------------------------------------------------------------------
# Webhook 发送
# ---------------------------------------------------------------------------


async def _send_webhook(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    method: str,
    timeout: int,
    retry_count: int,
    retry_delay: int,
) -> dict[str, Any]:
    """发送 Webhook，支持指数退避重试。"""
    last_error = ""
    for attempt in range(retry_count + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(
                    method,
                    url,
                    json=payload,
                    headers=headers,
                )
                if resp.status_code < 400:
                    return {
                        "success": True,
                        "status_code": resp.status_code,
                        "attempt": attempt + 1,
                    }
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:
            last_error = str(exc)

        if attempt < retry_count:
            import asyncio

            await asyncio.sleep(retry_delay * (2**attempt))

    return {"success": False, "error": last_error, "attempt": retry_count + 1}


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@router.get("/alerts/config", summary="读取告警 Webhook 配置")
async def get_alert_config() -> dict[str, Any]:
    """返回当前告警 Webhook 配置。"""
    return _load_config()


@router.put("/alerts/config", summary="更新告警 Webhook 配置")
async def put_alert_config(body: WebhookConfigBody) -> dict[str, Any]:
    """保存告警 Webhook 配置。

    配置后，舆情监控专家在检测到紧急级舆情时，除了推送 IM 群，
    还会 POST 告警数据到此 Webhook URL。
    """
    cfg = body.model_dump()
    _save_config(cfg)
    logger.info("alert webhook config updated: url=%s enabled=%s", cfg["url"], cfg["enabled"])
    return {"status": "ok", "config": cfg}


@router.post("/alerts/test", summary="发送测试告警")
async def test_alert(body: AlertTestBody) -> dict[str, Any]:
    """发送一条测试告警到已配置的 Webhook，验证链路是否通畅。"""
    cfg = _load_config()
    if not cfg.get("url") or not cfg.get("enabled"):
        raise HTTPException(status_code=400, detail="Webhook 未配置或未启用")

    alert = AlertPayload(
        alert_id=str(uuid4()),
        level=body.level,
        keyword=body.keyword,
        platform="test",
        message=f"[测试告警] {body.keyword} · 级别={body.level}",
        details={"test": True, "source": "alert_webhook_api"},
    )

    result = await _send_webhook(
        url=cfg["url"],
        payload=alert.model_dump(),
        headers=cfg.get("headers", {"Content-Type": "application/json"}),
        method=cfg.get("method", "POST"),
        timeout=cfg.get("timeout_seconds", 10),
        retry_count=cfg.get("retry_count", 3),
        retry_delay=cfg.get("retry_delay_seconds", 5),
    )

    _append_history({**alert.model_dump(), "delivery": result})
    return result


@router.get("/alerts/history", summary="查看告警历史")
async def get_alert_history(limit: int = 50) -> dict[str, Any]:
    """返回最近的告警记录（默认 50 条，最新在前）。"""
    return {"alerts": _load_history(limit=limit)}


@router.post("/alerts/acknowledge", summary="确认告警已处理")
async def acknowledge_alert(alert_id: str) -> dict[str, Any]:
    """标记某条告警为已处理（从待处理队列移除）。

    前端 Dashboard 可用此接口标记"已读"或"已处理"。
    """
    _ensure_dirs()
    acknowledged = False
    if _HISTORY_FILE.exists():
        lines = _HISTORY_FILE.read_text(encoding="utf-8").strip().split("\n")
        updated = []
        for line in lines:
            try:
                record = json.loads(line)
                if record.get("alert_id") == alert_id:
                    record["acknowledged"] = True
                    record["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
                    acknowledged = True
                updated.append(json.dumps(record, ensure_ascii=False))
            except json.JSONDecodeError:
                updated.append(line)
        _HISTORY_FILE.write_text("\n".join(updated) + "\n", encoding="utf-8")

    if not acknowledged:
        raise HTTPException(status_code=404, detail=f"告警 {alert_id} 不存在")

    return {"status": "ok", "alert_id": alert_id, "acknowledged": True}
