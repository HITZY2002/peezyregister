# -*- coding: utf-8 -*-
"""注册/登录编排：临时邮箱 -> hCaptcha 打码 -> 注册/登录 -> 创建 API Key -> 推送到 sub2api。"""
from __future__ import annotations

import json
import logging
import os
import random
import string
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import captcha as _captcha_cfg
from config import email as _email_cfg
from config import peezy as _peezy_cfg
from config import sub2api as _sub2api_cfg
from core.captcha_solver import CaptchaRunSolver
from core.mail_client import TempMailClient
from core.peezy_client import PeezyClient
from core.sub2api_client import Sub2APIClient

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _random_password(length: int) -> str:
    length = max(8, int(length or _peezy_cfg.PEEZY_PASSWORD_LENGTH))
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_"
    # 保证至少含字母和数字
    pwd = [
        random.choice(string.ascii_letters),
        random.choice(string.digits),
    ]
    pwd += [random.choice(alphabet) for _ in range(length - 2)]
    random.shuffle(pwd)
    return "".join(pwd)


def _default_model_mapping() -> dict:
    mapping = {"auto": "auto"}
    models = _peezy_cfg.PEEZY_MODELS or []
    if isinstance(models, list):
        for model in models:
            mapping[str(model)] = str(model)
    elif isinstance(models, dict):
        mapping.update({str(k): str(v) for k, v in models.items()})
    return mapping


def _build_model_mapping(opts: RunOptions | None = None) -> dict:
    if opts is not None and isinstance(opts.model_mapping, dict) and opts.model_mapping:
        return {str(k): str(v) for k, v in opts.model_mapping.items()}
    configured = _sub2api_cfg.SUB2API_MODEL_MAPPING
    if isinstance(configured, dict) and configured:
        return {str(k): str(v) for k, v in configured.items()}
    return _default_model_mapping()


@dataclass
class RunOptions:
    count: int = 1
    mode: str = "register"  # register | login
    workers: int = 1
    direct: bool = False
    proxy: str = ""
    no_push: bool = False
    output: str = "accounts.json"
    account_file: str = "accounts_to_login.txt"
    group_id: str = ""
    group_name: str = ""
    api_key_name_prefix: str = "peezy"
    note_prefix: str = "peezy2api"
    dry_run: bool = False
    # sub2api 账号并发（覆盖 SUB2API_CONCURRENCY）
    concurrency: int = 1
    # 模型映射覆盖（dict；None 时用配置默认）
    model_mapping: dict | None = None
    # WebUI 停止信号（内部使用）
    stop_event: threading.Event | None = None


@dataclass
class FlowComponents:
    peezy: PeezyClient
    captcha: CaptchaRunSolver
    mail: TempMailClient
    sub2: Sub2APIClient | None = None


