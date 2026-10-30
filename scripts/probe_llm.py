"""Probe the Zhipu (bigmodel.cn) LLM endpoint from inside the container.

Usage (inside docker):  python probe_llm.py
Reads the key from the manager DB-free path: pass via env LLM_API_KEY,
otherwise falls back to the value found in ai_model_config by the caller.
"""

import json
import os
import sys
import urllib.error
import urllib.request

KEY = os.environ.get("LLM_API_KEY", "")
BASE = os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
MODEL = os.environ.get("LLM_MODEL", "glm-5.3-flash")

if not KEY:
    print("FAIL: LLM_API_KEY env is empty")
    sys.exit(1)

url = BASE.rstrip("/") + "/chat/completions"
body = json.dumps(
    {"model": MODEL, "messages": [{"role": "user", "content": "你好，请用一句话介绍自己"}],
     "stream": False},
    ensure_ascii=False,
).encode("utf-8")

req = urllib.request.Request(
    url,
    data=body,
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY},
)

try:
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    print(f"OK HTTP {r.status}")
    print(f"MODEL {MODEL} -> {content[:100]}")
except urllib.error.HTTPError as exc:
    print(f"FAIL HTTP {exc.code}")
    print(exc.read().decode("utf-8", "replace")[:500])
except Exception as exc:  # noqa: BLE001
    print(f"FAIL {type(exc).__name__}: {exc}")
    sys.exit(2)
