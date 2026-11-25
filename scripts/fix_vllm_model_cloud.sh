#!/usr/bin/env bash
# fix_vllm_model_cloud.sh -- 在云服务器上修复 VLLM 模型名（glm-4.6 -> GLM-4.6V）
#
# 背景：智谱 API 返回 400 {'code':'1210','message':"messages.content.type 参数非法，
#       取值范围 ['text']"}，说明当前 VLLM model_name 是【纯文本模型】glm-4.6，
#       不接受 image_url 类型 content。多模态模型必须用 GLM-4.6V（带 V）。
#
# 用法（在云服务器 /opt/xiaozhi-esp32-server 任意目录执行）：
#   bash fix_vllm_model_cloud.sh
#   bash fix_vllm_model_cloud.sh --check   # 只查看不改

set -u

DB_CONTAINER="${DB_CONTAINER:-xiaozhi-esp32-server-db}"
SERVER_CONTAINER="${SERVER_CONTAINER:-xiaozhi-esp32-server}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASS="${MYSQL_PASS:-123456}"
DB_NAME="${DB_NAME:-xiaozhi_esp32_server}"

show() {
  echo "=== 当前 VLLM 配置 ==="
  docker exec "$DB_CONTAINER" sh -c \
    "mysql -u$MYSQL_USER -p$MYSQL_PASS -t -e \"
     SELECT model_code,
            JSON_UNQUOTE(JSON_EXTRACT(config_json,'\$.model_name')) AS model_name,
            JSON_UNQUOTE(JSON_EXTRACT(config_json,'\$.base_url'))   AS base_url,
            CONCAT(LEFT(JSON_UNQUOTE(JSON_EXTRACT(config_json,'\$.api_key')),6),'...') AS key_prefix
     FROM $DB_NAME.ai_model_config WHERE model_type='VLLM';
    \"" 2>/dev/null
}

show

if [ "${1:-}" = "--check" ]; then
  exit 0
fi

echo
echo "=== 修正为 GLM-4.6V（多模态） ==="
docker exec "$DB_CONTAINER" sh -c \
  "mysql -u$MYSQL_USER -p$MYSQL_PASS -e \"
   UPDATE $DB_NAME.ai_model_config
   SET config_json = JSON_SET(config_json, '\$.model_name', 'GLM-4.6V')
   WHERE model_type='VLLM' AND model_code='ChatGLMVLLM';
  \"" 2>/dev/null

echo "=== 重启服务端，使新配置生效 ==="
docker restart "$SERVER_CONTAINER" >/dev/null

echo "等待服务就绪..."
for i in $(seq 1 60); do
  if docker logs --tail 40 "$SERVER_CONTAINER" 2>&1 | grep -q "server listening on"; then
    echo "server listening on 0.0.0.0:8000"
    break
  fi
  sleep 2
done

echo
show

echo
echo "=== 完成 ==="
echo "下一步："
echo "  1) 让设备复位（重新拉取配置）"
echo "  2) 对设备说「打开摄像头看看前面是什么」"
echo "  3) 观察日志：docker logs -f $SERVER_CONTAINER | grep -Ei 'camera|vision|vllm|执行工具'"
echo
echo "期望日志（成功）："
echo "  INFO-执行工具: self_camera_take_photo"
echo "  INFO-发送客户端mcp工具调用请求: self.camera.take_photo"
echo "  （不再出现 400 / code 1210）"
echo "  INFO-收到mcp消息：{... \"success\":true ...}"
