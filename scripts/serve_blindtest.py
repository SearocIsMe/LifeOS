#!/usr/bin/env python3
"""One-command blind-test server (被试浏览器访问入口).

负责人执行（一条命令）：
    python3 scripts/serve_blindtest.py
    → 被试在浏览器打开 http://<本机IP>:8200/blindtest?survey=LIFE-BT-002

Serves the subject-facing blind-test app on port 8200 (决策门前仅局域网；
arch §5.10: 决策门前不暴露公网). Bearer token is NOT needed for subjects —
this is the public-by-design subject page; data still anonymized (方案 A:
email 原文不入库, only one-way hash dedup).
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lifeos.dogfood.blindtest_app import create_blindtest_app  # noqa: E402


def lan_ip() -> str:
    """Best-effort LAN IP for the printed URL (被试从本机/局域网访问)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main() -> int:
    ap = argparse.ArgumentParser(description="serve the blind-test subject page")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8200)
    ap.add_argument("--out-dir", default="reports/blindtest")
    args = ap.parse_args()

    import uvicorn

    app = create_blindtest_app(out_dir=args.out_dir)
    ip = lan_ip()
    print("=" * 64)
    print("LifeOS 盲测服务已启动（决策门前仅局域网，不暴露公网）")
    print(f"  被试访问（示例，替换成实际下发的化名编号）：")
    print(f"    http://{ip}:{args.port}/blindtest?survey=LIFE-BT-002")
    print(f"  本机访问：")
    print(f"    http://127.0.0.1:{args.port}/blindtest?survey=LIFE-BT-002")
    print(f"  作答落库：{args.out_dir}/responses.jsonl（匿名化）")
    print("=" * 64)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
