# LifeOS 阶段 0 → K8s 集群环境迁移交接文档

版本 1.0 ｜ 2026-09-16 ｜ 交接方：原开发环境（Windows 笔记本 + WSL2 Docker，AI 协作完成阶段 0）
接收方：**新环境工程执行者（含接手智能大模型）**，在 K8s 集群环境直接操作 `dtc-w1`、`aisi-w7` 等节点继续阶段 0 收尾与阶段 1 工作
决策依据：[ADR-0004_部署环境迁移至K8s集群.md](adr/ADR-0004_部署环境迁移至K8s集群.md)

> **给接手智能大模型的第一句话**：这个项目对「诚实」的纪律要求高于对进度的要求。所有实测字段必须实测后填写，禁止编造；所有引用必须核对出处；材料的来源与签署不可篡改；报告不许静默 PASS。违反这些的项目自身红线比任何技术错误都严重（见 §8）。

---

## 1. 项目一页纸背景

- **LifeOS 是什么**：驱动 AI Pet 心智软资产（身份/记忆/人格/关系）的运行时；核心承诺「换模型、换库、换载体后，还是同一个它」。**不输出运动控制、不含产品 UI**。
- **三条可证伪假设**：H1 身份连续可工程化 > H2 记忆可信 > H3 用户可感知（H1 是全部价值的地基，先证它）。
- **路线图位置**：四阶段门禁制。**阶段 0（契约与可重放骨架）工程验证已完成**；正在收尾；下一步阶段 1（跨模型连续性最小验证，6～8 周，本地推理部署是最大工作量项——这正是本次迁移到 H200 集群的动机）。
- **架构一句话**：确定性主干 + 概率性叶子。L0→L1→L2 三级事件；`deterministic_commit` 是全仓库唯一的 L1→L2 变换（在线/回放同一路径）；LLM 输出永不直写权威表；Policy 审批在事务开启前；PostgreSQL 16+pgvector 是唯一权威源。

## 2. 必读文档地图（按此顺序）

| 顺序 | 文档 | 作用 |
|---|---|---|
| 1 | [README.md](../../README.md) | 项目全貌（英文） |
| 2 | doc/LifeOS_研发路线图_v0.9.1.md | 怎么动手：阶段划分、Gate、数字来源表（§1.2）、第一周清单 |
| 3 | doc/LifeOS_产品规格说明书_v0.9.1.md | 验收口径：§1.3 判定框架、§3.2 指标、§10 Gate、§12 排查表、§9 合规 |
| 4 | doc/LifeOS_架构设计_v0.9.1.md | 怎么实现：§3 事件模型、§4 15 实体、§7 事务、§8 部署（§8 已被 ADR-0004 修订） |
| 5 | phases/phase-0/01_详细设计.md | 阶段 0 契约细节 + 设计决策（D2-1/D3-1/D3-2/D4-2） |
| 6 | phases/phase-0/02_工程设计执行方案.md | AC-01～AC-10 验收 case 定义 + 差异登记表 |
| 7 | phases/phase-0/03_核心事实集与行为场景编写规范.md | 材料规格与双路径流程（P1/P2） |
| 8 | phases/phase-0/adr/（ADR-0001～0004） | 四个已定决策，**ADR-0004 是本次迁移的依据** |

## 3. 当前状态快照（2026-09-15 完成时点）

### 3.1 已完成（含证据物）

| 项 | 状态 | 证据物 |
|---|---|---|
| 15 实体 Schema + alembic 0001 迁移 | ✅ | `src/lifeos/entities.py`、`alembic/versions/0001_initial_schema.py` |
| L0/L1/L2 事件管线 + `deterministic_commit`（纯函数） | ✅ | `src/lifeos/events/`；回放一致率 100%（含篡改负例自检） |
| Policy 最小骨架（RED-01 医疗 / RED-02 sensitive 话题） | ✅ | `src/lifeos/policy/engine.py`；拒绝零状态副作用已测 |
| 写路径三层守卫 + 多实例隔离 | ✅ | `tests/test_llm_boundary.py`、`tests/test_isolation.py` |
| 27 项自动化测试 | ✅ | tier A 25/25 + tier B 2/2（pytest marker `db`） |
| **gold set 注册冻结** | ✅ | core_facts v0.1.0（50 条，hash `506c9f4c…`）、behavior_scenario v0.1.0（30 个，hash `e4bef442…`）；manifest 在 `phases/phase-0/reports/goldset_*.manifest.json`；来源/签署：ADR-0003 P2 路径（AI 起草+独立审核+具名负责人 Jiang Haipeng/Searoc 审定签署 2026-09-15） |
| Gate 0 报告 | ✅（verdict=PASS @ 2026-09-15T13:52Z） | `phases/phase-0/reports/gate0_report.json`（**注意：见 §6 第 5 步，迁移后须复测**） |

