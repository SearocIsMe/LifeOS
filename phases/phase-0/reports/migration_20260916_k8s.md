# K8s 集群迁移执行记录（HANDOVER §5–§8 全程留档）

- 执行：2026-09-16，执行者＝接手 AI 协作（在 `aisi-w4` 节点操作 kubectl），决策依据 [ADR-0004](../adr/ADR-0004_部署环境迁移至K8s集群.md) 与 [HANDOVER](../HANDOVER_迁移K8s集群交接.md)
- 结论：**迁移完成，Gate 0 在新环境复测 verdict=PASS**（`gate0_report.json` @ 2026-09-16T03:15Z；旧报告归档为 `gate0_report.20260915.local.json`）
- 执行方式：用户指定的「每步确认」模式（§1–§5 每步经用户确认后执行）

## 1. 实测数据（ADR-0002 回填依据，全部 kubectl/API/命令实测）

| 项 | 实测值 | 来源 |
|---|---|---|
| K8s 版本 | server/节点全部 v1.28.15（10 节点 Ready），containerd 1.6.38 | `kubectl get nodes -o wide` |
| `dtc-w1` GPU | **3× NVIDIA H200 NVL**，单卡 143771 MiB，驱动 570.148.08，CUDA 12.8，compute 9.0；Supermicro AS--5126GS-TNRT | 节点标签 `nvidia.com/gpu.count/product/memory` + Pod 内 `nvidia-smi` |
| GPU 共享方案 | **time-slicing 30 份/卡**（`gpu.replicas=30`），资源名 `nvidia.com/gpu.shared`，capacity=90（3×30）；单 Pod 内 nvidia-smi 见 1 个 H200 实例（按分配暴露，预期行为） | `gpu-operator/time-slicing-config`（h200-30x）+ 节点标签 |
| `aisi-w7` 规格 | 384 CPU / ~2.2TiB 内存 / ~3.4TiB 磁盘；taint `mpc-cpt-role=infra:NoSchedule`（postgres Pod 加 toleration，节点未改） | `kubectl get node -o jsonpath` |
| 存储 | huawei-sc（csi.huawei.com，RWX，Immediate）；pgdata 100Gi、lifeos-work-rwx 50Gi 均 Bound | `kubectl get sc/pvc` |
| postgres Pod | 1/1 Running @ aisi-w7；requests 2C/4Gi、limits 4C/16Gi；readinessProbe pg_isready；PGDATA=`/var/lib/postgresql/data/pgdata` | `kubectl get pod/describe` |
| 数据库 | 16 表（15 实体 + alembic_version）；pgvector 扩展可用；`lifeos_app` 角色 SELECT/INSERT，raw/interpreted/domain 三表 UPDATE/DELETE 已回收（`has_table_privilege=false` 实测） | Pod 内 SQL 验证 |
| Provider key | 未配置（无 `lifeos-provider*` Secret；envcheck 只报名字） | `kubectl get secrets` |
| 镜像 | `172.128.0.11:30500/dtc/pgvector:pg16` 已推送（tags list + manifest 200）；ai-stack 沿用 `dtc/ai-stack:gpu-cu128-tf2.18-torch2.7-jproot-coder-2026.05.12.3` | registry HTTP API |

## 2. 验证结果（HANDOVER §6 顺序）

1. `kubectl apply -k k8s/` → postgres Pod ready ✅（`db wait` 经 port-forward 验证可达）
2. `alembic -c alembic.ini upgrade head`（Pod 内，新建库）✅ → 16 表 + `lifeos_app` 权限回收 ✅
3. `pytest tests -q -m "not db"` → **25/25**（宿主机 Python 3.12.14 venv 与 ai-stack Pod Python 3.10.12 双环境各验一次）✅
4. `pytest tests -q -m db` → **2/2**（Pod 内 runner + 宿主机 port-forward 双路径）✅
5. `bash scripts/gate0_check.sh --with-db` → 新 `gate0_report.json` **verdict=PASS**（7 项工程检查 + core_facts/behavior_scenario 双 pass + env.overall=pass）✅
6. ADR-0002 逐项实测回填 ✅（模型候选清单留待负责人查官方模型卡签署）
7. 遗留人工项：Gate 0 双人签署；独立保留集圈定（≥10 事实 + ≥6 场景）；Provider key 配置与计费告警；`downgrade base` 可逆性演练（破坏性，须专用库+双人确认）

## 3. 过程事件与修复（诚实记录）

