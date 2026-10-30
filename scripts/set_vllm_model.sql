-- set_vllm_model.sql
-- 将智能体绑定的 VLLM（视觉大模型）指向可用的多模态模型 GLM-4.6V。
--
-- 背景（2026-10-30 实测）：
--   1) 原先 VLLM 的 api_key 是占位符 "你的api_key" → Authorization header 含中文
--      → 'ascii' codec can't encode characters in position 7-8 → 视觉接口全部失败
--   2) 已用 scripts/fix_vllm_key.sql 把有效 key 复制给 VLLM
--   3) 但 model_name 仍是文本模型名，需改为多模态模型 GLM-4.6V
--
-- 已实测：GLM-4.6V 用该 key 调用返回 HTTP 200（scripts/probe_vllm.py）
--
-- 用法：
--   docker cp scripts/set_vllm_model.sql xiaozhi-esp32-server-db:/tmp/sv.sql
--   docker exec xiaozhi-esp32-server-db sh -c 'mysql -uroot -p123456 < /tmp/sv.sql'
--   docker restart xiaozhi-esp32-server

-- 1) 预览
SELECT '=== BEFORE ===' AS info;
SELECT model_code,
       JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.model_name')) AS model_name,
       JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.base_url'))   AS base_url,
       CONCAT(LEFT(JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.api_key')),6),'...') AS key_masked
FROM xiaozhi_esp32_server.ai_model_config
WHERE model_type='VLLM';

-- 2) 设置多模态模型名
UPDATE xiaozhi_esp32_server.ai_model_config
SET config_json = JSON_SET(config_json, '$.model_name', 'GLM-4.6V')
WHERE model_type='VLLM' AND model_code='ChatGLMVLLM';

-- 3) 校验
SELECT '=== AFTER ===' AS info;
SELECT model_code,
       JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.model_name')) AS model_name,
       JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.base_url'))   AS base_url,
       CONCAT(LEFT(JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.api_key')),6),'...') AS key_masked
FROM xiaozhi_esp32_server.ai_model_config
WHERE model_type='VLLM';
