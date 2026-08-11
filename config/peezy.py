# -*- coding: utf-8 -*-
"""Peezy (p0.systems) 对接配置。"""
from config.env_loader import apply_env_overrides

# Peezy 云 API 基础地址（前端常量 El() = https://api.p0.systems）
PEEZY_API_BASE = "https://api.p0.systems"

# 网页 Origin / Referer，hCaptcha siteReferer 也用它
PEEZY_SITE_ORIGIN = "https://peezy.p0.systems"
PEEZY_CONNECT_PATH = "/connect"

# OpenAI 兼容网关上游地址（写入 sub2api 账号的 base_url）
PEEZY_UPSTREAM_BASE_URL = "https://api.p0.systems/api/agents/v1"

# 默认模型列表（写入 sub2api 账号的 model_mapping；也可用 PEEZY_MODELS json 覆盖）
PEEZY_MODELS = ["kimi-k3", "grok-4.5"]

# 注册生成的随机密码长度（站点要求 >= 8）
PEEZY_PASSWORD_LENGTH = 14

# 注册/登录时使用的 hCaptcha sitekey（优先从 /auth/config 动态获取，这里是兜底）
PEEZY_HCAPTCHA_SITEKEY = "23743efe-d960-43b0-ab62-6db42b767966"

# 请求超时（秒）
PEEZY_TIMEOUT = 30

# 单账号失败后的重试次数（每次换一个新邮箱）
PEEZY_REGISTER_RETRIES = 3

apply_env_overrides(globals(), {
    "PEEZY_API_BASE": "str",
    "PEEZY_SITE_ORIGIN": "str",
    "PEEZY_CONNECT_PATH": "str",
    "PEEZY_UPSTREAM_BASE_URL": "str",
    "PEEZY_MODELS": "json",
    "PEEZY_PASSWORD_LENGTH": "int",
    "PEEZY_HCAPTCHA_SITEKEY": "str",
    "PEEZY_TIMEOUT": "int",
    "PEEZY_REGISTER_RETRIES": "int",
})
