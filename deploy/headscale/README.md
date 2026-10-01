# headscale 穿透：施测页公网发布（用户修改方案，替换 frp）

> 用户修改：① webpage 部署 K8s（ns=lifeos-dev，8000::30811）② **headscale 做穿透：lifeos.dtcinfra.net（公网头节点）→ 10.97.176.242::30811（NTU 网关子路由）**。

## 拓扑（headscale 头节点 → NTU 子节点）

```
被试（公网浏览器）
  → https://lifeos.dtcinfra.net/blindtest?survey=LIFE-BT-XXX
    → [headscale 头节点] (headscale server + 反代 Caddy 443 TLS)
      → tailscale 网络 (headscale 管理的 overlay overlay)
        → [NTU 网关节点 10.97.176.242] (tailscale 客户端，NodePort 30811 子路由)
          → K8s Service lifeos-blindtest-page (NodePort 30811 → container 8000)
            → uvicorn 施测页 → PVC /data/blindtest/responses.jsonl（数据落本机）
```

**headscale 与 tailscale 的关系**：headscale 是**自托管**的 tailscale 控制服务器（管理节点注册与密钥）——NTU 网关运行 tailscale 客户端注册到 headscale，公网头节点也注册到同一 headscale，两者建立 overlay 网络穿透（Caddy 反代到 tailscale IP）。

## 操作步骤

### 第 1 步：K8s 部署施测页（ns=lifeos-dev，8000::30811）

```bash
# 1) 镜像构建 + 推内网 registry
docker build -f deploy/blindtest/Dockerfile -t 172.128.0.11:30500/dtc/lifeos-blindtest-page:0.1.0 .
docker push 172.128.0.11:30500/dtc/lifeos-blindtest-page:0.1.0
# 2) 部署
kubectl apply -f k8s/60-blindtest-page.yaml
kubectl -n lifeos-dev get pods -l app=lifeos-blindtest-page
# 3) NodePort 验证
curl -s http://<node>:30811/blindtest | head -c 120     # 200 含 2026-ETH-00001
curl -s "http://<node>:30811/blindtest/api/survey?survey=LIFE-BT-002" | python3 -m json.tool | head -8
```

（注意：原部署形态 40-dev-stack 用 `kubectl apply -k k8s/`——kustomization.yaml 需补 `- 60-blindtest-page.yaml`。）

### 第 2 步：headscale 服务器（lifeos.dtcinfra.net 公网头节点）

1. 确认 headscale 已运行（用户已有）：
   ```bash
   headscale version
   # namespaces/users 已配（tailscale 客户端注册用）
   ```
2. 创建被试路由用的 user（如未配）：
   ```bash
   headscale users create lifeos-page
   # 生成注册密钥：
   headscale preauthkeys create --user lifeos-page --expiration 24h
   ```
3. 头节点也运行 tailscale 客户端注册到 headscale（同一 server）：
   ```bash
   tailscale up --login-server https://lifeos.dtcinfra.net --authkey <密钥>
   tailscale status   # 头节点自身也在 overlay
   ```
4. 反代：Caddyfile `lifeos.dtcinfra.net:443` → **NTU 网关的 tailscale IP**（或头节点直接路由）：
   ```
   lifeos.dtcinfra.net {
       reverse_proxy <NTU 网关节点 tailscale IP>:30811
   }
   ```
   （NTU 网关节点的 tailscale IP 用 `tailscale status` 从 headscale 管理面板查。）

### 第 3 步：NTU 网关节点（10.97.176.242）子路由

1. 运行 tailscale 客户端注册到 headscale：
   ```bash
   tailscale up --login-server https://lifeos.dtcinfra.net --authkey <密钥>
   tailscale status   # 建立与头节点的 overlay
   ```
2. 子路由：NodePort 30811 已在 K8s Service 暴露（`k8s/60-blindtest-page.yaml`）——网关节点直接访问 `<node>:30811`（overlay 或 LAN）；
3. 防火墙：NTU 内网**不需要开入站**（tailscale 客户端主动注册；overlay 双向经 WireGuard）；
4. 若网关节点就是 K8s node（dtc-w1），直接 `10.97.176.242:30811`。

### 第 4 步：验证（检查清单）

| # | 项 | 命令 | 通过判据 |
|---|---|---|---|
| 1 | K8s Pod 就绪 | `kubectl -n lifeos-dev get pods -l app=lifeos-blindtest-page` | `Running 1/1` |
| 2 | NodePort | `curl -s http://10.97.176.242:30811/blindtest` | 200 含 2026-ETH-00001 |
| 3 | 公网页面 | `curl -s https://lifeos.dtcinfra.net/blindtest` | 200 + HTML 含「2026-ETH-00001」 |
| 4 | 公网 API | `curl -s "https://lifeos.dtcinfra.net/blindtest/api/survey?survey=LIFE-BT-002"` | JSON 返回 LIFE-BT-002 / 24 trials |
| 5 | overlay 穿透 | 头节点 `tailscale ping <NTU 网关节点 tailscale IP>` | `pong` |
| 6 | 防重/限流 | 两个公网 IP 各提交一次 + 同 IP 第 11 次 | 互不影响 + 429 |
| 7 | 数据落 PVC | `kubectl -n lifeos-dev exec deploy/lifeos-blindtest-page -- cat /data/blindtest/responses.jsonl` | 公网作答实时落 PVC |
| 8 | HTTPS | 浏览器锁标 | Caddy 自动证书 |

## 与 frp 方案的对比（用户修改的原因）

| 方案 | 优点 | 缺点 |
|---|---|---|
| frp（原方案） | 简单、零 overlay | 自维护转发/token；frps 主机单点 |
| **headscale（用户修改）** | **WireGuard 加密 overlay**（零配置加密）；K8s 原生 NodePort 对接；用户已有 headscale（用户：NTU 内网已有 headscale 基础） | 需要注册两个节点（头/网关）；headscale server 可用性依赖 |

（frp 配置三件套保留在 `deploy/frp/` 存档——不删除，方案 A/B 对照；生产走 headscale。）