### 3.2 未完成（接手后的工作面）

1. **环境迁移本体**（本交接文档 §5～§7 的全部动作）；
2. **ADR-0002 重测**：迁移后所有实测字段作废重填（节点/驱动/CUDA/K8s 版本/存储类/GPU 探测/Provider key）；
3. **Gate 0 双人签署**：架构负责人 + 1 名非编写成员复核签署 `gate0_report.json`（AC-10 最后一道人工动作）；
4. **独立保留集圈定**（ADR-0003 P2 收尾：≥10 事实 + ≥6 场景，不得用于调试）；
5. 阶段 1 预备：按 H200 显存重筛本地模型候选 2～3 个（引用官方模型卡，禁止凭印象），人格探针预测试、核心事实集 100 条扩充评估。

## 4. 基础设施变更（本次决策，ADR-0004）

| | 旧（本机，降级为开发备选） | 新（验收路径） |
|---|---|---|
| 形态 | Windows 11 + WSL2 + Docker Compose | **K8s 集群** |
| 数据库 | compose 内 `pgvector/pgvector:pg16`（localhost:5432） | `aisi-w7` 节点上的 PostgreSQL 16 + pgvector Pod（namespace `lifeos-dev`） |
| 推理 | 笔记本 RTX 4060 8GB（瓶颈） | `dtc-w1` 节点 **3× H200**（阶段 1 Provider B 部署目标） |
| 已实测记录 | `reports/envcheck.json`、ADR-0002（2026-09-15） | **全部作废重测** |

## 5. 代码与环境触点清单（迁移必改项，逐项打勾）

- [ ] **`k8s/` 目录**（新建）：建议清单见 §7——namespace `lifeos-dev`；postgres Deployment+PVC+Service（nodeSelector 钉到 `aisi-w7`）；推理占位 Deployment（`dtc-w1`，阶段 1 启用，先只做 GPU 探测 Pod）；**按集群实际的 StorageClass / 镜像仓库 / 节点 label 修改后才能 apply**；
- [ ] **`src/lifeos/store/db.py`**：`DEFAULT_DATABASE_URL` 指向集群内 DNS（形如 `postgresql+psycopg://lifeos:<密码>@postgres.lifeos-dev.svc.cluster.local:5432/lifeos`）；运行时一律以 `DATABASE_URL` 环境变量注入，**密码走 K8s Secret，不入库不入仓库**；
- [ ] **`alembic.ini` / `alembic/env.py`**：URL 同上；迁移改为集群内 Job 或进入应用 Pod 执行（`alembic -c alembic.ini upgrade head`）；
- [ ] **`src/lifeos/cli.py` 的 `envcheck()`**：把 docker 探测段替换为 kubectl 段——检查 namespace 存在、两节点 Ready、postgres Pod 健康、pgvector 扩展、在 GPU Pod 内执行 `nvidia-smi` 记录 3×H200、Provider key 改为探测 K8s Secret 存在性（只报名字，不报值）；
- [ ] **`scripts/gate0_check.sh`**：`docker compose up -d postgres` → `kubectl apply -k k8s/ && kubectl -n lifeos-dev wait --for=condition=ready pod -l app=postgres --timeout=120s`；`--with-db` 语义不变；
- [ ] **`tests/test_db_tier.py`**：保证 `DATABASE_URL` 可达（集群内 runner，或开发时 `kubectl port-forward`）；
- [ ] **文档回写**：02 文档 AC-01/AC-02 的命令、01 文档 §2.2，在迁移完成后按实际命令更新（当前以 ADR-0004 为准）。

## 6. 迁移后必须重跑的验证（顺序执行，全部留档）

