# Schema v1
SQLAlchemy metadata creates users/audits/batches/mappings/runs/target_rows. Unique natural names, foreign keys, and target unique(run_id,key_digest) enforce linkage. Successful workers atomically commit accepted target rows; cancelled/failed runs do not persist partial targets. Restore replaces a run's target set under a run row lock and checks the logical backup checksum before commit.

## 交班核对单（handover sheets）
新增四表，均由 SQLAlchemy metadata 自动建立，无外部迁移依赖：

- `system_settings(key unique, value JSON)`：系统级开关。`review_enabled` 记录核对权限是否在授权内，含 enabled/reason/actor/at。
- `handover_sheets`：按批次开的核对单主表，含 status(active/revoked/expired/reclaimed)、current_version、expires_at、revoked_reason、last_revoked_at。
- `handover_sheet_versions`：每次开单或开新版本写入一行不可变 JSON 快照（snapshot/runs_snapshot/targets_snapshot/rejected_snapshot + summary 校验摘要）。`unique(sheet_id, version)`。reclaimed=1 时清空三个载荷列但保留 summary 与翻页凭据。
- `handover_sheet_pages`：续页游标，记录 version_id/section/page/offset/total/next_offset/finished/delivered_key。`unique(version_id, section, page)` 保证并发下页号不重；索引覆盖 (version_id, section)。

并发与一致性：开单/开版本在同一事务读取已提交的批次、运行、目标行、拒绝行并复制为快照，之后新迁移与备份恢复继续落库也不影响旧版本。续页对单据行 `SELECT ... FOR UPDATE` 取锁串行分配游标，锁仅在单次请求事务内持有，不为整单长占事务；唯一约束冲突时整体重试（全新会话 + 指数退避）。游标持久化，进程重启后仍可从下一页续查，重放已交付页不新增游标。

失效语义：撤回核对权限把所有 active 单置为 revoked 并拒绝续页/开版本/新开单，重新授权不复活任何旧单；到期由读路径惰性置为 expired；回收仅允许对非 active 单操作，清空快照载荷后续页返回 version_reclaimed/sheet_reclaimed 并提示重新开单。所有失效在详情接口的 `invalid` 字段与续页 409 响应中给出可读原因。
