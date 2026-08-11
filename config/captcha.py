# -*- coding: utf-8 -*-
"""CaptchaRun 打码平台配置。"""
from config.env_loader import apply_env_overrides

# CaptchaRun API 基础地址
CAPTCHA_RUN_API_BASE = "https://api.captcha.run"

# CaptchaRun 令牌（登录后台「用户信息」页获取；请自行填写）
# 没有账号？点此注册（邀请）：https://captcha-run.com/sso?inviter=ce5f1e67-e364-40b9-9593-6be2f36d2108
CAPTCHA_RUN_TOKEN = ""

# 创建 HCaptcha 任务参数
CAPTCHA_USE_CACHE = True

# 轮询间隔与总超时（秒）
CAPTCHA_POLL_INTERVAL = 5
CAPTCHA_MAX_WAIT = 180

apply_env_overrides(globals(), {
    "CAPTCHA_RUN_API_BASE": "str",
    "CAPTCHA_RUN_TOKEN": "str",
    "CAPTCHA_USE_CACHE": "bool",
    "CAPTCHA_POLL_INTERVAL": "int",
    "CAPTCHA_MAX_WAIT": "int",
})