1. `kubectl apply -k k8s/` → postgres Pod `ready` → `python -m lifeos.cli db wait`；
2. `alembic -c alembic.ini upgrade head`（新建库执行；已有库不重复执行）→ 15 表 + `lifeos_app` 权限（迁移 0001 自动创建角色并回收三事件表的 UPDATE/DELETE）；
3. `pytest tests -q -m "not db"`（25 项，纯函数级，应全过——与环境无关）；
4. `pytest tests -q -m db`（2 项：迁移/权限断言 + 持久化→回注水化→回放 100%→隔离）；
5. `bash scripts/gate0_check.sh --with-db` → 生成**新环境的** `reports/gate0_report.json`（覆盖旧报告前把旧的归档为 `gate0_report.20260915.local.json`）；**verdict 必须再次 PASS，才算迁移完成**；
6. **ADR-0002 逐项实测回填**（禁止凭记忆/估计填写）：k8s 版本、`aisi-w7` 规格（CPU/内存/磁盘/存储类）、`dtc-w1` 规格（3×H200 型号确认、驱动/CUDA、`nvidia-smi` 输出）、postgres Pod 资源限额、网络策略；
7. **本地模型候选重筛**（H200 显存宽裕，候选档位上调；引用官方模型卡）；
8. 遗留人工项：Gate 0 报告双人签署；独立保留集圈定（≥10 事实 + ≥6 场景）。

## 7. K8s 清单（按集群示例约定改写；来源＝`phases/phase-0/k8s-pod-example/`）

### 7.0 从示例吃透的集群约定（新清单必须遵守）

读透 `k8s-pod-example/{statefulset,pvc,secret}-example*.yaml` 后提炼的集群事实，逐条对照执行：

1. **GPU 资源名是 `nvidia.com/gpu.shared`**（共享 GPU/vGPU 方案），不是 `nvidia.com/gpu`；requests=limits 同值；
2. **必须 `runtimeClassName: nvidia`**；
3. **节点定位用 affinity 而非 nodeSelector**：GPU 池是 `dtc-w1`/`dtc-w2`（required In 两台 + preferred `dtc-w1`）；`aisi-w7` 这类单节点钉扎才用 required 单值；
4. **容器以 root 运行**：`securityContext.runAsUser: 0 / runAsGroup: 0`；
5. **镜像走内部仓库** `172.128.0.11:30500/dtc/...`（工作镜像 tag 形如 `gpu-cu128-tf2.18-torch2.7-jproot-coder-2026.05.12.3`，即 CUDA 12.8 / torch 2.7 基线），`imagePullPolicy: IfNotPresent`——LifeOS 自建镜像须推送到该仓库；
6. **存储用 `storageClassName: huawei-sc`、RWX 网络盘**（示例 3Ti，`*-network-pvc-rwx`），另配 `emptyDir medium: Memory` 挂 `/dev/shm`（16Gi）；
7. **服务三件套**：StatefulSet + headless Service（稳定 DNS）+ NodePort Service（外部访问，示例端口段 307xx）；
8. **Secret 用 Opaque + `stringData`**，容器经 `secretKeyRef` 注入（APP_PASSWORD / JUPYTER_TOKEN / CODE_SERVER_PASSWORD 同源一个 password key）；
9. **注意**：`k8s-pod-example/secret-exmaple.yaml` 内含真实形态的密码示例——按 §8 密钥红线，正式部署前轮换该密码，且不得把真实 Secret 提交进 git。

### 7.1 数据库（`aisi-w7`）—— Secret + StatefulSet + 双 Service

