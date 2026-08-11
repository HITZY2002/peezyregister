# -*- coding: utf-8 -*-
"""CaptchaRun hCaptcha 打码客户端。

接口（已实测验证）：
  POST https://api.captcha.run/v2/tasks
    Authorization: Bearer <token>
    {"captchaType":"HCaptcha","siteKey":"...","siteReferer":"...","useCache":true}
    -> 201 {"taskId":"..."}
  GET  https://api.captcha.run/v2/tasks/{taskId}
    -> {"status":"Working|Success|...", "response":{"gRecaptchaResponse":"P1_..."}}
"""
from __future__ import annotations

import logging
import time

from core.http import make_session, request_retry

logger = logging.getLogger(__name__)


class CaptchaRunError(RuntimeError):
    """CaptchaRun 请求或打码失败。"""


class CaptchaRunSolver:
    def __init__(
        self,
        token: str,
        *,
        api_base: str = "https://api.captcha.run",
        use_cache: bool = True,
        poll_interval: float = 5,
        max_wait: float = 180,
        direct: bool = False,
        proxy: str = "",
        timeout: int = 30,
    ):
        if not token:
            raise CaptchaRunError("未配置 CAPTCHA_RUN_TOKEN")
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.use_cache = use_cache
        self.poll_interval = poll_interval
        self.max_wait = max_wait
        self.timeout = timeout
        self.session = make_session(direct=direct, proxy=proxy)
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def create_task(self, site_key: str, site_referer: str) -> str:
        payload = {
            "captchaType": "HCaptcha",
            "siteKey": site_key,
            "siteReferer": site_referer,
            "useCache": self.use_cache,
        }
        resp = request_retry(
            self.session,
            "POST",
            f"{self.api_base}/v2/tasks",
            json=payload,
            timeout=self.timeout,
        )
        if resp.status_code not in (200, 201):
            raise CaptchaRunError(f"创建打码任务失败 HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        task_id = data.get("taskId") or data.get("id")
        if not task_id:
            raise CaptchaRunError(f"创建打码任务响应缺少 taskId: {str(data)[:300]}")
        return str(task_id)

    def fetch_task(self, task_id: str) -> dict:
        resp = request_retry(
            self.session,
            "GET",
            f"{self.api_base}/v2/tasks/{task_id}",
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise CaptchaRunError(f"查询打码任务失败 HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def solve_hcaptcha(self, site_key: str, site_referer: str, *, retries: int = 2) -> str:
        """创建 HCaptcha 任务并轮询，返回 gRecaptchaResponse。"""
        last_error = ""
        for attempt in range(retries + 1):
            try:
                task_id = self.create_task(site_key, site_referer)
                logger.info("[CaptchaRun] 已提交任务 %s，开始轮询", task_id)
                deadline = time.time() + self.max_wait
                while time.time() < deadline:
                    data = self.fetch_task(task_id)
                    status = str(data.get("status") or "")
                    if status == "Success":
                        response = data.get("response") or {}
                        token = response.get("gRecaptchaResponse")
                        if not token:
                            raise CaptchaRunError("任务标记成功但缺少 gRecaptchaResponse")
                        logger.info("[CaptchaRun] 打码成功（%s），token 长度 %d", task_id, len(token))
                        return str(token)
                    if status.lower() in {"error", "failed", "failure", "expired"}:
                        raise CaptchaRunError(f"打码任务失败 status={status}: {str(data)[:300]}")
                    remaining = int(deadline - time.time())
                    logger.info(
                        "[CaptchaRun] 任务 %s 状态 %s，%.0fs 后重试（剩余 %ds）",
                        task_id, status, self.poll_interval, remaining,
                    )
                    time.sleep(self.poll_interval)
                raise CaptchaRunError(f"打码超时（>{self.max_wait:.0f}s）")
            except CaptchaRunError as exc:
                last_error = str(exc)
                logger.warning("[CaptchaRun] 第 %d 次尝试失败：%s", attempt + 1, last_error)
                if attempt < retries:
                    time.sleep(3)
        raise CaptchaRunError(f"CaptchaRun 打码最终失败：{last_error}")
