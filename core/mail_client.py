# -*- coding: utf-8 -*-
"""cloudflare_temp_email 兼容的临时邮箱客户端。

已实测验证：
  POST /api/new_address {"domain":"mail.example.com"} -> {address,jwt,password,address_id}
  GET  /api/mails?limit=10&offset=0  Authorization: Bearer <jwt> -> {results:[...],count}
"""
from __future__ import annotations

import logging
import re
import secrets
import string
import threading

from core.http import make_session, request_retry

logger = logging.getLogger(__name__)


class TempMailError(RuntimeError):
    """临时邮箱请求失败。"""


class TempMailAccount:
    def __init__(self, address: str, jwt: str, password: str = "", address_id=None):
        self.address = address
        self.jwt = jwt
        self.password = password
        self.address_id = address_id


class TempMailClient:
    def __init__(
        self,
        api_base: str = "",
        *,
        path_address: str = "/api/new_address",
        path_messages: str = "/api/mails",
        domains: str = "",
        name_length: int = 10,
        direct: bool = False,
        proxy: str = "",
        timeout: int = 20,
    ):
        self.api_base = api_base.rstrip("/")
        self.path_address = path_address
        self.path_messages = path_messages
        self.name_length = max(4, int(name_length))
        self.timeout = timeout
        self.domains = [
            d.strip().lstrip("@").lower()
            for d in re.split(r"[,;\s]+", domains or "")
            if d.strip() and "." in d
        ] or []
        self._domain_counter = 0
        self._domain_lock = threading.Lock()
        self.session = make_session(direct=direct, proxy=proxy)

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def _next_domain(self) -> str:
        if not self.domains:
            return ""
        with self._domain_lock:
            domain = self.domains[self._domain_counter % len(self.domains)]
            self._domain_counter += 1
        return domain

    def create_address(self, domain: str = "") -> TempMailAccount:
        selected = (domain or "").strip().lstrip("@") or self._next_domain()
        local = "".join(
            secrets.choice(string.ascii_lowercase + string.digits)
            for _ in range(self.name_length)
        )
        payload = {"name": local}
        if selected:
            payload["domain"] = selected
        resp = request_retry(
            self.session,
            "POST",
            self.api_base + self.path_address,
            json=payload,
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise TempMailError(f"创建临时邮箱失败 HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if not isinstance(data, dict):
            raise TempMailError(f"创建临时邮箱响应格式错误: {str(data)[:200]}")
        nested = data.get("data") if isinstance(data.get("data"), dict) else {}
        address = (
            data.get("address") or nested.get("address")
            or nested.get("email") or data.get("email") or ""
        )
        jwt = data.get("jwt") or nested.get("jwt") or nested.get("token") or data.get("token") or ""
        if not address or "@" not in address:
            raise TempMailError(f"创建临时邮箱响应缺少 address: {str(data)[:200]}")
        account = TempMailAccount(
            address=str(address).strip(),
            jwt=str(jwt).strip(),
            password=str(data.get("password") or nested.get("password") or "").strip(),
            address_id=data.get("address_id") or nested.get("address_id"),
        )
        logger.info("[TempMail] 已创建邮箱 %s", account.address)
        return account

    def list_mails(self, jwt: str, *, limit: int = 10, offset: int = 0) -> list[dict]:
        resp = request_retry(
            self.session,
            "GET",
            self.api_base + self.path_messages,
            params={"limit": limit, "offset": offset},
            headers={"Authorization": f"Bearer {jwt}"},
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise TempMailError(f"拉取邮件失败 HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("results", "messages", "mails", "data", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []
