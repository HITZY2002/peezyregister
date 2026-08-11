# -*- coding: utf-8 -*-
"""sub2api 推送配置。"""
from config.env_loader import apply_env_overrides

# 是否在拿到 API Key 后自动推送到 sub2api
SUB2API_AUTO_PUSH = True

# sub2api 管理 API 基础地址（自行填写，例如 https://sub2api.你的域名.top，不要带 /api/v1）
SUB2API_API_BASE = ""

# 管理接口鉴权 Key（在 sub2api 后台生成 Admin API Key）
SUB2API_API_KEY = ""

# 鉴权头名称与前缀（默认 x-api-key，无需 Bearer 前缀）
SUB2API_AUTH_HEADER = "x-api-key"
SUB2API_AUTH_PREFIX = ""

# 推送账号的平台与类型
SUB2API_PLATFORM = "openai"
SUB2API_TYPE = "apikey"

# 目标分组：优先 group_id；留空则按 group_name 查找，找不到时自动创建
SUB2API_GROUP_ID = ""
SUB2API_GROUP_NAME = ""

# 账号调度参数
SUB2API_CONCURRENCY = 1
SUB2API_PRIORITY = 0
SUB2API_RATE_MULTIPLIER = 1

# 模型映射（默认 PEEZY_MODELS 原样映射 + auto->auto）
SUB2API_MODEL_MAPPING = None

SUB2API_TIMEOUT = 30

apply_env_overrides(globals(), {
    "SUB2API_AUTO_PUSH": "bool",
    "SUB2API_API_BASE": "str",
    "SUB2API_API_KEY": "str",
    "SUB2API_AUTH_HEADER": "str",
    "SUB2API_AUTH_PREFIX": "str",
    "SUB2API_PLATFORM": "str",
    "SUB2API_TYPE": "str",
    "SUB2API_GROUP_ID": "str",
    "SUB2API_GROUP_NAME": "str",
    "SUB2API_CONCURRENCY": "int",
    "SUB2API_PRIORITY": "int",
    "SUB2API_RATE_MULTIPLIER": "int",
    "SUB2API_MODEL_MAPPING": "json",
    "SUB2API_TIMEOUT": "int",
})
