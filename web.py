# -*- coding: utf-8 -*-
"""Peezy2API WebUI 启动入口。
用法：
    python web.py                 # 默认 http://127.0.0.1:8000，仅本机
    python web.py --port 8001
    python web.py --host 0.0.0.0  # 允许局域网访问（含密钥的敏感工具，自行评估）
"""
import argparse
import faulthandler
import logging
import sys
import webbrowser
from pathlib import Path
from threading import Timer

from webui.app import create_app


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> None:
    _ensure_utf8_stdio()
    # 诊断：若服务卡死，每隔一段时间把全部线程栈写入 logs/faulthandler.log
    try:
        logs_dir = Path(__file__).resolve().parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        _fh = open(logs_dir / "faulthandler.log", "a", encoding="utf-8")
        faulthandler.enable(file=_fh)
        faulthandler.dump_traceback_later(45, repeat=True, file=_fh)
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Peezy2API WebUI 控制台")
    parser.add_argument("--host", default="127.0.0.1", help="绑定地址，默认仅本机 127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="端口，默认 8000")
    parser.add_argument("--no-browser", action="store_true", help="启动时不自动打开浏览器")
    parser.add_argument("--verbose", action="store_true", help="详细日志")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    app = create_app()
    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host}:{args.port}"
    logger.info("WebUI 已启动：%s", url)
    if args.host in ("0.0.0.0", "::"):
        logger.warning("已绑定所有网卡，局域网内其他设备可访问。这是含密钥的敏感工具，请确认网络可信。")

    if not args.no_browser:
        Timer(1.0, lambda: webbrowser.open(url)).start()

    # debug=False：避免 reloader 双进程导致后台线程重复
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
