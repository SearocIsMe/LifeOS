-- fix_asr_language.sql
-- 把 FunASR 的 language 从 "auto" 锁定为 "zh"，消除自动语言误判。
--
-- 证据（2026-10-30 服务端日志，同一设备同一麦克风）：
--   20:47:00  识别语言: zh  识别文本: 先打开摄像头。      ← 正确
--   20:48:28  识别语言: zh  识别文本: 请打开摄像头。      ← 正确
--   21:13:29  识别语言: en  识别文本: No there's don't.   ← 误判
--   21:14:23  识别语言: ko  识别文本: 채무.               ← 误判为韩语
-- 说明：硬件与声学链路正常，故障来自 SenseVoice 的自动语种识别（LID）。
--
-- 用法：
--   docker cp scripts/fix_asr_language.sql xiaozhi-esp32-server-db:/tmp/fa.sql
--   docker exec xiaozhi-esp32-server-db sh -c 'mysql -uroot -p123456 < /tmp/fa.sql'
--   docker restart xiaozhi-esp32-server

SELECT '=== BEFORE ===' AS info;
SELECT model_code,
       JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.type'))     AS asr_type,
       JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.language')) AS language,
       JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.model_dir'))AS model_dir
FROM xiaozhi_esp32_server.ai_model_config
WHERE model_type='ASR';

-- 锁定中文
UPDATE xiaozhi_esp32_server.ai_model_config
SET config_json = JSON_SET(config_json, '$.language', 'zh')
WHERE model_type='ASR'
  AND JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.language')) = 'auto';

SELECT '=== AFTER ===' AS info;
SELECT model_code,
       JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.type'))     AS asr_type,
       JSON_UNQUOTE(JSON_EXTRACT(config_json,'$.language')) AS language
FROM xiaozhi_esp32_server.ai_model_config
WHERE model_type='ASR';
