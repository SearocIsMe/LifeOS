"""probe_vllm.py -- verify a vision (multimodal) model end-to-end.

Sends a tiny 1x1 PNG as an image_url data URI, so it works without any real photo.
Reads key/base/model from env:
    LLM_API_KEY, LLM_BASE_URL, VLLM_MODEL

Usage (inside container):
    docker exec -e LLM_API_KEY=... -e VLLM_MODEL=GLM-4.6V \
      xiaozhi-esp32-server python /tmp/probe_vllm.py
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request

KEY = os.environ.get("LLM_API_KEY", "")
BASE = os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
MODEL = os.environ.get("VLLM_MODEL", "GLM-4.6V")

# 1x1 transparent PNG
PNG = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001" "0d0a2db40000000049454e44ae426082"
    )
).decode()

if not KEY:
    print("FAIL: LLM_API_KEY empty")
    sys.exit(1)

url = BASE.rstrip("/") + "/chat/completions"
payload = {
    "model": MODEL,
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": "这是什么颜色？只回答颜色词。"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + PNG}},
        ],
    }],
    "max_tokens": 32,
}
body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    url, data=body,
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY},
)

try:
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    msg = data["choices"][0]["message"]["content"]
    print(f"OK HTTP {r.status}  model={MODEL}")
    print(f"REPLY: {msg[:120]}")
except urllib.error.HTTPError as exc:
    print(f"FAIL HTTP {exc.code}  model={MODEL}")
    print(exc.read().decode("utf-8", "replace")[:400])
    sys.exit(2)
except Exception as exc:  # noqa: BLE001
    print(f"FAIL {type(exc).__name__}: {exc}")
    sys.exit(3)
