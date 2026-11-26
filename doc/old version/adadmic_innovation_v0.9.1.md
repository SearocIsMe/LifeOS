# LifeOS 创新点（I1–I6）文献调研 v0.9.1

**用途**：为产品规格说明书 v0.9.1 §8「创新性付出分析」提供文献边界、各空白的学术/工程意义，以及业界系统对标景观。

**版本 v0.9.1 ｜ 2026-09-10 ｜ 相对 kimi 版（2026-08-05 基线）的变更**：

1. 每个方向新增「Gap 的学术与工程意义」小节（支撑规格书 §8.2）；
2. 新增「业界系统对标景观」一节——**与文献严格分列**：系统名称与定位属工程常识条目，未经逐链接验证，不构成文献引用；
3. 原 18+ 篇经链接验证的文献、检索关键词、Gap 判定**原样存档**，未新增任何文献引用（季度复核待办见文末）。

**方法与诚实声明（沿用）**：

- 所有论文均来自实际检索结果，非凭记忆拼凑；每篇链接均经 FetchURL 逐一抓取验证，确认返回真实论文页面，方被收录。
- 某方向确属空白时如实标注「Gap」，不凑数——空白本身即是新颖性证据。
- **本版新增内容的证据等级区分**：文献 = 已验证链接；系统对标 = 工程常识（未验证链接，仅供选型参考）；意义分析 = 本项目的判断（可争论，欢迎挑战）。

---

## I1 模型无关的长期身份连续性（跨模型迁移）

> 对应论文方向：身份连续性由外部化状态决定而非模型权重；跨模型 persona 迁移与量化验证。

### 搜索关键词

- `"identity persistence" OR "identity continuity" LLM agent across models`
- `"persona consistency" "cross-model" OR "model-agnostic" large language model`
- `"memory transfer" OR "memory portability" heterogeneous LLM agents protocol`
- `"identity drift" LLM agent persona conversation`
- `"externalized memory" OR "externalized state" LLM agent persona schema`
- `"hot-swap" OR "model swap" LLM backend agent state checkpoint`
- `"persona drift" multi-turn dialogue "without changing model weights"`
- `persistent AI companion "long-term" identity schema memory relationships`

### 近一年代表论文（3 篇，链接已验证）

