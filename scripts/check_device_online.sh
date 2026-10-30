#!/usr/bin/env bash
# check_device_online.sh -- 诊断 generator「在线」判定的真实返回
# 依据：generator 用 POST /xiaozhi/device/tools/list/{deviceId} 且 code===0 判在线
#
# 用法（WSL 内）：
#   CHROME_TOKEN="<从浏览器 localStorage.token 里 JSON.parse(...).token 取得>" \
#     bash scripts/check_device_online.sh 1c:29:04:31:11:88
#
# 不传 token 时只验证「无鉴权」分支（应返回 401），用于确认接口存在。

set -u
DEV="${1:-1c:29:04:31:11:88}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8002}"
TOKEN="${CHROME_TOKEN:-}"

URL="http://${HOST}:${PORT}/xiaozhi/device/tools/list/${DEV}"

echo "=== target: $URL ==="

echo
echo "--- 1) 无 token（预期 401，证明接口存在且强制鉴权） ---"
curl -s -m 10 -w "\nHTTP:%{http_code}\n" \
  -X POST -H 'Content-Type: application/json' "$URL"

if [ -n "$TOKEN" ]; then
  echo
  echo "--- 2) 带浏览器 token（预期 code:0 = 设备在线） ---"
  curl -s -m 10 -w "\nHTTP:%{http_code}\n" \
    -X POST -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${TOKEN}" "$URL"
else
  echo
  echo "--- 2) 跳过（未提供 CHROME_TOKEN）---"
  echo "    取 token 方法：浏览器 F12 Console 执行"
  echo "    JSON.parse(localStorage.getItem('token')).token"
fi

echo
echo "--- 3) 服务端最近 20 分钟设备连接痕迹 ---"
docker logs --since 20m xiaozhi-esp32-server 2>&1 \
  | grep -E 'listen消息|大模型收到|超时|断开连接|连接资源' | tail -8

echo
echo "--- 4) 设备表 last_connected_at ---"
docker exec xiaozhi-esp32-server-db mysql -uroot -p123456 -N \
  -e "SELECT id,last_connected_at FROM xiaozhi_esp32_server.ai_device;" 2>/dev/null
