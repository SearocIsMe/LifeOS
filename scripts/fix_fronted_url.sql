-- fix_fronted_url.sql
-- 修正 server.fronted_url：把无效的 https://www.tokynflow.com 改为可用地址。
--
-- 背景（2026-11-01 实测）：
--   OTA 响应中的 activation.message = "https://www.tokynflow.com\n<验证码>"
--   设备把该地址显示在 LCD 上，用户需访问它完成绑定。
--   但实测 https://www.tokynflow.com/ 的 TLS 握手失败（证书未覆盖 www 子域）：
--       https://www.tokynflow.com/xiaozhi/ota/  -> HTTP 000（SSL 失败）
--       https://tokynflow.com/xiaozhi/ota/      -> HTTP 200（证书有效）
--       http://tokynflow.com:8002/xiaozhi/ota/  -> HTTP 200
--   因此用户打不开绑定页面 -> 无法绑定设备与智控台。
--
-- 用法（云服务器）：
--   docker cp scripts/fix_fronted_url.sql xiaozhi-esp32-server-db:/tmp/ff.sql
--   docker exec xiaozhi-esp32-server-db sh -c 'mysql -uroot -p123456 < /tmp/ff.sql'
--   docker restart xiaozhi-esp32-server

SELECT '=== BEFORE ===' AS info;
SELECT param_code, IFNULL(param_value,'<NULL>') AS val
FROM xiaozhi_esp32_server.sys_params
WHERE param_code IN ('server.fronted_url','server.ota','server.websocket','server.auth.enabled');

-- 用能通过的地址（优先 443 / 主域，证书有效）
UPDATE xiaozhi_esp32_server.sys_params
SET param_value = 'https://tokynflow.com'
WHERE param_code = 'server.fronted_url';

SELECT '=== AFTER ===' AS info;
SELECT param_code, IFNULL(param_value,'<NULL>') AS val
FROM xiaozhi_esp32_server.sys_params
WHERE param_code IN ('server.fronted_url','server.ota','server.websocket','server.auth.enabled');