1. **`__init__.py` 整批丢失（仓库完整性事件）**：`.gitignore` 的 `_*.*` 模式误伤所有 `__init__.py`，git 迁移时全部丢失 → `from lifeos import POLICY_VERSION` 等 8 测试失败、`data/` 材料同样未随 git 迁移。已重建 6 个 `__init__.py`（版本常量 0.1.0 取自已归档 gate0_report；再导出按仓库实际用法），`.gitignore` 加 `!__init__.py` 例外。**教训：`_*/`、`_*.*` 类 ignore 模式会吞掉 dunder 文件。**
2. **gold set 冻结材料核验**：用户找回原版 `data/goldset/` 两个 v0.1.0 yaml，items hash 与注册 manifest **逐字一致**（`506c9f4c…` / `e4bef442…`），签署块为原件（Jiang Haipeng / Searoc）。两个 format template 按validator+测试契约重建（文件头标注性质，非评测材料）。
3. **pgvector 镜像推送**：首次 ctr push 因 tag 指向多架构 index 且本地缺子 manifest 失败（`content digest not found`）→ `--all-platforms` 完整拉取后推送成功。
4. **postgres 调度失败**：aisi-w7 taint → 按用户选定方案在 Pod 加 toleration（节点未动，零副作用）。
5. **postgres CrashLoop**：huawei-sc 卷根只读 `.snapshot`（NAS 快照目录）破坏入口脚本 chown → PGDATA 改指子目录 `…/data/pgdata`（NAS 跑 postgres 的标准做法）。
6. **`db wait` 退出码恒 0**：`cli.py` 的 `db wait` 无论可达与否都 exit 0（仅打印 reachable 布尔），脚本改用 `wait_for_db` 真实退出码探针；**cli 语义未改**。
7. **容器层易失**：Pod 重建后装在 `/home/app/.venv` 的依赖丢失 → 项目 venv 改建在 PVC `/data/LifeOS/.venv`（持久化，Pod 漂移/重建不丢）。
8. **密码轮换 ×1**：初次生成的 `DATABASE_URL` 前缀（含密码）在调试输出中出现过一次 → 已执行完整轮换（`ALTER USER` + Secret 重建 + 双 StatefulSet 滚动重启 + db tier 复测 2/2）。现值只存在于集群 Secret，未再外泄。

## 4. 交付物清单

- `k8s/`（新建）：[kustomization](../../k8s/kustomization.yaml)、[create-secrets.sh](../../k8s/create-secrets.sh)（Secret 创建/轮换脚本，固化迁移中手工执行的命令）、[10-namespace](../../k8s/10-namespace.yaml)、[20-postgres.secret.example（模板）](../../k8s/20-postgres.secret.example.yaml)、[30-postgres](../../k8s/30-postgres.yaml)、[40-dev-stack](../../k8s/40-dev-stack.yaml)、[50-work-pvc](../../k8s/50-work-pvc.yaml)、[README](../../k8s/README.md)
- 代码触点：[db.py](../../../src/lifeos/store/db.py)（集群 DNS 默认值）、[alembic.ini](../../../alembic.ini)/[env.py](../../../alembic/env.py)（DATABASE_URL 优先）、[cli.py envcheck()](../../../src/lifeos/cli.py)（kubectl 探测段）、[gate0_check.sh](../../../scripts/gate0_check.sh)（K8s 路径 + 自动 port-forward）、[test_db_tier.py](../../../tests/test_db_tier.py)、[pyproject.toml](../../../pyproject.toml)、[docker-compose.yml](../../../docker-compose.yml)（标注降级）
- 报告：`gate0_report.json`（新环境 PASS）、`gate0_report.20260915.local.json`（归档）、本记录
- 文档回写：[ADR-0002 追记](../adr/ADR-0002_Gate0环境检查记录.md)（实测回填）、01 §2.2.1、02 AC-01/AC-02 执行记录

## 5. 新环境速查

```bash
# 应用入口（ai-stack Pod，仓库在 /data/LifeOS，venv 在 /data/LifeOS/.venv）
kubectl -n lifeos-dev exec lifeos-ai-stack-0 -- bash -lc "cd /data/LifeOS && .venv/bin/python -m pytest tests -q -m db"

# 一键 Gate 0（宿主机，aisi-w4；自动 port-forward，密码从 Secret 读取不打印）
PYTHON="$PWD/.venv/bin/python" bash scripts/gate0_check.sh --with-db

# GPU 探测
kubectl -n lifeos-dev exec lifeos-ai-stack-0 -- nvidia-smi
```