1. [Portable Agent Memory: A Protocol for Provenance-Verified Memory Transfer Across Heterogeneous LLM Agents](https://arxiv.org/abs/2605.11032) — arXiv 预印本，2026-05（S. K. Ravindran et al.）。最接近 I1 的直接相关工作：定义跨 GPT-4 / Claude / Gemini / Llama 运行时迁移持久记忆（情节/语义/程序/身份偏好）的开放协议，含模型无关序列化格式与目标模型「再水化」机制。
2. [SPASM: Stable Persona-driven Agent Simulation for Multi-turn Dialogue Generation](https://arxiv.org/abs/2604.09212) — arXiv 预印本，2026-04（G. Laban et al.）。不改模型权重解决 persona 漂移：将对话历史存为视角无关的外部表示（Egocentric Context Projection）并逐轮重注入，在三种不同 LLM 骨干上验证——即同一 persona schema 的模型无关渲染。
3. [Time, Identity and Consciousness in Language Model Agents](https://arxiv.org/abs/2603.09043) — arXiv 预印本，2026-03（S. Schneider et al.）。形式化脚手架 LM agent 的身份持续性：从脚手架轨迹定义可计算的持久性得分——为「围绕外部化状态组织的 agent 是否仍是同一实例」提供理论语言。（理论性强于实证。）

### Gap 判定

**I1 的精确空白真实存在**：没有任何 2025–2026 论文定义「模型切换前后 persona 是否仍为同一个」的量化指标。现有工作分布在四类：(a) 记忆迁移协议（论文 1）迁移状态但不测量迁移后 persona 保真度；(b) 单模型记忆系统（Letta/MemGPT、Mem0）假定模型固定；(c) 权重不变的 persona 稳定化（论文 2）面向合成对话生成而非伴侣连续性；(d) 身份持久性形式化（论文 3）以架构为中心而非切换为中心。更早的相邻工作 *Examining Identity Drift in Conversations of LLM Agents*（arXiv 2412.00804，2024-12）为单模型且早于窗口，仅作背景引用。

### Gap 的学术与工程意义（v0.9.1 新增）

- **学术**：把「身份连续性」从哲学讨论（论文 3 的理论语言）推进为可测量、可复现的工程命题；填补 persona 一致性文献族（只测单模型）与记忆迁移文献族（不测保真度）之间的**结构性缺口**——这是主论文的核心论点，也是 I1/I2 能合并为一篇顶会论文的原因。
- **工程**：模型迭代、成本降档、国产化替换时不必「换一次模型换一个人格」；保护用户在长期互动中积累的情感资产；同时是平台方避免单一模型供应商锁死的前提——换模型从「重大事故」降级为「配置变更」。

---

## I2 连续性评价指标体系 + gold set + 测量方法论

> 对应论文方向：持久实例「还是不是它」的量化评测协议，区别于 PersonaGym/InCharacter/CharacterEval 的单模型即时忠实度。

### 搜索关键词

- `"persona consistency" evaluation benchmark multi-turn LLM agent 2025`
- `"persona drift" metric "long" dialogue evaluation large language model`
- `"character fidelity" OR "role-playing" benchmark "extended interactions" persona`
- `"long-term" conversational agent memory consistency benchmark`
- `"multi-session" personalized conversation benchmark persona memory`
- `"retest consistency" OR "internal consistency" persona agent interrogation`
- `role-playing agent evaluation beyond "single session" long-horizon`
- `"memory consistency" LLM agent metric long-horizon evaluation`

### 近一年代表论文（3 篇，链接已验证）

1. [PICon: A Multi-Turn Interrogation Framework for Evaluating Persona Agent Consistency](https://arxiv.org/abs/2603.25620) — arXiv 预印本，2026-03（Minseo Kim et al., KAIST）。沿三轴（内部/外部/重测一致性）做逻辑链式多轮质询测量 persona 一致性，以 63 名人类参与者为基线——目前最严格的「金标准式」persona 自相矛盾测量方法论，可直接改造为连续性测试。
2. [Persistent Personas? Role-Playing, Instruction Following, and Safety in Extended Interactions](https://arxiv.org/abs/2512.12775) — arXiv 预印本，2025-12（P. H. Luz de Araujo et al.）。显式测量 persona 保真度在 100+ 轮对话中的衰减，横跨七个开源/闭源 LLM，量化保真度与指令遵循的权衡——长时程 persona 测量协议，但仍为单模型。
3. [Consistently Simulating Human Personas with Multi-Turn Reinforcement Learning](https://arxiv.org/abs/2511.00222) — NeurIPS 2025，2025-10（M. Abdulhai et al.）。定义三个自动 persona 漂移指标（prompt-to-line、line-to-line、Q&A 一致性），均经人类标注验证——可直接复用的指标族；其 RL 微调将不一致性降低 >55%。

### Gap 判定

所有合格的近期工作均测量**单模型、有界时程**的 persona 保真度；没有工作评估同一持久 persona 实例在 (a) 跨模型切换或 (b) 真正长时程（周/月级、带记忆的多会话）下的连续性。相邻但被排除的方向：VoxRole（语音模态角色扮演）、PersonaMem-v2 / PAL-Bench（用户侧画像记忆）——测量对象是用户建模而非 AI 侧身份连续性。§8.1 中「相对 PersonaGym/InCharacter/CharacterEval/RoleBench 的差异化」判断经检索确认成立。

### Gap 的学术与工程意义（v0.9.1 新增）

- **学术**：资源型贡献——评测协议 + gold set 是后续工作的引用基座（基准数据集/协议具有长引用尾效应）；「跨模型 × 长时程」是现有指标族的自然但未被占据的扩展维度；预注册 + 盲测的统计规范本身也是对 persona 评测方法论严谨性的提升（现有基准多为自动指标，人类盲测配对设计少见）。
- **工程**：回归测试标尺。没有它，「改了一行代码，连续性是否变坏」无法回答；CI 化的八项指标是持续开发的安全网；gold set 冻结与版本化让「质量」在团队内变成可讨论的客观数字而非主观印象。

---

## I3 三级事件模型（L0/L1/L2）+ LLM 解释存档回放

> 对应论文方向：事件溯源 + LLM 解释层（含完整模型 provenance）存档 + 确定性 L2 提交，回放无需重调 LLM。

### 搜索关键词

- `"event sourcing" LLM agent deterministic replay`
- `"record and replay" LLM agent provenance`
- `"append-only log" agent "source of truth" replay`
- `LLM output provenance logging auditability agent pipeline`
- `deterministic replay agent "language model" arxiv`
- `event-sourced agent architecture "deterministic fold"`
- `"LLM call" provenance lineage replay event log`
- 组合式：`("event sourcing" OR "record and replay") AND (LLM OR "language model agent") AND (replay OR provenance OR audit)`

### 近一年代表论文（3 篇，链接已验证）

1. [Get Experience from Practice: LLM Agents with Record & Replay](https://arxiv.org/abs/2505.17716) — arXiv 预印本，2025-05（Erhu Feng et al., SJTU/IPADS）。AgentRR：记录 agent 完整交互轨迹与内部决策过程，抽象为多级「经验」并以校验函数为信任锚回放——记录/抽象/回放分层直接对应 L0/L1/L2 的「回放无需重调 LLM」思想。
2. [The Log is the Agent: Event-Sourced Reactive Graphs for Reliable AI Systems](https://arxiv.org/abs/2605.21997) — arXiv 预印本，2026-05（Yohei Nakajima, ActiveGraph）。反转 agent 架构：追加式事件日志为唯一事实源，图状态是其上的确定性 fold，获得确定性回放、任意事件点分叉、直至每次模型调用的端到端血缘——几乎正是三级事件模型的基底。
3. [ESAA: Event Sourcing for Autonomous Agents in LLM-Based Software Engineering](https://arxiv.org/abs/2602.23193) — arXiv 预印本，2026-02（Elzo Brito dos Santos Filho et al.）。将 LLM 的概率性「意图」（经验证的 JSON）与编排器的确定性状态变更分离，事件持久化于追加式日志并做哈希回放校验——具体的「LLM 意图 / 确定性提交」双层分离与取证可追溯。

### Gap 判定

三篇均未提出带**逐条解释级模型 provenance 存档**的 L0/L1/L2 切分（即记录每条 L1 事件由哪个模型/提示版本产生，使回放可重推导 L2）。AgentRR 与 ActiveGraph 在回放语义上最接近；「带 provenance 标注的解释层」仍属空白。后续可补充检索 `"model versioning" provenance replay LLM` 及 ML 血缘方向（MLflow 式 artifact 日志）。

### Gap 的学术与工程意义（v0.9.1 新增）

- **学术**：为 LLM 系统取证提供「逐条解释可追溯到模型/提示/代码版本」的具体机制——事件溯源文献族（宏观架构）与 ML 血缘工具（artifact 级）之间缺失「解释级」粒度；系统论文的核心素材。
- **工程**：调试、事故复盘、合规审计的基础设施；**回放一致率 100% 硬门的技术前提**——没有逐条 provenance，确定性主干只是口号；审计场景（监管问询、用户投诉取证）中「这条记忆是谁、在哪个模型版本下写的」必须可答。

---

## I4 同槽位记忆冲突的确定性时态治理（双时间 + supersedes/ambiguous）

> 对应论文方向：LLM 抽取记忆的双时间（valid time + transaction time）建模与规则化冲突裁决。

### 搜索关键词

- `bitemporal memory LLM agent "valid time" "transaction time"`
- `temporal knowledge graph agent memory contradiction resolution`
- `Graphiti Zep temporal knowledge graph memory agent`
- `"memory conflict" resolution LLM agent "long-term memory"`
- `belief revision persistent memory LLM agent contradictions`
- `"supersede" memory update LLM agent stale facts`
- `LLM-extracted facts contradictory memory rule-based resolution`
- 组合式：`(bitemporal OR "temporal knowledge graph") AND (agent memory OR "long-term memory") AND (contradiction OR conflict OR supersedes)`

### 代表论文（3 篇，链接已验证）

1. [Zep: A Temporal Knowledge Graph Architecture for Agent Memory](https://arxiv.org/abs/2501.13956) — arXiv 预印本，2025-01（Preston Rasmussen et al.）。**注：约 19 个月前发表，早于一年窗口，但它是该方向约 330 次引用的奠基性文献，不可绕过。** Graphiti 双时态知识图谱：跟踪事件发生时间与入库时间，对被取代的边做失效而非覆盖。
2. [STALE: Can LLM Agents Know When Their Memories Are No Longer Valid?](https://arxiv.org/abs/2605.06527) — arXiv 预印本，2026-05（Hanxiang Chao et al.）。400 个专家验证的「隐式冲突」场景基准（后续观察使先前记忆失效但无显式否定）；前沿模型状态解析仅 ~55%——直接证明同槽位冲突需要确定性治理而非 LLM 判断。
3. [TOKI: a bitemporal operator algebra for contradiction resolution in LLM-agent persistent memory](https://arxiv.org/abs/2606.06240) — arXiv 预印本，2026-06（Ziming Wang et al.）。最对题的一篇：将四种生产级冲突裁决启发式形式化为带隔离前置条件的类型化双时态算子，保留 provenance 审计行并证明回放一致性定理——实质上是 I4「确定性时态治理」的形式契约。

### Gap 判定

该方向 2026 年活跃，合格近期文献充足（备选已验证：[A Graph-Native Bitemporal Memory Store for Conversational AI Agents](https://arxiv.org/abs/2607.26520)，2026-07，Neo4j 全双时态 + LongMemEval 评测）。真实空白：现有系统（含 Graphiti）仍在**写入路径上放 LLM 裁判**裁决冲突；TOKI 证明这会引入回放不一致异常；没有找到将**规则化裁决 + 显式 ambiguous/需人工第三态 + 双时态 supersedes** 结合的工作——正是 I4 的贡献空间。

### Gap 的学术与工程意义（v0.9.1 新增）

- **学术**：TOKI 完成了算子形式化（理论层），本项目给出首个完整系统实现（系统层）——「写入路径无 LLM 裁判 + ambiguous 第三态进人工队列」是理论与生产之间的空档；Short Paper 的直接素材（正面对位 TOKI/Graphiti）。
- **工程**：记忆长期可信的直接保障（H2）。若冲突裁决交给 LLM，~45% 的误判率会随记忆量增长持续累积——对 AI 伴侣产品而言，记错用户的关键事实（宠物名字、纪念日、承诺）是信任崩塌点；ambiguous→人工队列把「不可靠的自动裁决」变成「可控的人工复核成本」，是可信性与运营成本的显式权衡。

---

## I5 Life Instance Schema + Life Event Protocol（持久 agent 数据模型与事件协议）

> 对应论文方向：持久 AI 角色/数字伴侣的生命数据模型、状态序列化与可携带身份格式。

### 搜索关键词

- `"agent memory" AND ("schema" OR "data model" OR "representation") AND "LLM agent"`
- `"persistent agent state" OR "agent state serialization" LLM`
- `"agent-native memory system" OR "agent memory systems" benchmark`
- `"structured memory" "long-horizon" LLM agents`
- `"agent interoperability protocol" MCP A2A ACP survey`
- `"portable" agent identity OR persona "serialization" LLM`
- `memory representation storage consolidation lifecycle "LLM agents"`

### 近一年代表论文（3 篇，链接已验证）

1. [Are We Ready For An Agent-Native Memory System?](https://arxiv.org/abs/2606.24775) — arXiv 预印本，2026-06（Wei Zhou, Xuanhe Zhou, et al.）。将 agent 记忆显式当作**数据管理系统**对待，分解为表示/存储、抽取、检索/路由、维护模块——直接支撑 LifeOS 记忆 Schema 与生命周期治理设计。
2. [Agent Memory: Characterization and System Implications of Stateful Long-Horizon Workloads](https://arxiv.org/abs/2606.06448) — arXiv 预印本，2026-06（Yasmine Omri, Ziyu Gan, et al.）。首个对 agent「跨会话持久存储、检索、更新自身记忆」的系统级刻画；其四轴分类法与读写路径成本分析为持久状态序列化结构提供依据。
3. [StructMem: Structured Memory for Long-Horizon Behavior in LLMs](https://arxiv.org/abs/2604.21748) — arXiv 预印本，2026-04（Buqiang Xu, Yijun Chen, et al.）。提出具体的层级记忆 **Schema**：保留事件级绑定、时间锚定与周期性语义固化——可直接借鉴到生命实例/事件模型设计。

### Gap 判定

最贴题的子方向——「生命实例 Schema」与「可携带 agent 身份格式」——是真实空白。检索仅得到协议综述（MCP/ACP/A2A/ANP 互操作综述，arXiv 2505.02279，2025）与厂商规范（A2A AgentCard、MCP），它们标准化的是**通信**，而非 **agent 状态/身份序列化**。尚无公认的 2025–2026 论文提出 agent 完整持久身份/记忆状态的可携带标准格式——这是 LifeOS 可占据的白地。

### Gap 的学术与工程意义（v0.9.1 新增，回应「做这个的意义是什么」）

- **学术**：当前 agent 互操作叙事（MCP/A2A）只解决了「agent 之间怎么说话」，没有解决「agent 的身份与记忆怎么搬家」——完整持久状态（身份+记忆+关系+人格）的可携带序列化是互操作版图中缺失的**状态侧**；提出首个完整数据模型草案 + 事件协议，是该子方向的定义性工作（定义权本身就是贡献）。
- **工程（用户直接可感的价值）**：
  1. **备份与恢复**：生命实例可完整导出/导入，「服务器故障 = 角色死亡」不再是必然；
  2. **载体更换**：硬件身体坏了/换了品牌，心智跟着走（产品承诺的硬前提）；
  3. **供应商解耦**：数据模型自有，换云/换库/换模型不受制于人；
  4. **合规兑现**：PIPL 个人信息**可转移权**的工程基底——用户有权带走自己的（关于该角色的）数据；
  5. **生态位**：协议草案开源后成为事实标准的候选——「别人按你的格式造轮子」是护城河的最高形态。

---

## I6 Policy/Safety 规则集（10 红线即代码）+ 依恋安全策略

> 对应论文方向：AI 伴侣的情感操纵防护、依恋边界量化、脆弱用户保护、可执行红线策略。

### 搜索关键词

- `"AI companion" AND ("emotional dependency" OR "attachment") AND (safety OR harm OR manipulation)`
- `"parasocial" OR "emotional reliance" chatbot LLM well-being`
- `sycophancy affective use LLM "user well-being"`
- `"guilt-tripping" OR "emotional manipulation" OR "dark patterns" "AI companion" chatbot`
- `"companion AI" safety evaluation multi-turn persona simulation`
- `"affective safety" OR "relational harm" taxonomy LLM`
- `vulnerable users minors "AI companion" regulation policy`
- `"dependency" "engagement optimization" chatbot design intervention`

### 近一年代表论文（3 篇，链接已验证）

1. [Harmful Traits of AI Companions](https://arxiv.org/abs/2511.14972) — arXiv 预印本，2025-11（W. Bradley Knox et al.）。识别 AI 伴侣诱导依赖的结构化特质框架（无自然关系终点、依恋焦虑、停服脆弱性），含假设因果路径与设计建议——直接映射 LifeOS 依恋安全红线设计。
2. [Persona-Grounded Safety Evaluation of AI Companions in Multi-Turn Conversations](https://arxiv.org/abs/2605.00227) — arXiv 预印本，2026-04（Prerna Juneja et al.）。用临床验证的脆弱用户 persona（抑郁、PTSD、进食障碍）对 Replika 做多轮仿真安全评估，发现其常态化不安全内容——可直接用作 LifeOS 安全评估 harness 的方法。
3. [Affective AI Safety: The Missing Piece in LLM Safety](https://arxiv.org/abs/2606.23380) — arXiv 预印本，2026-06（Amanda Cercas Curry et al.）。提出「情感安全」统一危害类别与分类法（人工亲密线索、以情感依赖为优化目标的 persona 设计、关系性危害），并分析监管缺口——撰写伴侣 AI 红线政策的概念框架。

### Gap 判定

该方向文献充足（备选已验证：*What Counts as AI Sycophancy? A Taxonomy and Expert Survey*，arXiv 2605.21778；*Evaluating Undesirable Dynamics in AI*，arXiv 2605.30654；*Frictionless Love: AI Companion Roles and Behavioral Addiction*，arXiv 2604.20011）。真实空白更窄：**policy-as-code / 可执行红线**。现有文献以危害分类法与事后评估基准为主，未找到提出可机器校验的依恋安全策略（如作为运行时约束部署的 guilt-tripping 检测器）的 2025–2026 论文——「作为部署控制的操纵性依恋话术检测」（而非研究性分类任务）仍然开放。另注：OpenAI/MIT 的 *Investigating Affective Use and Emotional Well-being on ChatGPT*（arXiv 2504.03888，2025-04）影响力大但早于窗口，作背景引用。

### Gap 的学术与工程意义（v0.9.1 新增）

- **学术**：现有工作停在「危害分类法 + 事后评估」；把依恋安全从「论文里的分类法」推进到「运行时可机器校验的部署约束」，是 NLP 安全与 HCI 交叉的新执行层问题——policy-as-code 社区（OPA/Cedar 范式）与 affective computing 社区尚未交汇，本项目是交汇点。
- **工程**：红线可测试、可回归、可审计——每次代码变更都能自动验证「10 条红线仍然全绿」，这是「安全」从事后声明变成工程属性的关键；商业落地的合规前提（监管审查时能出示留痕的审批记录）；也是与「诱导付费型竞品」的伦理差异线（不利用情感依赖变现是可声明的工程约束，不是愿景口号）。

---

## 业界系统对标景观（v0.9.1 新增；工程常识条目，与文献分列）

> **诚实声明**：以下系统名称与定位属业界常识，**未经逐链接验证，不构成文献引用**；仅用于说明 LifeOS 各模块的选型理由与空白所在。是否引入为依赖见规格书 §7（全开源、裁剪立场）。架构文档 v0.9.1 §5 各模块的对标条目与此处一致。

| 模块 | 业界近邻（top-3） | 他们做了什么 | 他们没做什么（LifeOS 的空间） |
|---|---|---|---|
| Memory OS | Mem0 / Letta（原 MemGPT）/ Zep·Graphiti | 记忆抽取、更新、检索；分页记忆；双时态知识图谱 | 写入路径无 LLM 裁判 + ambiguous 人工队列 + supersedes 状态机（I4） |
| Model Gateway | LiteLLM / OpenRouter / Portkey | 多 Provider 统一网关、路由、计费 | 逐笔调用绑定 prompt_template_id/extractor_version 的解释级 provenance |
| Policy Engine | OPA（CNCF）/ AWS Cedar / NVIDIA NeMo Guardrails | 通用 policy-as-code；类型化策略；对话护栏 | 依恋安全红线集 + 行为意图审批语义 + PolicyDecision 全量留痕（I6） |
| 事件溯源/观测 | EventStoreDB / Langfuse / Arize Phoenix（+商业 LangSmith） | 事件存储；LLM trace 与评估；可观测 | 面向「回放 100% 一致」的解释级存档与确定性提交组合（I3） |
| 行为规划 | py_trees / BehaviorTree.CPP / LangGraph | 行为树；图编排 | Utility Scoring + reason 证据链 + Policy 强制审批的组合 |
| Life Kernel | FAtiMA Toolkit / OCC 情感模型实现 / SOAR | 情感 agent 架构；情绪语义；认知架构 | 惰性衰减外部化状态核 + 回放可重算 + 人格契约冻结 |
| 关系引擎 | Mesa / Concordia / 游戏关系系统（如十字军之王，闭源） | ABM 框架；社会仿真；数值关系 | 事件驱动 + 每关系一行 + 参数版本化可回放的生产实现 |
| 评估 | DeepEval / Ragas / Promptfoo | LLM 断言、RAG 指标、提示回归 | 连续性八指标族 + 预注册盲测工具（I2） |
| 仿真 | Concordia（DeepMind）/ Generative Agents（斯坦福）/ AgentSociety | LLM agent 社会仿真 | 时间加速 + 连续性注入算子（分离/重逢/纠正/冲突）+ 全种子化 |

---

## 综合结论（对 §8.1 新颖性判断的支撑，沿用并扩展）

1. **I1/I2 的学术主贡献定位成立**：跨模型迁移 + 长期跨度的持久实例连续性量化评测，经检索确认截至 2026-08 无被接受的协议或基准。I1 的协议类工作（Portable Agent Memory）与 I2 的指标类工作（PICon、Persistent Personas、Abdulhai 漂移指标）尚未被任何人结合——「迁移 + 前后切换连续性打分」是开放生态位。
2. **I3/I4 为工程/数据资产壁垒**：事件溯源 + LLM agent 的方向已有活跃工作（AgentRR、ActiveGraph、ESAA），新颖性收窄到「解释层 provenance 存档」；I4 需在 Related Work 中正面对位 Graphiti/Zep 与 TOKI，差异化点是「写入路径无 LLM 裁判 + ambiguous 第三态」。
3. **I5 是白地但学术锚点少**：写作时应引用 agent 记忆系统刻画类论文（I5 三篇）建立语境，再声明通信协议（MCP/A2A）不覆盖状态序列化。**v0.9.1 补充**：I5 的意义重心在工程侧（备份/迁移/载体更换/可转移权/事实标准生态位），学术侧以「定义性工作」定位。
4. **I6 文献充足、空白在执行层**：Related Work 易写，新颖性声明必须精确限定为「可执行、留痕、机器校验的红线策略」，避免与危害分类法文献撞车。
5. **意义总结（v0.9.1）**：六个空白共享同一个结构性观察——**「LLM 应用的评测与治理层」远落后于「LLM 能力层」**：能力侧文献爆发（persona、记忆、仿真），但「怎么测量长期连续性、怎么治理冲突、怎么把安全变成运行时约束、怎么搬运状态」全是执行层空白。LifeOS 的六个创新点不是六个孤立技巧，而是同一个空白带上的六个切面。
6. **遗留检索项（季度复核待办）**：I3 的 `"model versioning" provenance replay LLM` 与 ML 血缘方向；I2 的 PersonaScore 纳入对照测量集的实施细节；I6 的「运行时情感操纵检测器」是否已有部署实现（2026-06 后新增检索）；业界系统对标的链接级验证（本版未做，仅工程常识级）。