class ResultStore:
    """线程安全地把结果追加到 JSON 文件。"""

    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._rows: list[dict] = []
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    self._rows = [r for r in loaded if isinstance(r, dict)]
            except Exception:
                pass

    def append(self, record: dict) -> None:
        with self._lock:
            self._rows.append(record)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(self._rows, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(tmp, self.path)

    def already_has(self, email: str) -> bool:
        with self._lock:
            return any(str(r.get("email") or "").lower() == str(email).lower() for r in self._rows)


def _build_components(opts: RunOptions) -> FlowComponents:
    peezy = PeezyClient(
        api_base=_peezy_cfg.PEEZY_API_BASE,
        site_origin=_peezy_cfg.PEEZY_SITE_ORIGIN,
        connect_path=_peezy_cfg.PEEZY_CONNECT_PATH,
        timeout=_peezy_cfg.PEEZY_TIMEOUT,
        direct=opts.direct,
        proxy=opts.proxy,
    )
    captcha = CaptchaRunSolver(
        _captcha_cfg.CAPTCHA_RUN_TOKEN,
        api_base=_captcha_cfg.CAPTCHA_RUN_API_BASE,
        use_cache=_captcha_cfg.CAPTCHA_USE_CACHE,
        poll_interval=_captcha_cfg.CAPTCHA_POLL_INTERVAL,
        max_wait=_captcha_cfg.CAPTCHA_MAX_WAIT,
        direct=opts.direct,
        proxy=opts.proxy,
    )
    mail = TempMailClient(
        _email_cfg.MAIL_API_BASE,
        path_address=_email_cfg.MAIL_PATH_ADDRESS,
        path_messages=_email_cfg.MAIL_PATH_MESSAGES,
        domains=_email_cfg.MAIL_DOMAINS,
        name_length=_email_cfg.MAIL_NAME_LENGTH,
        direct=opts.direct,
        proxy=opts.proxy,
        timeout=_email_cfg.MAIL_TIMEOUT,
    )
    sub2 = None
    if not opts.no_push:
        sub2 = Sub2APIClient(
            _sub2api_cfg.SUB2API_API_BASE,
            _sub2api_cfg.SUB2API_API_KEY,
            auth_header=_sub2api_cfg.SUB2API_AUTH_HEADER,
            auth_prefix=_sub2api_cfg.SUB2API_AUTH_PREFIX,
            timeout=_sub2api_cfg.SUB2API_TIMEOUT,
            direct=opts.direct,
            proxy=opts.proxy,
        )
    return FlowComponents(peezy=peezy, captcha=captcha, mail=mail, sub2=sub2)


def _resolve_group_id(sub2: Sub2APIClient, opts: RunOptions) -> int | None:
    group_id = str(opts.group_id or _sub2api_cfg.SUB2API_GROUP_ID or "").strip()
    if group_id:
        return int(group_id)
    group_name = str(opts.group_name or _sub2api_cfg.SUB2API_GROUP_NAME or "").strip()
    if group_name:
        return sub2.ensure_group(group_name, platform=_sub2api_cfg.SUB2API_PLATFORM)
    return None


def _push_to_sub2api(
    components: FlowComponents,
    opts: RunOptions,
    *,
    email: str,
    api_key: str,
    group_id: int | None,
) -> dict:
    sub2 = components.sub2
    if sub2 is None:
        return {"pushed": False, "reason": "push disabled"}
    base_url = _peezy_cfg.PEEZY_UPSTREAM_BASE_URL
    model_mapping = _build_model_mapping(opts)
    concurrency = int(
        opts.concurrency if opts.concurrency and opts.concurrency > 0 else _sub2api_cfg.SUB2API_CONCURRENCY
    )
    notes = f"{opts.note_prefix}:{email}"
    result = sub2.push_api_key_account(
        name=email,
        api_key=api_key,
        base_url=base_url,
        model_mapping=model_mapping,
        group_ids=[group_id] if group_id else None,
        concurrency=concurrency,
        priority=_sub2api_cfg.SUB2API_PRIORITY,
        rate_multiplier=_sub2api_cfg.SUB2API_RATE_MULTIPLIER,
        notes=notes,
    )
    return {
        "pushed": bool(result.get("ok")),
        "updated": bool(result.get("updated")),
        "sub2api_account_id": result.get("account_id"),
        "group_id": group_id,
        "base_url": base_url,
    }


def _solve_captcha(components: FlowComponents) -> str:
    site_key = components.peezy.get_hcaptcha_sitekey(_peezy_cfg.PEEZY_HCAPTCHA_SITEKEY)
    return components.captcha.solve_hcaptcha(site_key, components.peezy.site_referer)


def register_one(components: FlowComponents, store: ResultStore, opts: RunOptions) -> dict:
    """注册一个新 Peezy 账号并推送 sub2api。失败时换新邮箱重试。"""
    retries = max(1, int(_peezy_cfg.PEEZY_REGISTER_RETRIES or 1))
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            mail_account = components.mail.create_address()
            email = mail_account.address
            if store.already_has(email):
                logger.info("[Runner] 邮箱 %s 已处理过，跳过", email)
                continue
            password = _random_password(_peezy_cfg.PEEZY_PASSWORD_LENGTH)
            logger.info("[Runner] 第 %d/%d 次尝试，邮箱 %s", attempt, retries, email)
            captcha_token = _solve_captcha(components)
            token, user = components.peezy.register(email, password, captcha_token)
            api_key = components.peezy.create_api_key(token)
            record = {
                "status": "success",
                "mode": "register",
                "email": email,
                "password": password,
                "user_id": (user or {}).get("id"),
                "auth_token": token,
                "api_key": api_key,
                "api_base_url": _peezy_cfg.PEEZY_UPSTREAM_BASE_URL,
                "created_at": _now_iso(),
            }
            if not opts.dry_run and not opts.no_push:
                try:
                    group_id = _resolve_group_id(components.sub2, opts)
                    push = _push_to_sub2api(components, opts, email=email, api_key=api_key, group_id=group_id)
                    record.update(push)
                except Exception as exc:
                    record["pushed"] = False
                    record["push_error"] = f"{type(exc).__name__}: {exc}"
                    logger.warning("[Runner] sub2api 推送失败（本地账号已保留）：%s", exc)
            else:
                record["pushed"] = False
                record["push_error"] = "dry-run/no-push"
            store.append(record)
            logger.info("[Runner] 完成：%s -> %s", email, api_key)
            return record
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("[Runner] 第 %d 次尝试失败：%s", attempt, last_error)
            time.sleep(2)
    return {
        "status": "failed",
        "mode": "register",
        "error": last_error,
        "created_at": _now_iso(),
    }


def login_one(components: FlowComponents, store: ResultStore, opts: RunOptions, email: str, password: str) -> dict:
    """用已有账号登录并创建 API Key。"""
    try:
        if store.already_has(email):
            logger.info("[Runner] 邮箱 %s 已处理过，跳过", email)
            return {"status": "skipped", "mode": "login", "email": email, "created_at": _now_iso()}
        logger.info("[Runner] 登录 %s", email)
        captcha_token = _solve_captcha(components)
        token, user = components.peezy.login(email, password, captcha_token)
        api_key = components.peezy.create_api_key(token)
        record = {
            "status": "success",
            "mode": "login",
            "email": email,
            "password": password,
            "user_id": (user or {}).get("id"),
            "auth_token": token,
            "api_key": api_key,
            "api_base_url": _peezy_cfg.PEEZY_UPSTREAM_BASE_URL,
            "created_at": _now_iso(),
        }
        if not opts.dry_run and not opts.no_push:
            try:
                group_id = _resolve_group_id(components.sub2, opts)
                push = _push_to_sub2api(components, opts, email=email, api_key=api_key, group_id=group_id)
                record.update(push)
            except Exception as exc:
                record["pushed"] = False
                record["push_error"] = f"{type(exc).__name__}: {exc}"
                logger.warning("[Runner] sub2api 推送失败（本地账号已保留）：%s", exc)
        else:
            record["pushed"] = False
            record["push_error"] = "dry-run/no-push"
        store.append(record)
        logger.info("[Runner] 完成：%s -> %s", email, api_key)
        return record
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        logger.warning("[Runner] 登录失败 %s：%s", email, error)
        return {"status": "failed", "mode": "login", "email": email, "error": error, "created_at": _now_iso()}


def load_login_accounts(path: str) -> list[tuple[str, str]]:
    """读取登录账号文件，每行 email====password（支持 ---- 分隔）。"""
    p = Path(path)
    accounts: list[tuple[str, str]] = []
    if not p.exists():
        return accounts
    for raw in p.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        sep = "====" if "====" in line else ("----" if "----" in line else None)
        if not sep:
            continue
        email, _, password = line.partition(sep)
        email = email.strip()
        password = password.strip()
        if email and password and "@" in email:
            accounts.append((email, password))
    return accounts


def run(opts: RunOptions, *, on_result: Callable[[dict], None] | None = None) -> list[dict]:
    components = _build_components(opts)
    store = ResultStore(opts.output)
    results: list[dict] = []
    stop_event = opts.stop_event

    def record_result(record: dict) -> None:
        results.append(record)
        if on_result is not None:
            try:
                on_result(record)
            except Exception:
                pass

    def should_stop() -> bool:
        return bool(stop_event is not None and stop_event.is_set())

    try:
        if opts.mode == "login":
            accounts = load_login_accounts(opts.account_file)
            if not accounts:
                logger.error("未从 %s 读取到账号（格式 email====password）", opts.account_file)
                return results
            if opts.count and opts.count > 0:
                accounts = accounts[:opts.count]
            for email, password in accounts:
                if should_stop():
                    logger.info("[Runner] 收到停止信号，终止")
                    break
                record_result(login_one(components, store, opts, email, password))
            return results

        # register 模式
        from concurrent.futures import ThreadPoolExecutor, as_completed

        count = max(1, opts.count)
        workers = max(1, opts.workers)
        if workers <= 1:
            for _ in range(count):
                if should_stop():
                    logger.info("[Runner] 收到停止信号，终止")
                    break
                record_result(register_one(components, store, opts))
            return results

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(register_one, components, store, opts) for _ in range(count)]
            for future in as_completed(futures):
                record_result(future.result())
                if should_stop():
                    logger.info("[Runner] 收到停止信号，终止剩余任务")
                    for pending in futures:
                        pending.cancel()
                    break
        return results
    finally:
        components.peezy.close()
        components.captcha.close()
        components.mail.close()
        if components.sub2 is not None:
            components.sub2.close()
