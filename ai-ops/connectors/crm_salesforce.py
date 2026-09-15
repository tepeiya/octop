"""CRM Connector · Phase 3 模块 3.2

功能：
  - 对接主流 CRM（Salesforce / HubSpot / 飞书 CRM / 企微 SCRM）
  - 获取客户列表、跟进记录、商机状态
  - 同步运营 Agent 生成的客户洞察到 CRM

设计原则：
  - OAuth 凭证走 Octop 的 Connector OAuth 体系
  - 不修改 Octop 核心 connectors/，作为独立扩展
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SUPPORTED_CRMS = ["salesforce", "hubspot", "feishu_crm", "wecom_scrm"]


@dataclass
class CRMCredential:
    """CRM 凭证。"""
    crm_type: str
    api_key: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    instance_url: str | None = None  # Salesforce 实例 URL


class CRMConnector:
    """CRM 连接器。"""

    def __init__(self, credential: CRMCredential) -> None:
        self.credential = credential
        self.crm_type = credential.crm_type

    async def get_customers(
        self, page: int = 1, limit: int = 50
    ) -> dict[str, Any]:
        """获取客户列表。"""
        return await self._api_get("customers", {
            "page": page, "limit": limit,
        })

    async def get_customer_detail(self, customer_id: str) -> dict[str, Any]:
        """获取客户详情。"""
        return await self._api_get(f"customers/{customer_id}", {})

    async def get_follow_ups(
        self, customer_id: str | None = None, limit: int = 20
    ) -> dict[str, Any]:
        """获取跟进记录。"""
        params = {"limit": limit}
        if customer_id:
            params["customer_id"] = customer_id
        return await self._api_get("follow_ups", params)

    async def get_opportunities(
        self, status: str = "open"
    ) -> dict[str, Any]:
        """获取商机列表。"""
        return await self._api_get("opportunities", {"status": status})

    async def add_follow_up(
        self, customer_id: str, content: str, next_action: str = ""
    ) -> dict[str, Any]:
        """添加跟进记录（写操作）。"""
        return await self._api_post("follow_ups", {
            "customer_id": customer_id,
            "content": content,
            "next_action": next_action,
            "source": "ai_ops_agent",
        })

    async def sync_customer_insight(
        self, customer_id: str, insight: dict[str, Any]
    ) -> dict[str, Any]:
        """将 AI Agent 生成的客户洞察同步到 CRM。"""
        return await self._api_post(f"customers/{customer_id}/insights", {
            "insight": insight,
            "synced_by": "ai_ops_agent",
        })

    # ---- 内部方法 ----

    async def _api_get(
        self, endpoint: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        url = self._build_url(endpoint)
        headers = self._build_headers()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("CRM GET %s failed: %s", endpoint, exc)
            return {"error": str(exc)}

    async def _api_post(
        self, endpoint: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        url = self._build_url(endpoint)
        headers = self._build_headers()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=data, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("CRM POST %s failed: %s", endpoint, exc)
            return {"error": str(exc)}

    def _build_url(self, endpoint: str) -> str:
        base = self._get_base_url()
        return f"{base}/{endpoint}"

    def _get_base_url(self) -> str:
        if self.crm_type == "salesforce" and self.credential.instance_url:
            return f"{self.credential.instance_url}/services/data/v58.0/sobjects"
        urls = {
            "salesforce": "https://api.salesforce.com/services/data/v58.0",
            "hubspot": "https://api.hubapi.com/crm/v3",
            "feishu_crm": "https://open.feishu.cn/open-apis/crm/v1",
            "wecom_scrm": "https://qyapi.weixin.qq.com/cgi-bin/externalcontact",
        }
        return urls.get(self.crm_type, "")

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.credential.access_token:
            if self.crm_type == "salesforce":
                headers["Authorization"] = f"Bearer {self.credential.access_token}"
            elif self.crm_type == "hubspot":
                headers["Authorization"] = f"Bearer {self.credential.api_key}"
            else:
                headers["Authorization"] = f"Bearer {self.credential.access_token}"
        return headers


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


async def crm_get_customers(
    ctx: Any,
    crm_type: str,
    page: int = 1,
) -> dict[str, Any]:
    """获取 CRM 客户列表。

    Args:
        crm_type: CRM 类型（salesforce/hubspot/feishu_crm/wecom_scrm）
        page: 页码
    """
    if crm_type not in SUPPORTED_CRMS:
        return {"error": f"不支持的 CRM: {crm_type}, 支持: {SUPPORTED_CRMS}"}

    cred = CRMCredential(
        crm_type=crm_type,
        access_token=ctx.get("crm_token"),
        api_key=ctx.get("crm_api_key"),
        instance_url=ctx.get("crm_instance_url"),
    )
    connector = CRMConnector(cred)
    return await connector.get_customers(page=page)


async def crm_add_follow_up(
    ctx: Any,
    crm_type: str,
    customer_id: str,
    content: str,
    next_action: str = "",
) -> dict[str, Any]:
    """添加客户跟进记录。

    Args:
        crm_type: CRM 类型
        customer_id: 客户 ID
        content: 跟进内容
        next_action: 下一步动作
    """
    if crm_type not in SUPPORTED_CRMS:
        return {"error": f"不支持的 CRM: {crm_type}"}

    cred = CRMCredential(
        crm_type=crm_type,
        access_token=ctx.get("crm_token"),
    )
    connector = CRMConnector(cred)
    return await connector.add_follow_up(customer_id, content, next_action)


async def crm_sync_insight(
    ctx: Any,
    crm_type: str,
    customer_id: str,
    insight: dict[str, Any],
) -> dict[str, Any]:
    """同步 AI 生成的客户洞察到 CRM。

    Args:
        crm_type: CRM 类型
        customer_id: 客户 ID
        insight: 洞察数据（JSON）
    """
    if crm_type not in SUPPORTED_CRMS:
        return {"error": f"不支持的 CRM: {crm_type}"}

    cred = CRMCredential(
        crm_type=crm_type,
        access_token=ctx.get("crm_token"),
    )
    connector = CRMConnector(cred)
    return await connector.sync_customer_insight(customer_id, insight)


TOOLS = [
    crm_get_customers,
    crm_add_follow_up,
    crm_sync_insight,
]
