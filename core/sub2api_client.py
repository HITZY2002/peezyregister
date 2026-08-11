# -*- coding: utf-8 -*-
"""sub2api 管理 API 客户端：把 Peezy API Key 推成 openai/apikey 账号。

已实测验证（Wei-Shaw/sub2api 魔改版）：
  GET    /api/v1/admin/groups                     x-api-key: <key>
  POST   /api/v1/admin/accounts
    {"name","platform":"openai","type":"apikey",
     "credentials":{"api_key":"p0ag_...","base_url":"https://api.p0.systems/api/agents/v1",
                    "model_mapping":{...}},
     "group_ids":[..],"concurrency","priority","rate_multiplier","auto_pause_on_expired",
     "confirm_mixed_channel_risk"}
    -> 200 {"code":0,"data":{"id":..}}
  DELETE /api/v1/admin/accounts/{id}
"""
from __future__ import annotations

import logging

from core.http import make_session, request_retry

logger = logging.getLogger(__name__)


class Sub2APIError(RuntimeError):
    """sub2api 管理接口错误。"""


class Sub2APIClient:
    def __init__(
        self,
        api_base: str,
        api_key: str,
        *,
        auth_header: str = "x-api-key",
        auth_prefix: str = "",
        timeout: int = 30,
        direct: bool = False,
        proxy: str = "",
    ):
        if not api_base:
            raise Sub2APIError("未配置 SUB2API_API_BASE")
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.session = make_session(direct=direct, proxy=proxy)
        header = str(auth_header or "x-api-key").strip() or "x-api-key"
        prefix = str(auth_prefix or "").strip()
        if api_key:
            self.session.headers[header] = f"{prefix} {api_key}".strip() if prefix else api_key
        self.session.headers.update({"Accept": "application/json"})

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def _check(self, resp) -> dict:
        if resp.status_code >= 400:
            raise Sub2APIError(f"sub2api 请求失败 HTTP {resp.status_code}: {resp.text[:400]}")
        try:
            data = resp.json()
        except Exception:
            raise Sub2APIError(f"sub2api 响应不是 JSON: {resp.text[:300]}")
        if isinstance(data, dict) and data.get("code") not in (None, 0):
            raise Sub2APIError(f"sub2api 业务错误 code={data.get('code')}: {str(data.get('message'))[:300]}")
        return data.get("data") if isinstance(data, dict) and "data" in data else data

    def list_groups(self, platform: str = "") -> list[dict]:
        params = {"page": 1, "page_size": 200}
        if platform:
            params["platform"] = platform
        resp = request_retry(
            self.session, "GET", f"{self.api_base}/api/v1/admin/groups",
            params=params, timeout=self.timeout,
        )
        data = self._check(resp)
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("items") or data.get("list") or []
        else:
            items = []
        return [item for item in items if isinstance(item, dict)]

    def list_accounts(self, *, platform: str = "openai", page: int = 1, page_size: int = 200) -> list[dict]:
        params = {"page": page, "page_size": page_size, "platform": platform}
        resp = request_retry(
            self.session, "GET", f"{self.api_base}/api/v1/admin/accounts",
            params=params, timeout=self.timeout,
        )
        data = self._check(resp)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [item for item in (data.get("items") or []) if isinstance(item, dict)]
        return []

    def find_account_by_name(self, name: str) -> dict | None:
        for item in self.list_accounts(platform="openai"):
            if str(item.get("name") or "") == str(name):
                return item
        return None

    def ensure_group(self, name: str, platform: str = "openai") -> int:
        """按名称查找分组，找不到则创建，返回 group id。"""
        if not name:
            raise Sub2APIError("SUB2API_GROUP_NAME 为空，无法创建/查找分组")
        for group in self.list_groups(platform=platform):
            if str(group.get("name") or "") == str(name):
                return int(group["id"])
        resp = request_retry(
            self.session, "POST", f"{self.api_base}/api/v1/admin/groups",
            json={"name": name, "platform": platform},
            timeout=self.timeout,
        )
        data = self._check(resp)
        group_id = data.get("id") if isinstance(data, dict) else None
        if not group_id:
            raise Sub2APIError(f"创建分组失败，响应缺少 id: {str(data)[:300]}")
        logger.info("[Sub2API] 已创建分组 %s id=%s", name, group_id)
        return int(group_id)

    def push_api_key_account(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        model_mapping: dict | None = None,
        group_ids: list[int] | None = None,
        concurrency: int = 1,
        priority: int = 0,
        rate_multiplier: int = 1,
        notes: str = "",
        update_existing: bool = True,
    ) -> dict:
        credentials: dict = {"api_key": api_key, "base_url": base_url}
        if model_mapping:
            credentials["model_mapping"] = model_mapping
        payload = {
            "name": name,
            "platform": "openai",
            "type": "apikey",
            "credentials": credentials,
            "concurrency": concurrency,
            "priority": priority,
            "rate_multiplier": rate_multiplier,
            "auto_pause_on_expired": True,
            "confirm_mixed_channel_risk": True,
        }
        if notes:
            payload["notes"] = notes
        if group_ids:
            payload["group_ids"] = group_ids

        # 去重：同名已存在则用 PUT 更新，避免重复推送
        existing = self.find_account_by_name(name)
        if existing and existing.get("id") is not None:
            if not update_existing:
                return {"ok": False, "skipped": True, "account_id": existing.get("id")}
            account_id = int(existing["id"])
            resp = request_retry(
                self.session, "PUT", f"{self.api_base}/api/v1/admin/accounts/{account_id}",
                json=payload, timeout=self.timeout,
            )
            self._check(resp)
            logger.info("[Sub2API] 已更新账号 id=%s name=%s", account_id, name)
            return {"ok": True, "updated": True, "account_id": account_id}

        resp = request_retry(
            self.session, "POST", f"{self.api_base}/api/v1/admin/accounts",
            json=payload, timeout=self.timeout,
        )
        data = self._check(resp)
        account_id = data.get("id") if isinstance(data, dict) else None
        if not account_id:
            raise Sub2APIError(f"创建账号失败，响应缺少 id: {str(data)[:300]}")
        logger.info("[Sub2API] 已推送账号 id=%s name=%s", account_id, name)
        return {"ok": True, "updated": False, "account_id": int(account_id)}

    def delete_account(self, account_id: int) -> None:
        resp = request_retry(
            self.session, "DELETE", f"{self.api_base}/api/v1/admin/accounts/{account_id}",
            timeout=self.timeout,
        )
        self._check(resp)
        logger.info("[Sub2API] 已删除账号 id=%s", account_id)
