# data/consent/：法域 × 语言同意模板装载（Phase 3 S2）

- 来源：[`doc/templates/consent/consent_template_zh.yaml`](../../doc/templates/consent/consent_template_zh.yaml)（阶段 2 S5 工件）；
- 装载形态：按 **法域（CN/SG/HK/MO）× 语言（zh）** 拆分为 4 份独立模板，每份 `jurisdiction` 唯一、条款结构一致、法条引用各异（规格书 §9.4 统一工程落地：jurisdiction 字段 + 模板版本化）；
- 版本纪律：`template.version` 遵循 `document_version` 版本化管理；模板变更走 ADR + 重新签署，**不可原地改**（阶段 0 冻结纪律沿用）；
- 两级删除语义与 30 天备份窗口披露在 `data_deletion` 条款中明示（规格书 §9.3）；
- 性质：装载模板（施测用），非评测材料；签署字段为空位（施测期由被试与负责人签署，不预填——README 签署纪律沿用）。
