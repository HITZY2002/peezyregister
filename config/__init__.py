# -*- coding: utf-8 -*-
"""加载 .env 并聚合各配置模块。"""
from config.env_loader import load_env

load_env()

# 导入即完成 env 覆盖
from config import captcha, email, peezy, sub2api  # noqa: E402,F401

__all__ = ["captcha", "email", "peezy", "sub2api"]
