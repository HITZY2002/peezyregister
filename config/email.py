# -*- coding: utf-8 -*-
"""临时邮箱 Worker API 配置（cloudflare_temp_email 兼容）。"""
from config.env_loader import apply_env_overrides

# 临时邮箱 Worker API 根地址（请填写你自己的服务地址，例如 https://apimail.你的域名.top）
MAIL_API_BASE = ""

# 创建邮箱路径与取信路径
MAIL_PATH_ADDRESS = "/api/new_address"
MAIL_PATH_MESSAGES = "/api/mails"

# 默认收信域名，多个用逗号分隔，轮换使用（留空则由 Worker 决定）
MAIL_DOMAINS = ""

# 随机邮箱 local-part 长度
MAIL_NAME_LENGTH = 10

# 请求超时（秒）
MAIL_TIMEOUT = 20

apply_env_overrides(globals(), {
    "MAIL_API_BASE": "str",
    "MAIL_PATH_ADDRESS": "str",
    "MAIL_PATH_MESSAGES": "str",
    "MAIL_DOMAINS": "str",
    "MAIL_NAME_LENGTH": "int",
    "MAIL_TIMEOUT": "int",
})
