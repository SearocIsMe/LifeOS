# frp 内网穿透部署：施测页公网发布（方案 A）

> 目标：NTU 内网的施测页（uvicorn 8200）经 frp 反向穿透暴露到公网 `https://lifeos.dtcinfra.net/blindtest`，获取 60 份被试 survey 数据。
> 纪律核对：盲测页是**研究活动的例外场景**（arch §5.10 "决策门前不暴露公网"的豁免范围 = 仅 `/blindtest` 路由，主 API/studio 仍内网）；登记 ADR-0008（豁免范围 + HTTPS + 限流在档）。

## 拓扑

```
被试（公网浏览器，任意网络）
  → https://lifeos.dtcinfra.net/blindtest?survey=LIFE-BT-XXX
    → [公网 frps 主机] (nginx/caddy 443 TLS → frps vhostHTTPPort 8080)
      → frp 隧道（frpc 从 NTU 主动外连建立，经网关 10.97.176.242 出口 30810~30820）
        → [NTU 内网本机] uvicorn 8200 施测页
          → reports/blindtest/responses.jsonl（数据落本机，不跨境）
```

**核心优势**：frpc 是**主动外连**（出站）——NTU 内网**不需要开任何入站端口**；出口走网关允许的 30810~30820 段。

## 操作步骤

### 第 1 步：公网 frps 主机（lifeos.dtcinfra.net 解析到的机器）

1. DNS：确认 `lifeos.dtcinfra.net` A 记录指向该主机（如未配，在 DNS 服务商加 A 记录）；
2. 下载 frp：`wget https://github.com/fatedier/frp/releases/download/v0.61.0/frp_0.61.0_linux_amd64.tar.gz && tar xzf frp_0.61.0_linux_amd64.tar.gz`；
3. 把本仓库 `deploy/frp/frps.dtcinfra.toml` 复制到主机，**替换 token**（`CHANGE_ME` → 强随机值）；
4. 放行防火墙：`30810`（frp bind）、`30811`（可选 TCP）、`80/443`（被试访问）；
5. 启动：`./frps -c frps.dtcinfra.toml`（建议 systemd 常驻）；
6. TLS：Caddy 反代 `443 → 8080`（自动证书）——Caddyfile：
   ```
   lifeos.dtcinfra.net {
       reverse_proxy 127.0.0.1:8080
   }
   ```

### 第 2 步：NTU 内网本机（施测页所在）

1. 先起施测页：`.venv/bin/python scripts/serve_blindtest.py`（8200）；
2. 把 `deploy/frp/frpc.ntu.toml` 的 `auth.token` 替换为与 frps 一致的值；
3. 启动穿透：`frpc -c deploy/frp/frpc.ntu.toml`（frpc 二进制或 `uv pip install frp`）；
4. frpc 日志确认：`login to server success` + `proxy [lifeos-blindtest-http] success`。

### 第 3 步：验证（检查清单）

| # | 项 | 命令 | 通过判据 |
|---|---|---|---|
| 1 | 隧道建立 | frpc 日志 | `login to server success` |
| 2 | 公网页面 | `curl -s https://lifeos.dtcinfra.net/blindtest` | 200 + HTML 含「2026-ETH-00001」 |
| 3 | 公网 API | `curl -s "https://lifeos.dtcinfra.net/blindtest/api/survey?survey=LIFE-BT-002"` | JSON 返回 LIFE-BT-002 / 24 trials |
| 4 | 防重生效 | 两个不同公网 IP 各提交一次 | 互不影响（XFF 链记录各自真实 IP） |
| 5 | 限流生效 | 同 IP 第 11 次 /api | 429 |
| 6 | 数据落本机 | 本机 `reports/blindtest/responses.jsonl` | 公网作答实时落本机（不跨境） |
| 7 | HTTPS 证书 | 浏览器锁标 | Caddy 自动证书有效 |

## 运维注意

- **本机可用性**：您的电脑关机 = 问卷下线——收数周期内保持开机（或用 NTU 内的常驻服务器跑 frpc + uvicorn）；
- **NTU 网络关口**：若 30810 出口不通，依次试 30811~30820（frpc.serverPort 与 frps.bindPort 同步改）；
- **数据安全**：作答数据落本机（不落公网 frps）——frps 只转发流量；定期备份 `reports/blindtest/`；
- **token 管理**：`CHANGE_ME` 正式值不入仓库（部署时直接在主机/本机替换）。
