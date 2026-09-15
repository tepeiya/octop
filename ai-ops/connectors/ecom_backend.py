"""电商后台 Connector · Phase 3 模块 3.1

功能：
  - 对接主流电商后台 API（淘宝/京东/拼多多/抖店/快手小店）
  - 获取商品列表、价格、库存、订单状态
  - 对于没有开放 API 的旧系统，降级到浏览器 AI+（harness-browser）

设计原则：
  - 不在 Octop 的 infra/connectors/ 中注册（那是核心代码）
  - 作为独立插件运行，Agent 通过工具调用
  - 凭证加密存储在 Octop 的 secrets 中
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# 支持的电商平台
SUPPORTED_PLATFORMS = ["taobao", "jd", "pdd", "douyin_shop", "kuaishou_shop"]


@dataclass
class EcomCredential:
    """电商后台凭证。"""
    platform: str
    app_key: str | None = None
    app_secret: str | None = None
    access_token: str | None = None
    shop_id: str | None = None
    # 旧系统降级：浏览器登录态 Cookie
    cookies: dict[str, str] | None = None


class EcomBackendConnector:
    """电商后台 Connector。

    优先走平台开放 API；如果没有 API 权限，降级到浏览器 AI+。
    """

    def __init__(self, credential: EcomCredential) -> None:
        self.credential = credential
        self.platform = credential.platform

    async def get_product_list(
        self, page: int = 1, size: int = 50
    ) -> dict[str, Any]:
        """获取店铺商品列表。"""
        if self.credential.access_token:
            return await self._get_via_api("products/list", {
                "page": page, "size": size,
            })
        # 降级：提示 Agent 使用浏览器 AI+
        return {
            "mode": "browser_required",
            "message": f"{self.platform} 未配置 API Token，请使用浏览器 AI+ 爬取后台",
            "fallback_url": self._get_backend_url(),
        }

    async def get_product_detail(self, product_id: str) -> dict[str, Any]:
        """获取单个商品详情（价格/库存/SKU）。"""
        if self.credential.access_token:
            return await self._get_via_api("products/detail", {
                "product_id": product_id,
            })
        return {
            "mode": "browser_required",
            "product_id": product_id,
            "message": "需要浏览器 AI+ 获取详情",
        }

    async def update_price(
        self, product_id: str, new_price: float
    ) -> dict[str, Any]:
        """修改商品价格（需 HITL 审批）。"""
        if self.credential.access_token:
            return await self._post_via_api("products/price", {
                "product_id": product_id,
                "price": new_price,
            }, require_approval=True)
        return {
            "mode": "browser_required",
            "action": "update_price",
            "product_id": product_id,
            "new_price": new_price,
            "message": "需要浏览器 AI+ 操作后台改价",
            "require_approval": True,
        }

    async def list_orders(
        self, status: str = "pending", limit: int = 20
    ) -> dict[str, Any]:
        """获取订单列表。"""
        if self.credential.access_token:
            return await self._get_via_api("orders/list", {
                "status": status, "limit": limit,
            })
        return {
            "mode": "browser_required",
            "message": "需要浏览器 AI+ 获取订单",
        }

    # ---- 内部方法 ----

    async def _get_via_api(
        self, endpoint: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """通过平台开放 API 调用。"""
        base_url = self._get_api_base_url()
        headers = self._build_auth_headers()
        url = f"{base_url}/{endpoint}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("ecom API %s failed: %s", endpoint, exc)
            return {"error": str(exc), "endpoint": endpoint}

    async def _post_via_api(
        self, endpoint: str, data: dict[str, Any], require_approval: bool = False
    ) -> dict[str, Any]:
        """POST 到平台 API（写操作，强制审批）。"""
        if require_approval:
            return {
                "require_approval": True,
                "message": f"写操作 {endpoint} 需要 HITL 审批",
                "data": data,
            }

        base_url = self._get_api_base_url()
        headers = self._build_auth_headers()
        url = f"{base_url}/{endpoint}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=data, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("ecom API POST %s failed: %s", endpoint, exc)
            return {"error": str(exc)}

    def _get_api_base_url(self) -> str:
        """各平台 API 基础 URL。"""
        urls = {
            "taobao": "https://eco.taobao.com/router/rest",
            "jd": "https://api.jd.com/routerjson",
            "pdd": "https://gw-api.pinduoduo.com/api/router",
            "douyin_shop": "https://openapi-fxg.jinritemai.com",
            "kuaishou_shop": "https://open.kwaixiaodian.com",
        }
        return urls.get(self.platform, "")

    def _get_backend_url(self) -> str:
        """各平台商家后台 URL（浏览器降级用）。"""
        urls = {
            "taobao": "https://item.taobao.com/seller",
            "jd": "https://shop.jd.com",
            "pdd": "https://mms.pinduoduo.com",
            "douyin_shop": "https://fxg.jinritemai.com",
            "kuaishou_shop": "https://s.kwaixiaodian.com",
        }
        return urls.get(self.platform, "")

    def _build_auth_headers(self) -> dict[str, str]:
        """构建认证请求头。"""
        headers = {"Content-Type": "application/json"}
        if self.credential.access_token:
            headers["Authorization"] = f"Bearer {self.credential.access_token}"
        return headers


# ---------------------------------------------------------------------------
# 工具函数（供 Octop Agent 调用）
# ---------------------------------------------------------------------------


async def ecom_get_products(
    ctx: Any,
    platform: str,
    page: int = 1,
) -> dict[str, Any]:
    """获取电商后台商品列表。

    Args:
        platform: 平台名称（taobao/jd/pdd/douyin_shop/kuaishou_shop）
        page: 页码
    """
    if platform not in SUPPORTED_PLATFORMS:
        return {"error": f"不支持的平台: {platform}, 支持: {SUPPORTED_PLATFORMS}"}

    cred = EcomCredential(platform=platform, access_token=ctx.get("ecom_token"))
    connector = EcomBackendConnector(cred)
    return await connector.get_product_list(page=page)


async def ecom_update_price(
    ctx: Any,
    platform: str,
    product_id: str,
    new_price: float,
) -> dict[str, Any]:
    """修改商品价格（强制 HITL 审批）。

    Args:
        platform: 平台名称
        product_id: 商品 ID
        new_price: 新价格
    """
    if platform not in SUPPORTED_PLATFORMS:
        return {"error": f"不支持的平台: {platform}"}

    cred = EcomCredential(platform=platform, access_token=ctx.get("ecom_token"))
    connector = EcomBackendConnector(cred)
    return await connector.update_price(product_id, new_price)


async def ecom_list_orders(
    ctx: Any,
    platform: str,
    status: str = "pending",
) -> dict[str, Any]:
    """获取订单列表。

    Args:
        platform: 平台名称
        status: 订单状态（pending/shipped/completed）
    """
    if platform not in SUPPORTED_PLATFORMS:
        return {"error": f"不支持的平台: {platform}"}

    cred = EcomCredential(platform=platform, access_token=ctx.get("ecom_token"))
    connector = EcomBackendConnector(cred)
    return await connector.list_orders(status=status)


# 工具注册表
TOOLS = [
    ecom_get_products,
    ecom_update_price,
    ecom_list_orders,
]
