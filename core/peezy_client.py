# -*- coding: utf-8 -*-
"""Peezy (api.p0.systems) 客户端：注册 / 登录 / 创建 API Key。

逆向自 https://peezy.p0.systems/connect 前端（index-B48DHMMc.js）：
  - GET  /auth/config                     -> {"email":true,"hcaptcha":{"siteKey":"..."},"hcaptchaRequired":true}
  - POST /auth/email/register             {"email","password","captchaToken"} -> {"token","user"}
  - POST /auth/email/login                {"email","password","captchaToken"} -> {"token","user"}
  - POST /api/agents/v1/api-keys          {"name":"..."}  Bearer <token>      -> {"apiKey":"p0ag_...","record":{...}}

注册无需邮箱验证即返回 token（JWT 有效期 7 天）；API Key 永久有效（expires_at=null）。
"""
from __future__ import annotations

import logging

from core.http import make_session, request_retry

logger = logging.getLogger(__name__)


class PeezyError(RuntimeError):
    """Peezy API 业务错误。"""


class PeezyClient:
    def __init__(
        self,
        *,
        api_base: str = "https://api.p0.systems",
        site_origin: str = "https://peezy.p0.systems",
        connect_path: str = "/connect",
        timeout: int = 30,
        direct: bool = False,
        proxy: str = "",
    ):
        self.api_base = api_base.rstrip("/")
        self.site_origin = site_origin.rstrip("/")
        self.site_referer = self.site_origin + connect_path
        self.timeout = timeout
        self.session = make_session(direct=direct, proxy=proxy)
        self.session.headers.update({
            "Origin": self.site_origin,
            "Referer": self.site_referer,
            "Accept": "application/json",
        })
        self._auth_config: dict | None = None

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    # ---------- 公共接口 ----------

    def get_auth_config(self, *, refresh: bool = False) -> dict:
        if self._auth_config is not None and not refresh:
            return self._auth_config
        resp = request_retry(self.session, "GET", f"{self.api_base}/auth/config", timeout=self.timeout)
        if resp.status_code != 200:
            raise PeezyError(f"获取 /auth/config 失败 HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        self._auth_config = data if isinstance(data, dict) else {}
        return self._auth_config

    def get_hcaptcha_sitekey(self, fallback: str = "") -> str:
        try:
            cfg = self.get_auth_config()
            hc = cfg.get("hcaptcha") or {}
            site_key = str(hc.get("siteKey") or cfg.get("hcaptchaSiteKey") or "")
            if site_key:
                return site_key
        except Exception:
            pass
        return fallback

    def register(self, email: str, password: str, captcha_token: str) -> tuple[str, dict]:
        return self._email_auth("/auth/email/register", email, password, captcha_token)

    def login(self, email: str, password: str, captcha_token: str) -> tuple[str, dict]:
        return self._email_auth("/auth/email/login", email, password, captcha_token)

    def create_api_key(self, token: str, name: str = "Peezy CLI manual key") -> str:
        resp = request_retry(
            self.session,
            "POST",
            f"{self.api_base}/api/agents/v1/api-keys",
            json={"name": name},
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise PeezyError(f"创建 API Key 失败 HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        api_key = data.get("apiKey")
        if not api_key:
            raise PeezyError(f"创建 API Key 响应缺少 apiKey: {str(data)[:300]}")
        return str(api_key)

    # ---------- 内部 ----------

    def _email_auth(self, path: str, email: str, password: str, captcha_token: str) -> tuple[str, dict]:
        payload = {
            "email": email,
            "password": password,
            "captchaToken": captcha_token,
        }
        resp = request_retry(
            self.session,
            "POST",
            self.api_base + path,
            json=payload,
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            detail = ""
            try:
                detail = str(resp.json().get("error") or resp.text)[:300]
            except Exception:
                detail = resp.text[:300]
            raise PeezyError(f"{path} 失败 HTTP {resp.status_code}: {detail}")
        data = resp.json()
        token = data.get("token")
        user = data.get("user") if isinstance(data.get("user"), dict) else {}
        if not token:
            raise PeezyError(f"{path} 响应缺少 token: {str(data)[:300]}")
        logger.info(
            "[Peezy] %s 成功：%s（user_id=%s）",
            "注册" if "register" in path else "登录",
            email,
            user.get("id"),
        )
        return str(token), user
