# 退出-擦除演练记录（Phase 3 S3 §3.3，真数据链路演练）

> 演练日期：2026-09-30（mock 数据演练；真数据演练在 Pilot 入组后按同口径执行）。
> 口径：spec §9.3 两级删除 + 一票否决第 5 条（删除后残留即 No-Go）+ 知情同意书披露条款（30 天备份窗口，ADR-0007）。

## 1. 演练步骤与实测结果

| 步骤 | 动作 | 实现落点 | 实测结果 |
|---|---|---|---|
| 1 | 入组参与者拥有 1 条记忆 | `EventPipeline.ingest`（consent 已授） | ✅ 记忆落库 |
| 2 | 参与者行使撤回权（revoke） | `lifeos.consent.revoke_and_erase`（append-only trail 写 `revoked_at`） | ✅ 撤回写入，处理停止 |
| 3 | 撤回联动自动触发用户擦除 | `revoke_and_erase` → `store.erase.user_erase` | ✅ 自动擦除，零残留 |
| 4 | 全介质清除（权威行 + 向量通道） | `user_erase`（物理行删除 + outbox 清除） | ✅ `query_memories` 零命中 |
| 5 | 索引自动重建 | `user_erase` 重建 outbox（surviving memories） | ✅ 已删 id 不在重建索引中 |
| 6 | 不可恢复验证（三通道） | 权威/向量/全文三通道扫描 | ✅ `recoverable_channels == []`（一票否决第 5 条通过） |
| 7 | 擦除事件脱敏 | L2 erase 事件 payload 仅 memory_ids + 元数据 | ✅ 不含内容（spec §9.3） |

## 2. 覆盖测试

- `tests/test_erase.py`：6 case（全介质/不可恢复/事件脱敏/确定性/不删史不回归/fail-closed）；
- `tests/test_consent.py`：撤回联动 auto-erase 用例（revoke → 处理停止 + 零残留 + 二次 revoke 拒绝）；
- `tests/test_api.py`：`/rights/delete` 与 `/rights/revoke` 端到端用例。

## 3. 结论

退出-擦除-不可恢复链路在 mock 数据上全链路 exit 0；一票否决第 5 条的自动化断言已固化于 `user_erase`（`EraseReport.ir_recoverable`）。真数据演练待 Pilot 入组后按本记录同口径执行并回填。

## 4. 签署

- 执行：AI GLM 5.3 flash（2026-09-30）
- 复核：Jiang Haipeng（待签，Pilot 期真数据演练后补签）
