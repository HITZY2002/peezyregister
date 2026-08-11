# -*- coding: utf-8 -*-
"""从项目根目录 .env 加载密钥/敏感配置。

设计目标：
  - 重要 API Key 不写进 config/*.py 默认值，统一放在 .env
  - config 模块启动时读取环境变量，支持 python-dotenv；未安装时用内置轻量 parser
"""
from __future__ import annotations

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
_LOADED = False


def project_root() -> Path:
    return _PROJECT_ROOT


def env_path() -> Path:
    return _ENV_PATH


def read_env_file(path: Path | None = None) -> dict[str, str]:
    p = Path(path) if path else _ENV_PATH
    out: dict[str, str] = {}
    if not p.exists():
        return out
    for raw in p.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def load_env(*, override: bool = False) -> Path:
    global _LOADED
    try:
        from dotenv import load_dotenv
    except ImportError:
        if _ENV_PATH.exists():
            for key, value in read_env_file().items():
                if override or key not in os.environ:
                    os.environ[key] = value
        _LOADED = True
        return _ENV_PATH

    load_dotenv(_ENV_PATH, override=override, verbose=False)
    _LOADED = True
    return _ENV_PATH


def env_str(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip()


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or str(value).strip() == "":
        return default
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off", "", "none", "null"}:
        return False
    return default


def env_json(name: str, default: object = None) -> object:
    """读取 JSON 型 env（如模型映射）。"""
    import json

    value = os.environ.get(name)
    if value is None or str(value).strip() == "":
        return default
    try:
        return json.loads(str(value).strip())
    except Exception:
        return default


def apply_env_overrides(namespace: dict, mapping: dict[str, str]) -> None:
    """把 env 覆盖写回 config 模块的全局变量。
    mapping: {模块内变量名: 类型}，类型支持 str/int/bool/json。
    """
    for key, kind in mapping.items():
        if key not in os.environ:
            continue
        try:
            if kind == "int":
                namespace[key] = env_int(key, int(namespace.get(key, 0) or 0))
            elif kind == "bool":
                namespace[key] = env_bool(key, bool(namespace.get(key, False)))
            elif kind == "json":
                namespace[key] = env_json(key, namespace.get(key))
            else:
                namespace[key] = env_str(key, str(namespace.get(key, "")))
        except Exception:
            continue


def set_env_value(key: str, value: object, path: Path | None = None) -> str:
    """写入/更新 .env 中的单个键值，并同步到 os.environ。返回写入的字符串值。
    含空格/引号/注释符的值会自动加双引号并转义；JSON 值会被压缩后原样写入。
    """
    p = Path(path) if path else _ENV_PATH
    raw = str(value)
    need_quote = raw == "" or any(ch.isspace() for ch in raw) or "#" in raw
    if need_quote:
        escaped = raw.replace("\\", "\\\\").replace('"', '\\"')
        line = f'{key}="{escaped}"'
    else:
        line = f"{key}={raw}"

    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    found = False
    out: list[str] = []
    for ln in lines:
        if ln.strip().startswith(key + "="):
            out.append(line)
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(line)
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.environ[key] = raw
    return raw
