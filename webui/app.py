# -*- coding: utf-8 -*-
"""Peezy2API WebUI：分组选择 / 并发设置 / 模型映射 / 后台运行 / 日志与结果。"""
from __future__ import annotations

import json
import logging
import os
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from config import captcha as _captcha_cfg
from config import email as _email_cfg
from config import peezy as _peezy_cfg
from config import sub2api as _sub2api_cfg
from config.env_loader import project_root, set_env_value
from core.runner import RunOptions, _build_model_mapping, _default_model_mapping, run
from core.sub2api_client import Sub2APIClient

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RunManager:
    """在后台线程运行注册任务，收集日志与进度。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._logs: deque[str] = deque(maxlen=3000)
        # 日志队列专用锁：绝不与 self._lock 混用，避免与 logging 处理器形成死锁
        self._logs_lock = threading.Lock()
        self._log_handler: logging.Handler | None = None
        self._state: dict = {
            "running": False,
            "mode": "",
            "started_at": None,
            "finished_at": None,
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "results": [],
        }

    # ---------- 日志 ----------

    def _attach_log_handler(self) -> None:
        logs = self._logs
        logs_lock = self._logs_lock

        class _QueueHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                try:
                    # 过滤 werkzeug 访问日志，避免刷屏
                    if (record.name or "").startswith("werkzeug"):
                        return
                    line = self.format(record)
                    with logs_lock:
                        logs.append(line)
                except Exception:
                    pass

        handler = _QueueHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        handler.setLevel(logging.INFO)
        root = logging.getLogger()
        root.addHandler(handler)
        self._log_handler = handler

    def _detach_log_handler(self) -> None:
        if self._log_handler is not None:
            try:
                logging.getLogger().removeHandler(self._log_handler)
            except Exception:
                pass
            self._log_handler = None

    def log(self, message: str, level: int = logging.INFO) -> None:
        logger.log(level, message)

    # ---------- 运行 ----------

    @property
    def running(self) -> bool:
        with self._lock:
            return bool(self._state.get("running"))

    def start(self, opts: RunOptions, total: int) -> tuple[bool, str]:
        if self.running:
            return False, "已有任务在运行"
        stop_event = threading.Event()
        with self._lock:
            self._stop_event = stop_event
            self._state.update({
                "running": True,
                "mode": opts.mode,
                "started_at": _now_iso(),
                "finished_at": None,
                "total": total,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "results": [],
            })
        opts.stop_event = stop_event

        def worker() -> None:
            self._attach_log_handler()
            try:
                self.log(f"任务开始：mode={opts.mode} count={total} workers={opts.workers}")
                run(opts, on_result=self._on_result)
            except Exception as exc:
                self.log(f"任务异常终止：{type(exc).__name__}: {exc}", logging.ERROR)
            finally:
                self._detach_log_handler()
                with self._lock:
                    self._state["running"] = False
                    self._state["finished_at"] = _now_iso()
                self.log("任务结束")

        self._thread = threading.Thread(target=worker, name="peezy2api-run", daemon=True)
        self._thread.start()
        return True, "已启动"

    def stop(self) -> None:
        with self._lock:
            event = self._stop_event
        if event is not None:
            event.set()
            self.log("已请求停止（当前账号完成后终止）")

    def _on_result(self, record: dict) -> None:
        with self._lock:
            status = record.get("status")
            if status == "success":
                self._state["success"] += 1
            elif status == "failed":
                self._state["failed"] += 1
            elif status == "skipped":
                self._state["skipped"] += 1
            self._state["results"].append(record)
            if len(self._state["results"]) > 200:
                self._state["results"] = self._state["results"][-200:]

    def status(self) -> dict:
        with self._lock:
            snapshot = json.loads(json.dumps(self._state))
        with self._logs_lock:
            tail = list(self._logs)[-300:]
        snapshot["logs"] = tail
        return snapshot


manager = RunManager()


def _sub2_client(direct: bool = False, proxy: str = "") -> Sub2APIClient | None:
    try:
        return Sub2APIClient(
            _sub2api_cfg.SUB2API_API_BASE,
            _sub2api_cfg.SUB2API_API_KEY,
            auth_header=_sub2api_cfg.SUB2API_AUTH_HEADER,
            auth_prefix=_sub2api_cfg.SUB2API_AUTH_PREFIX,
            timeout=_sub2api_cfg.SUB2API_TIMEOUT,
            direct=direct,
            proxy=proxy,
        )
    except Exception as exc:
        logger.warning("sub2api 客户端初始化失败：%s", exc)
        return None


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.config["JSON_AS_ASCII"] = False

    @app.after_request
    def _no_cache(response):
        """禁止缓存页面与 API，避免浏览器拿到旧版前端。"""
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    @app.route("/")
    def index():
        return render_template("index.html")

    # ---------- 分组 ----------

    @app.route("/api/groups")
    def api_groups():
        client = _sub2_client()
        if client is None:
            return jsonify({"ok": False, "error": "sub2api 未配置（SUB2API_API_BASE / SUB2API_API_KEY）"})
        try:
            groups = client.list_groups(platform=_sub2api_cfg.SUB2API_PLATFORM)
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        finally:
            client.close()
        return jsonify({
            "ok": True,
            "groups": groups,
            "current_group_id": str(_sub2api_cfg.SUB2API_GROUP_ID or ""),
            "current_group_name": str(_sub2api_cfg.SUB2API_GROUP_NAME or ""),
        })

    # ---------- 配置 ----------

    @app.route("/api/config")
    def api_config():
        mapping = _sub2api_cfg.SUB2API_MODEL_MAPPING
        if not isinstance(mapping, dict) or not mapping:
            mapping = _default_model_mapping()
        return jsonify({
            "ok": True,
            "captcha_token": str(_captcha_cfg.CAPTCHA_RUN_TOKEN or ""),
            "sub2api_api_base": str(_sub2api_cfg.SUB2API_API_BASE or ""),
            "sub2api_api_key": str(_sub2api_cfg.SUB2API_API_KEY or ""),
            "mail_api_base": str(_email_cfg.MAIL_API_BASE or ""),
            "mail_domains": str(_email_cfg.MAIL_DOMAINS or ""),
            "group_id": str(_sub2api_cfg.SUB2API_GROUP_ID or ""),
            "group_name": str(_sub2api_cfg.SUB2API_GROUP_NAME or ""),
            "workers": int(os.environ.get("REGISTER_WORKERS") or 1),
            "concurrency": int(_sub2api_cfg.SUB2API_CONCURRENCY or 1),
            "model_mapping": mapping,
            "auto_push": bool(_sub2api_cfg.SUB2API_AUTO_PUSH),
            "direct": str(os.environ.get("DIRECT") or "").lower() in ("1", "true", "yes"),
            "proxy": str(os.environ.get("PROXY") or ""),
            "count": int(os.environ.get("REGISTER_COUNT") or 1),
            "mode": str(os.environ.get("REGISTER_MODE") or "register"),
            "account_file": str(os.environ.get("ACCOUNT_FILE") or "accounts_to_login.txt"),
            "output": str(os.environ.get("OUTPUT_FILE") or "accounts.json"),
        })

    @app.route("/api/config", methods=["POST"])
    def api_config_save():
        body = request.get_json(silent=True) or {}

        def save_str(key: str, field: str) -> str:
            value = body.get(field)
            if value is None:
                return os.environ.get(key, "")
            return set_env_value(key, str(value).strip())

        group_id = save_str("SUB2API_GROUP_ID", "group_id")
        group_name = save_str("SUB2API_GROUP_NAME", "group_name")
        captcha_token = save_str("CAPTCHA_RUN_TOKEN", "captcha_token")
        sub2api_api_base = save_str("SUB2API_API_BASE", "sub2api_api_base")
        sub2api_api_key = save_str("SUB2API_API_KEY", "sub2api_api_key")
        mail_api_base = save_str("MAIL_API_BASE", "mail_api_base")
        mail_domains = save_str("MAIL_DOMAINS", "mail_domains")

        workers = body.get("workers")
        if workers is not None:
            set_env_value("REGISTER_WORKERS", max(1, int(workers)))
            os.environ["REGISTER_WORKERS"] = str(max(1, int(workers)))

        concurrency = body.get("concurrency")
        if concurrency is not None:
            set_env_value("SUB2API_CONCURRENCY", max(1, int(concurrency)))
            os.environ["SUB2API_CONCURRENCY"] = str(max(1, int(concurrency)))

        mapping = body.get("model_mapping")
        if mapping is not None:
            if isinstance(mapping, dict) and mapping:
                compact = json.dumps(mapping, ensure_ascii=False, separators=(",", ":"))
                set_env_value("SUB2API_MODEL_MAPPING", compact)
            else:
                set_env_value("SUB2API_MODEL_MAPPING", "")

        if body.get("auto_push") is not None:
            set_env_value("SUB2API_AUTO_PUSH", "true" if body["auto_push"] else "false")
        if body.get("direct") is not None:
            set_env_value("DIRECT", "true" if body["direct"] else "false")
        save_str("PROXY", "proxy")
        save_str("REGISTER_COUNT", "count")
        save_str("REGISTER_MODE", "mode")
        save_str("ACCOUNT_FILE", "account_file")
        save_str("OUTPUT_FILE", "output")

        # 同步到内存中的配置模块
        _captcha_cfg.CAPTCHA_RUN_TOKEN = captcha_token
        _sub2api_cfg.SUB2API_API_BASE = sub2api_api_base
        _sub2api_cfg.SUB2API_API_KEY = sub2api_api_key
        _email_cfg.MAIL_API_BASE = mail_api_base
        _email_cfg.MAIL_DOMAINS = mail_domains
        _sub2api_cfg.SUB2API_GROUP_ID = group_id
        _sub2api_cfg.SUB2API_GROUP_NAME = group_name
        _sub2api_cfg.SUB2API_CONCURRENCY = max(1, int(os.environ.get("SUB2API_CONCURRENCY") or 1))
        mapping = body.get("model_mapping")
        _sub2api_cfg.SUB2API_MODEL_MAPPING = mapping if isinstance(mapping, dict) and mapping else None
        _sub2api_cfg.SUB2API_AUTO_PUSH = str(os.environ.get("SUB2API_AUTO_PUSH") or "true").lower() not in ("0", "false", "no")

        manager.log("配置已保存到 .env")
        return jsonify({"ok": True, "message": "配置已保存"})

    # ---------- 运行 ----------

    @app.route("/api/run", methods=["POST"])
    def api_run():
        if manager.running:
            return jsonify({"ok": False, "error": "已有任务在运行"})
        body = request.get_json(silent=True) or {}
        mode = str(body.get("mode") or "register")
        count = max(1, int(body.get("count") or 1))
        workers = max(1, int(body.get("workers") or os.environ.get("REGISTER_WORKERS") or 1))
        group_id = str(body.get("group_id") or _sub2api_cfg.SUB2API_GROUP_ID or "")
        group_name = str(body.get("group_name") or _sub2api_cfg.SUB2API_GROUP_NAME or "")
        concurrency = max(1, int(body.get("concurrency") or _sub2api_cfg.SUB2API_CONCURRENCY or 1))
        mapping = body.get("model_mapping")
        if not isinstance(mapping, dict) or not mapping:
            mapping = _sub2api_cfg.SUB2API_MODEL_MAPPING
        if not isinstance(mapping, dict) or not mapping:
            mapping = None
        direct = bool(body.get("direct", os.environ.get("DIRECT", "") in ("1", "true")))
        proxy = str(body.get("proxy") or os.environ.get("PROXY") or "")
        no_push = not bool(body.get("auto_push", _sub2api_cfg.SUB2API_AUTO_PUSH))
        account_file = str(body.get("account_file") or os.environ.get("ACCOUNT_FILE") or "accounts_to_login.txt")
        output = str(body.get("output") or os.environ.get("OUTPUT_FILE") or "accounts.json")

        opts = RunOptions(
            count=count,
            mode=mode,
            workers=workers,
            direct=direct,
            proxy=proxy,
            no_push=no_push,
            output=output,
            account_file=account_file,
            group_id=group_id,
            group_name=group_name,
            concurrency=concurrency,
            model_mapping=mapping,
        )
        ok, message = manager.start(opts, total=count)
        return jsonify({"ok": ok, "message": message})

    @app.route("/api/stop", methods=["POST"])
    def api_stop():
        manager.stop()
        return jsonify({"ok": True})

    @app.route("/api/status")
    def api_status():
        return jsonify({"ok": True, **manager.status()})

    @app.route("/api/accounts")
    def api_accounts():
        path = Path(str(os.environ.get("OUTPUT_FILE") or "accounts.json"))
        if not path.is_absolute():
            path = project_root() / path
        rows: list[dict] = []
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    rows = [r for r in loaded if isinstance(r, dict)]
            except Exception as exc:
                return jsonify({"ok": False, "error": f"读取结果失败：{exc}"})
        return jsonify({"ok": True, "accounts": rows[-200:]})

    return app
