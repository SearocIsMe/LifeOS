#!/usr/bin/env python3
"""check_llm_key.py -- read the *effective* LLM keys from the manager DB and probe each.

Why: the xiaozhi-server logs report a misleading `'ascii' codec can't encode ...`
when the upstream returns 401 (the Chinese error body blows up inside the OpenAI
SDK error path). To know the REAL cause you must probe the endpoint directly.

Run it from WSL (needs docker):
    python3 scripts/check_llm_key.py

It shells out to `docker exec xiaozhi-esp32-server-db mysql ...`, extracts every
LLM config_json with a non-placeholder api_key, and POSTs a one-shot chat request.
Exit code 0 = at least one usable key; 1 = none usable.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request

DB_CONTAINER = "xiaozhi-esp32-server-db"
MYSQL = ["docker", "exec", DB_CONTAINER, "mysql", "-uroot", "-p123456", "-N", "-e"]

PLACEHOLDERS = {"你的api_key", "??api_key", "", "your_api_key", "sk-xxx"}


def fetch_llm_configs() -> list[dict]:
    sql = (
        "SELECT CONCAT(model_code,'|',model_name,'|',config_json) "
        "FROM xiaozhi_esp32_server.ai_model_config WHERE model_type='LLM';"
    )
    out = subprocess.run(MYSQL + [sql], capture_output=True, text=True, timeout=30)
    rows = []
    for line in out.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        code, name, cfg = parts
        try:
            conf = json.loads(cfg)
        except json.JSONDecodeError:
            continue
        rows.append({"code": code, "name": name, **conf})
    return rows


def probe(conf: dict) -> tuple[bool, str]:
    key = str(conf.get("api_key") or "")
    base = str(conf.get("base_url") or "").rstrip("/")
    model = str(conf.get("model_name") or "")
    if not key or key in PLACEHOLDERS:
        return False, "skip: placeholder/empty key"
    if not base or not model:
        return False, "skip: missing base_url/model_name"

    url = base + "/chat/completions"
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": "你好"}], "stream": False},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        reply = data["choices"][0]["message"]["content"]
        return True, f"HTTP {resp.status} -> {reply[:60]}"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        return False, f"HTTP {exc.code} -> {detail}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {str(exc)[:150]}"


def main() -> int:
    try:
        configs = fetch_llm_configs()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL to query DB: {exc}")
        print("hint: is the stack up?  wsl bash -c 'docker ps | grep xiaozhi'")
        return 2

    if not configs:
        print("no LLM configs found in ai_model_config")
        return 2

    any_ok = False
    for conf in configs:
        ok, msg = probe(conf)
        any_ok = any_ok or ok
        flag = "OK  " if ok else "FAIL"
        print(f"[{flag}] {conf['code']} / {conf.get('model_name')} / {conf.get('base_url')}")
        print(f"       {msg}")

    print("\nverdict:", "PASS (at least one usable LLM key)" if any_ok else "FAIL (no usable key)")
    return 0 if any_ok else 1


if __name__ == "__main__":
    sys.exit(main())