```yaml
# k8s/10-namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: lifeos-dev
---
# k8s/20-postgres.secret.yaml —— 正式密码勿提交 git（用 kubectl create secret 或 sealed-secrets）
apiVersion: v1
kind: Secret
metadata:
  name: lifeos-postgres
  namespace: lifeos-dev
type: Opaque
stringData:
  POSTGRES_USER: lifeos
  POSTGRES_PASSWORD: "CHANGE_ME_ROTATE_BEFORE_APPLY"
  POSTGRES_DB: lifeos
---
# k8s/30-postgres.yaml —— 钉扎 aisi-w7；存储沿用 huawei-sc
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: lifeos-postgres
  namespace: lifeos-dev
spec:
  serviceName: lifeos-postgres-headless
  replicas: 1
  selector:
    matchLabels: { app: lifeos-postgres }
  template:
    metadata:
      labels: { app: lifeos-postgres }
    spec:
      securityContext:
        runAsUser: 0
        runAsGroup: 0
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: kubernetes.io/hostname
                    operator: In
                    values: [aisi-w7]
      containers:
        - name: postgres
          image: 172.128.0.11:30500/dtc/pgvector:pg16     # 推送到内部仓库后用此地址
          imagePullPolicy: IfNotPresent
          ports: [{ containerPort: 5432, name: pg }]
          envFrom:
            - secretRef: { name: lifeos-postgres }
          resources:
            requests: { cpu: "2", memory: 4Gi }
            limits:   { cpu: "4", memory: 16Gi }
          readinessProbe:
            exec: { command: ["pg_isready", "-U", "lifeos", "-d", "lifeos"] }
            initialDelaySeconds: 5
            periodSeconds: 5
          volumeMounts:
            - name: pgdata
              mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
    - metadata:
        name: pgdata
      spec:
        accessModes: [ReadWriteMany]                      # 沿用集群 RWX 能力（huawei-sc）
        storageClassName: huawei-sc
        resources: { requests: { storage: 100Gi } }
---
# headless：稳定 DNS（StatefulSet 必配）
apiVersion: v1
kind: Service
metadata:
  name: lifeos-postgres-headless
  namespace: lifeos-dev
spec:
  clusterIP: None
  selector: { app: lifeos-postgres }
  ports: [{ name: pg, port: 5432, targetPort: 5432 }]
---
# 客户端入口：应用统一连 postgres.lifeos-dev.svc.cluster.local:5432
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: lifeos-dev
spec:
  selector: { app: lifeos-postgres }
  ports: [{ name: pg, port: 5432, targetPort: 5432 }]
```

> 连接串（写入 K8s Secret / 环境变量，勿入仓库）：`postgresql+psycopg://lifeos:<密码>@postgres.lifeos-dev.svc.cluster.local:5432/lifeos`。
> 调试用 NodePort 暴露 5432 属例外，须登记 ADR 并在用后关闭——默认仅集群内可达。

### 7.2 开发/推理工作 Pod（`dtc-w1`，可漂移 `dtc-w2`）—— 完全沿用 ai-stack 形态

```yaml
# k8s/40-dev-stack.yaml —— 接手智能大模型的工作环境 + 阶段 1 推理载体
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: lifeos-ai-stack
  namespace: lifeos-dev
spec:
  serviceName: lifeos-ai-stack-headless
  replicas: 1
  selector:
    matchLabels: { app: lifeos-ai-stack }
  template:
    metadata:
      labels: { app: lifeos-ai-stack }
    spec:
      runtimeClassName: nvidia                              # 集群约定
      securityContext: { runAsUser: 0, runAsGroup: 0 }
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: kubernetes.io/hostname
                    operator: In
                    values: [dtc-w1, dtc-w2]
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              preference:
                matchExpressions:
                  - key: kubernetes.io/hostname
                    operator: In
                    values: [dtc-w1]
      containers:
        - name: ai-stack
          image: 172.128.0.11:30500/dtc/ai-stack:gpu-cu128-tf2.18-torch2.7-jproot-coder-2026.05.12.3
          imagePullPolicy: IfNotPresent
          ports:
            - { containerPort: 22, name: ssh }
            - { containerPort: 8888, name: jupyter }
            - { containerPort: 7777, name: code-server }
          env:
            - name: APP_PASSWORD
              valueFrom: { secretKeyRef: { name: lifeos-ai-stack, key: password } }
            - name: JUPYTER_TOKEN
              valueFrom: { secretKeyRef: { name: lifeos-ai-stack, key: password } }
            - name: CODE_SERVER_PASSWORD
              valueFrom: { secretKeyRef: { name: lifeos-ai-stack, key: password } }
            - name: DATABASE_URL                            # 应用与测试统一从这里取
              valueFrom: { secretKeyRef: { name: lifeos-postgres, key: DATABASE_URL } }
          resources:
            requests: { nvidia.com/gpu.shared: 1, cpu: "8", memory: 128Gi }
            limits:   { nvidia.com/gpu.shared: 1, cpu: "8", memory: 128Gi }
          volumeMounts:
            - { name: work, mountPath: /data }
            - { name: dshm, mountPath: /dev/shm }
      volumes:
        - name: work
          persistentVolumeClaim:
            claimName: lifeos-work-rwx                      # huawei-sc RWX，按需定容
        - name: dshm
          emptyDir: { medium: Memory, sizeLimit: 16Gi }
---
apiVersion: v1
kind: Service
metadata:
  name: lifeos-ai-stack-headless
  namespace: lifeos-dev
spec:
  clusterIP: None
  selector: { app: lifeos-ai-stack }
  ports:
    - { name: ssh, port: 22, targetPort: 22 }
    - { name: jupyter, port: 8888, targetPort: 8888 }
    - { name: code-server, port: 7777, targetPort: 7777 }
---
apiVersion: v1
kind: Service
metadata:
  name: lifeos-ai-stack-nodeport
  namespace: lifeos-dev
spec:
  type: NodePort
  selector: { app: lifeos-ai-stack }
  ports:
    - { name: ssh, port: 22, targetPort: 22, nodePort: 30793 }
    - { name: jupyter, port: 8888, targetPort: 8888, nodePort: 30794 }
    - { name: code-server, port: 7777, targetPort: 7777, nodePort: 30795 }
```

