# 阶段 0：契约与可重放骨架（Phase 0）

> 对应《LifeOS_研发路线图_v0.9.1》§2「阶段 0：契约与可重放骨架」。
> 周期 3 周 ｜ 2 人 ｜ 1～2 人月 ｜ 出口 = Gate 0。

## 本阶段回答的问题

- **做什么**：Schema（15 实体）+ 三级事件协议（L0/L1/L2）+ `deterministic_commit` + Policy 最小骨架（2 条红线）+ 回放取证 + 50 条核心事实集 / 30 个行为场景落库注册。
- **为什么先做它**：它是唯一「做对做错立刻知道」的阶段——回放一致率要么 100% 要么不是；全部后续工作都建立在这份契约上（路线图 §1.0）。
- **验证对象**：自动化断言（CI）+ 开发团队双人互审；结论只对工程团队内部有效（路线图 §1.1）。

## Gate 0 判据（规格书 §10，未通过只改契约层，不做 UI/Demo）

1. 示例事件全链路 round-trip（L0→L1→L2→状态写）；
2. 相同 L2 重放 100% 一致；
3. LLM 输出不能直写权威表；
4. Policy 拒绝后无状态副作用。

## 文档索引

| 文档 | 内容 | 读者 |
|---|---|---|
| [01_详细设计.md](01_详细设计.md) | 阶段 0 全部契约与模块的详细设计（15 实体、事件协议、`deterministic_commit`、Policy、隔离、事务、回放、gold set 落库） | 全体成员 |
| [02_工程设计执行方案.md](02_工程设计执行方案.md) | 按周/天的任务分解与执行步骤；10 个验收 case（AC-01～AC-10）的精确定义与验证命令；Gate 0 报告流程 | 工程执行者 |
| [03_核心事实集与行为场景编写规范.md](03_核心事实集与行为场景编写规范.md) | 「50 条核心事实必须人工编写」的原因、要求、规格定义、双人互审流程与校验器清单 | 事实/场景编写人与审校人 |
| [adr/ADR-0001_阶段0边界参数确认.md](adr/ADR-0001_阶段0边界参数确认.md) | Day 1 必须落档的边界参数记录 | 决策层 |
| [adr/ADR-0002_Gate0环境检查记录.md](adr/ADR-0002_Gate0环境检查记录.md) | GPU/模型候选/Provider key/Docker 版本实测记录（**须由负责人实测填写，禁止虚构**） | 工程负责人 |

## 目录约定

```
phases/
  phase-0/            ← 本阶段（设计 + ADR + 报告）
    reports/          ← Gate 0 验收报告等产物（由验证命令生成）
  phase-1/            ← 阶段 1 启动时创建
  phase-2/            ← 阶段 2 启动时创建
  phase-3/            ← 阶段 3 启动时创建
```

代码骨架在仓库根目录（`src/lifeos/`、`alembic/`、`tests/`、`scripts/`、`data/goldset/`、`docker-compose.yml`）——阶段 0 的工程定位就是「初始化这个仓库」。

## 快速开始（验证工具）

```bash
# 纯本地（无需数据库）：跑全部纯函数级验收
python3 -m pytest tests -q -m "not db"
python3 -m lifeos.cli verify all

# 需要数据库：启动 PostgreSQL + pgvector 后
docker compose up -d postgres
python3 -m pytest tests -q -m db

# 一键 Gate 0 自检（生成报告）
bash scripts/gate0_check.sh            # 不含 DB 层
bash scripts/gate0_check.sh --with-db  # 含 DB 层（需 Docker）
```

## 当前状态（诚实记录，随进度更新）

- [x] 阶段 0 详细设计文档（01/02/03 + ADR-0001/0002）
- [x] 工程骨架代码（15 实体 Schema、事件管线、`deterministic_commit`、Policy 最小骨架、回放取证、gold set 校验器/注册、CLI、27 项自动化测试）
- [x] 工程验证实际跑通（2026-09-15）：tier A 25/25 PASS；PostgreSQL 16+pgvector 容器启动、alembic 0001 迁移应用、tier B 2/2 PASS；Gate 0 四条判据全部 pass
- [x] Gate 0 报告已生成：`reports/gate0_report.json`（verdict=**INCOMPLETE**——工程判据全过，仅 gold set 材料待人工编写，见下两条）
- [ ] **50 条核心事实集人工编写 + 双人互审**（等待团队执行，规范见 03 文档；任何 LLM 不得代写，本仓库亦不会预置代写内容）
- [ ] **30 个行为场景人工编写 + 双人互审**
- [ ] ADR-0002 剩余字段补测（本地模型候选清单 2～3 个、云 Provider key 与计费告警；GPU/Postgres/Docker 已实测记录）
- [ ] Gate 0 报告签署（材料齐 + 补测齐后重跑 `bash scripts/gate0_check.sh --with-db`，verdict 转 PASS 后双人签署）

> 运行环境注意：Docker 位于 WSL2 内（Windows 主机 PATH 无 docker 命令）。WSL 下一键自检：
> `wsl bash -c "cd /mnt/c/00-work/07-Self/LifeOS && PYTHON=/mnt/c/00-work/07-Self/LifeOS/.venv/Scripts/python.exe bash scripts/gate0_check.sh --with-db"`
