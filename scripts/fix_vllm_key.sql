-- fix_vllm_key.sql
-- 把当前【有效】的 LLM api_key 复制给 VLLM（视觉模型），避免占位符污染 HTTP header。
--
-- 背景：VLLM 配置中的 api_key 仍是占位符 "你的api_key"（或 "??api_key"），
--      openai SDK 把它塞进 Authorization header 时触发
--      'ascii' codec can't encode characters in position 7-8
--      → 视觉接口全部失败。
--
-- 前提：ai_model_config 中 LLM 类型下至少有一个 api_key 是真实可用的
--      （可用 scripts/check_llm_key.py 先行验证）。
--
-- 用法：
--   docker cp scripts/fix_vllm_key.sql xiaozhi-esp32-server-db:/tmp/fix.sql
--   docker exec xiaozhi-esp32-server-db sh -c 'mysql -uroot -p123456 < /tmp/fix.sql'
--   然后重启 server:  docker restart xiaozhi-esp32-server

-- 1) 预览：当前 LLM 的真实 key（取第一个非占位符）
SELECT '=== source LLM key (preview, masked) ===' AS info;
SELECT model_code, model_name,
       CONCAT(LEFT(JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.api_key')), 6), '...') AS api_key_masked
FROM xiaozhi_esp32_server.ai_model_config
WHERE model_type='LLM'
  AND JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.api_key')) NOT IN ('你的api_key','??api_key','')
LIMIT 5;

-- 2) 执行：把该 key 复制给所有 VLLM 配置（仅当 VLLM 当前是占位符）
UPDATE xiaozhi_esp32_server.ai_model_config AS v
JOIN (
  SELECT JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.api_key')) AS k
  FROM xiaozhi_esp32_server.ai_model_config
  WHERE model_type='LLM'
    AND JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.api_key')) NOT IN ('你的api_key','??api_key','')
  ORDER BY is_default DESC
  LIMIT 1
) AS src
SET v.config_json = JSON_SET(v.config_json, '$.api_key', src.k)
WHERE v.model_type='VLLM'
  AND JSON_UNQUOTE(JSON_EXTRACT(v.config_json,'$.api_key')) IN ('你的api_key','??api_key','');

-- 3) 校验结果
SELECT '=== after fix (masked) ===' AS info;
SELECT model_code, model_name,
       CONCAT(LEFT(JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.api_key')), 6), '...') AS api_key_masked,
       JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.model_name')) AS vision_model
FROM xiaozhi_esp32_server.ai_model_config
WHERE model_type='VLLM';
