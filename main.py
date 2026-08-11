# -*- coding: utf-8 -*-
"""Peezy2API 命令行入口：注册/登录 Peezy 账号 -> 创建 API Key -> 推送 sub2api。"""
from __future__ import annotations

import argparse
import logging
import sys

from core.runner import RunOptions, run


def _ensure_utf8_stdio() -> None:
    """Windows 下让管道/重定向输出保持 UTF-8，避免 GBK 控制台乱码。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def configure_logging(verbose: bool = False) -> None:
    _ensure_utf8_stdio()
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    root.handlers = [handler]
    if not verbose:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Peezy2API：自动注册/登录 peezy.p0.systems，获取 API Key 并推送到 sub2api",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--count", type=int, default=1, help="注册/处理账号数量")
    parser.add_argument(
        "--mode",
        choices=["register", "login"],
        default="register",
        help="register=自动注册新号；login=使用已有账号（文件 email====password）",
    )
    parser.add_argument("--workers", type=int, default=1, help="并发线程数（打码/邮箱注意配额）")
    parser.add_argument("--account-file", default="accounts_to_login.txt", help="login 模式账号文件")
    parser.add_argument("--output", default="accounts.json", help="结果输出文件")
    parser.add_argument("--group-id", default="", help="sub2api 目标分组 id（覆盖 .env）")
    parser.add_argument("--group-name", default="", help="sub2api 目标分组名（找不到自动创建）")
    parser.add_argument("--no-push", action="store_true", help="不推送到 sub2api，只保存本地结果")
    parser.add_argument("--dry-run", action="store_true", help="只走注册/登录并取 key，不推送不落盘")
    parser.add_argument("--direct", action="store_true", help="直连（绕过系统/环境代理，本机 Clash 不稳时用）")
    parser.add_argument("--proxy", default="", help="强制使用指定 HTTP 代理，如 http://127.0.0.1:7897")
    parser.add_argument("-v", "--verbose", action="store_true", help="调试日志")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)
    opts = RunOptions(
        count=args.count,
        mode=args.mode,
        workers=args.workers,
        direct=args.direct,
        proxy=args.proxy,
        no_push=args.no_push,
        output=args.output,
        account_file=args.account_file,
        group_id=args.group_id,
        group_name=args.group_name,
        dry_run=args.dry_run,
    )
    results = run(opts)
    ok = [r for r in results if r.get("status") == "success"]
    failed = [r for r in results if r.get("status") == "failed"]
    skipped = [r for r in results if r.get("status") == "skipped"]
    print()
    print(f"完成：成功 {len(ok)}，失败 {len(failed)}，跳过 {len(skipped)}")
    for r in ok:
        print(
            f"  OK  {r.get('email')}  api_key={r.get('api_key')}  "
            f"pushed={r.get('pushed')}  sub2api_id={r.get('sub2api_account_id')}"
        )
    for r in failed:
        print(f"  FAIL {r.get('email', '-')}  {r.get('error')}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