配套 Secret：`lifeos-ai-stack`（key `password`，照示例 `stringData` 写法）与 `lifeos-postgres` 追加 key `DATABASE_URL`（整条连接串，供 `DATABASE_URL` 注入——`db.py`/`alembic`/pytest 全部从它读取）。

### 7.3 应用顺序与验证

```bash
kubectl apply -f k8s/10-namespace.yaml
kubectl apply -f k8s/20-postgres.secret.yaml
kubectl apply -f k8s/30-postgres.yaml
kubectl -n lifeos-dev wait --for=condition=ready pod -l app=lifeos-postgres --timeout=180s
kubectl apply -f k8s/40-dev-stack.yaml
# GPU 探测（在 ai-stack Pod 内，替代独立 gpu-probe）：
kubectl -n lifeos-dev exec lifeos-ai-stack-0 -- nvidia-smi   # 应见 H200；记录 3 卡型号/显存 → ADR-0002
# 数据库迁移与验收：
kubectl -n lifeos-dev exec lifeos-ai-stack-0 -- bash -lc "cd /data/LifeOS && alembic -c alembic.ini upgrade head && python -m pytest tests -q"
```

> 仓库本体放在 `/data`（RWX 网络盘），Pod 漂移（dtc-w1↔dtc-w2）不丢工作区；`lifeos-postgres-0` 的 DNS 为 `lifeos-postgres-0.lifeos-postgres-headless.lifeos-dev.svc.cluster.local`（headless 语义）。
> 本节清单已尽量贴合集群约定，但 **apply 前仍须核对**：镜像已推送、huawei-sc 可用、NodePort 30793-30795 未被占用、`DATABASE_URL` 密码已轮换。

## 8. 纪律红线（接手者必须遵守，违反即返工）

1. **gold set 已冻结**：`data/goldset/*/​*_v0.1.yaml` 与注册 hash 不可改；修订=新版本+重签+重注册（ADR-0003）；
2. **`deterministic_commit` 单一路径**：全仓库只允许 `pipeline.py`（运行时）与 `replay.py`（回放）调用——`verify boundary` 会查 import 图；
3. **append-only**：三事件表（raw/interpreted/domain）不得出现 UPDATE/DELETE 授权（迁移 0001 已回收，改动即破坏 AC-02）；
4. **诚实纪律**：ADR-0002 等实测字段禁止编造；引用先核对（规格书 §15）；gate0 报告不许静默 PASS（cli.py 已内置签署检查——**不要移除**）；
5. **材料口径**：评测材料来源/签署按 ADR-0003 P2 记录，论文引用不得表述为纯人工原创；参考答案/期望意图不得进入被测系统上下文；
6. **不轻信本交接文档**：接手后先跑 §6 第 3 步（纯函数测试）验证仓库完整性，再逐步推进。

## 9. 责任与联系

- 决策层/材料审定签署：Jiang Haipeng；材料互审签署：Searoc；
- 交接文档生成：原环境 AI 协作（2026-09-16），内容以仓库内 ADR/报告为准，本文如有出入以 ADR 与 gate0_report 为准。
