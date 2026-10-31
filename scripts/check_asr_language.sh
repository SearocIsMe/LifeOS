#!/usr/bin/env bash
# check_asr_language.sh -- 核对 ASR 语言配置是否已锁定为中文
#
# 背景：FunASR(SenseVoice) 的 language="auto" 会启用自动语种识别(LID)，
#       在音频质量一般时可能把中文判成 en/ko，导致识别文本变成乱码。
#       把 language 锁定为 "zh" 可关闭该不确定性。
#
# 用法（WSL 内）：
#   bash scripts/check_asr_language.sh

set -u

echo "=== 1) ai_model_config 中所有 ASR 的 language ==="
docker exec xiaozhi-esp32-server-db sh -c \
  "mysql -uroot -p123456 -t -e \"
   SELECT id, model_code, model_type,
          JSON_UNQUOTE(JSON_EXTRACT(config_json,'\$.type'))     AS asr_type,
          JSON_UNQUOTE(JSON_EXTRACT(config_json,'\$.language')) AS language
   FROM xiaozhi_esp32_server.ai_model_config
   WHERE model_type='ASR' AND id IN ('ASR_FunASR','ASR_FunASRServer','ASR_SherpaASR');
  \"" 2>/dev/null

echo
echo "=== 2) 设备实际绑定的 ASR 记录 ==="
docker exec xiaozhi-esp32-server-db sh -c \
  "mysql -uroot -p123456 -t -e \"
   SELECT d.id AS device_id, a.agent_name, a.asr_model_id,
          JSON_UNQUOTE(JSON_EXTRACT(m.config_json,'\$.language')) AS language
   FROM xiaozhi_esp32_server.ai_device d
   LEFT JOIN xiaozhi_esp32_server.ai_agent a ON d.agent_id=a.id
   LEFT JOIN xiaozhi_esp32_server.ai_model_config m ON m.id=a.asr_model_id;
  \"" 2>/dev/null

echo
echo "=== 3) 运行时是否仍有非中文语种误判（近 30 分钟） ==="
docker logs --since 30m xiaozhi-esp32-server 2>&1 \
  | grep -E '识别语言|识别文本' | tail -10

BAD=$(docker logs --since 30m xiaozhi-esp32-server 2>&1 \
      | grep -cE '识别语言: (en|ko|ja|yue)')
echo
if [ "$BAD" -gt 0 ]; then
  echo "[WARN] 近 30 分钟出现 $BAD 次非中文语种判定"
  echo "       若 language 已为 zh，请确认设备已复位重连（设备会缓存私有配置）"
else
  echo "[OK] 近 30 分钟无非中文语种判定"
fi
