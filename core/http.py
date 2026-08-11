# -*- coding: utf-8 -*-
"""共享 HTTP 工具：代理处理 + 连接重试。"""
from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)


def make_session(*, direct: bool = False, proxy: str = "") -> requests.Session:
    """创建 requests Session。
    direct=True 时完全绕过系统/环境代理（本机 Clash 导致 api.p0.systems 连接不稳时用）。
    proxy 非空时强制走该代理。
    """
    session = requests.Session()
    if direct:
        session.trust_env = False
        session.proxies = {}
    elif proxy:
        session.proxies = {"http": proxy, "https": proxy}
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    })
    return session


def request_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    retries: int = 8,
    backoff: float = 2.0,
    **kwargs,
) -> requests.Response:
    """带退避的请求，自动重试连接类错误（SSL/超时/代理断连）。
    4xx/5xx 不重试（调用方自行处理业务错误）。
    """
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return session.request(method.upper(), url, **kwargs)
        except requests.exceptions.RequestException as exc:
            last_error = exc
            if attempt >= retries:
                break
            wait = backoff * (2 ** attempt)
            logger.debug("%s %s 连接失败(%s)，%.1fs 后重试", method.upper(), url, type(exc).__name__, wait)
            time.sleep(wait)
    raise last_error
