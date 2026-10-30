#!/usr/bin/env python3
"""probe_lan.py -- xiaozhi service LAN reachability probe (cross-platform).

Why a file instead of an inline heredoc: `wsl bash -c "python3 - <<'PY' ..."` breaks
under double-quote nesting, and PowerShell does not support heredocs at all.

Usage
-----
    python3 scripts/probe_lan.py                      # default 192.168.1.3
    python3 scripts/probe_lan.py 10.87.159.102         # explicit host LAN IP
    python3 scripts/probe_lan.py 192.168.1.3 --json    # machine-readable

Exit code: 0 if every endpoint answered with an HTTP status, 1 otherwise.

NOTE (WSL mirrored mode): run this INSIDE WSL (or on another host in the same LAN).
Probing your own LAN IP from Windows/WSL may return false negatives under
`networkingMode=mirrored`; a second LAN device is the cleanest check.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

ENDPOINTS = [
    ("dashboard", "/", "智控台"),
    ("ota", "/xiaozhi/ota/", "OTA 接口"),
    ("websocket", ":8000/xiaozhi/v1/", "WebSocket 入口"),
    ("vision", ":8003/mcp/vision/explain", "视觉分析接口"),
]


def build_urls(host: str) -> list[tuple[str, str, str]]:
    """Return [(name, url, description)].

    Ports follow the deployment: 8002 = manager web/api, 8000 = ws, 8003 = http/vision.
    """
    return [
        ("dashboard", f"http://{host}:8002/", "智控台根路径（不是 /xiaozhi/）"),
        ("ota", f"http://{host}:8002/xiaozhi/ota/", "设备 OTA 下发地址"),
        ("websocket", f"http://{host}:8000/xiaozhi/v1/", "WebSocket 入口（GET 200 = 端口可达）"),
        ("vision", f"http://{host}:8003/mcp/vision/explain", "视觉分析接口"),
    ]


def probe(url: str, timeout: float) -> dict:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"url": url, "status": resp.status, "ok": True}
    except urllib.error.HTTPError as exc:
        # Any HTTP status still proves the endpoint is reachable (401 is expected
        # for API paths when auth is enabled - it means the chain is alive).
        return {"url": url, "status": exc.code, "ok": True,
                "note": "HTTPError but reachable (401/403 = auth, expected)" if exc.code in (401, 403) else ""}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "status": None, "ok": False, "error": type(exc).__name__}


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe xiaozhi service endpoints on a LAN address")
    ap.add_argument("host", nargs="?", default="192.168.1.3", help="host LAN IPv4 of the xiaozhi server")
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args()

    results = [{"name": n, "desc": d, **probe(u, args.timeout)}
               for n, u, d in build_urls(args.host)]

    if args.json:
        print(json.dumps({"host": args.host, "results": results}, ensure_ascii=False, indent=2))
    else:
        print(f"host: {args.host}")
        for r in results:
            status = r["status"] if r["status"] is not None else "FAIL"
            flag = "OK  " if r["ok"] else "FAIL"
            print(f"  [{flag}] {str(status):>4}  {r['url']}")
            if r.get("note"):
                print(f"          note: {r['note']}")
            if r.get("error"):
                print(f"          error: {r['error']}")

    all_ok = all(r["ok"] for r in results)
    print(f"\nverdict: {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
