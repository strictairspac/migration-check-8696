# 见山 · 检验结果迁移核对站

见山质量档案组13人用源批次、字段映射、后台对账运行完成旧字段检验结果的有证据交接。

## 场景与业务
上游实验室交付旧字段JSON检验记录；过去人工改字段名、复制到新表并凭总行数判断成功。痛点：非法数值默默丢失、重复委托号覆盖、备份无法证明能恢复。本站登记原始行，字段映射规定类型和必填，Python逐块转换并保留拒绝原行，真实PG目标表一次提交。下游质量复核人下载对账凭据，管理员用JSON逻辑备份恢复本次运行目标并核验。

五业务页：源批次、字段映射、迁移执行（可取消）、差异核对（拒绝区/目标行/备份）、交班核对单（版本冻结与游标续页）；管理员另有审计、回传恢复与核对权限开关。三核心实体batches/mappings/runs，另target_rows持久化目标行，handover_sheets/handover_sheet_versions/handover_sheet_pages/system_settings支撑按批次核对单。全部实体按模型/schema/service/controller/routes/前端api/store/page贯穿。

## 启动与账号
```sh
cp .env.example .env
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
```
前端 http://localhost:18248 ，后端 http://localhost:19248/docs ，PostgreSQL localhost:17748（migrate / migratepass / migrationcheck）。结束docker compose down -v --remove-orphans会清除本地数据。

| 角色 | 账号 | 权限 / 页面 | 典型动作 |
|---|---|---|---|
| admin | admin@migration.local | 全部、审计、恢复 | 回传备份恢复目标并校验 |
| operator | operator@migration.local | 创建/编辑/执行/取消/导出 | 配置映射并迁移 |
| viewer | viewer@migration.local | 只读、下载凭据/备份 | 复核拒绝区和真实目标表 |

密码统一Migrate2026!；PBKDF2密码与8小时JWT。本地演示凭据与JWT密钥，部署前更换。

## 一天的交接剧本
1. 09:00 operator签入，查看见山日班检验结果12条正常记录。
2. 09:05 登记lab-results-20261117.json，委托号JS-20261117-001结果420.1MPa。
3. 09:10 新建shift-20261117批次，复制旧字段。
4. 09:15 字段映射：委托号→sample_code、检测项→test_name、结果→result_value、单位→unit、时间→measured_at，每块4行。
5. 09:20 提交shift-20261117对账，或运行旧字段异常样本查看重复/非法数字/空值/缺列拒绝。
6. 09:25 查看接受/拒绝与分块证据，读取真实PG目标表。
7. 09:30 下载reconciliation-<id>.json与backup-<id>.json，viewer复核。
8. 10:00 admin回传该备份，恢复并核对摘要，查看审计完成事件。

seed含三账号、三批次（三种正常/异常/空输入）、三映射。固定数值、自然键upsert式补缺，不覆盖用户编辑；连续执行不新增。

## 迁移、校验、取消与恢复
字段类型为text/decimal/datetime。decimal使用Decimal精确转换为6位小数字符串，范围±1e9；无穷/NaN拒绝。空值/空串按required隔离（只有unit可非必填）；缺源字段隔离。时间统一UTC，无时区按Asia/Shanghai(+08:00)解释。自然键sample_code+test_name按规范JSON SHA-256计算；同次运行重复键只接受首条合法记录。每行与全部接受行用排序key/紧凑JSON/UTF-8算SHA-256。拒绝行保存原行和原因。

最多2000源行、每行20列、单元格500字符；每块1-500行。逐块更新进度；取消在块间检查，最终提交前锁定run再次检查，成功目标一次提交；取消/异常没有部分目标数据。后台任务使用简单Redis单消费者；进程崩溃可能留下running状态，需人工复核并新建任务，不自动重试。

下载备份为本工具目标行的逻辑JSON快照(version1)，含run_id/rows/row_hashes/checksum，不是pg_dump或物理备份，不含WAL/索引/权限。管理员恢复只允许该运行已保存checksum完全匹配的备份；先核验逐行/总体摘要、schema和自然键，再事务性替换该运行target_rows，回读重新计算摘要并保存recovery记录。篡改、错运行、未完成运行拒绝，恢复事务回滚；不能用任意新数据覆盖目标。

## 交班核对单：版本冻结与游标续页
页面按批次开交班核对单，把"开单时刻"的批次、运行清单、目标行、拒绝行复制为不可变JSON快照（handover_sheet_versions，含逐项checksum摘要）。此后新迁移与备份恢复仍可并发落库，同一张单的任何续页始终读开单时的版本，不被后写数据改变；需要纳入最新落库时显式"开新版本"，旧版本快照仍完整保留。

续页分区为 runs（已完成运行）/targets（目标行）/rejected（拒绝行）。游标持久化在 handover_sheet_pages：按 (version_id, section, page) 唯一约束 + 单据行锁 `FOR UPDATE` 串行分配，计数与翻页不漏不重；锁只在单次请求事务内持有，无须为整单长占事务。每个信封返回 page/offset/next_offset/total/count/finished/delivered_key。重放已交付页（带 page 参数）返回原内容且不新增游标；跳页返回409并给出应续页码；读完后再请求为幂等完成态。游标落库，进程重启后仍可从下一页续查。

失效与回收：
- 管理员在"核对权限"开关撤回后，所有生效单立即置为 revoked，续页/开版本/新开单一律拒绝；重新授权只允许开新单，不复活任何旧单。
- 单据到期（默认240分钟，可5-1440）由读路径惰性置为 expired，续页返回409与到期时间。
- 到期或撤回后管理员可回收旧版本：清空快照载荷但保留摘要与翻页凭据；并发续页要么在回收前读全，要么收到 version_reclaimed/sheet_reclaimed 并提示重新开单，不会读到半份数据。
- 详情接口的 `invalid` 字段与续页409响应都带 code/message，页面据此渲染失效横幅与重开指引，页面始终可续查或说明失效原因。

接口（均需JWT）：`GET/POST /sheets`、`GET /sheets/{id}`、`POST /sheets/{id}/versions`、`GET /sheets/{id}/pages/{section}?page_size=&page=`、`POST /sheets/{id}/reclaim`（管理员）、`GET/PUT /review/permission`（PUT仅管理员）。开单/开版本需 operator 或 admin；观察员只读与续页。


受控场景演示旧字段到新目标结构的逻辑迁移，数据库真实保存源/映射/目标/对账。不能连接远端数据库，不宣称生产异构迁移或灾备能力。

## 工程与开发
Python3.11/FastAPI/SQLAlchemy/psycopg/Redis/PostgreSQL16，原生HTML/CSS/JS，nginx1.27。exact五服务frontend/backend/worker/db/redis均healthcheck，数据库/Redis/共享产物命名卷；依赖健康后启动。请求追踪、全局错误、JWT授权和业务审计横切。

backend/src按models/schemas/services/controllers/routes/middlewares/config/constants/utils；backend/scripts/seed_demo.py；backend/migrations记录元数据版本。frontend/src按api/stores/pages/components/common/hooks/router/types/constants/utils；共享table/status/feedback；forms/poll hooks。角色/状态/类型枚举在backend/src/constants/enums.py与frontend/src/constants/enums.js。墨绿邮政凭单视觉，Noto Sans SC/Space Mono双字体来自Google Fonts，离线回退；桌面/平板/手机响应。

.env.example定义COMPOSE_PROJECT_NAME/三端口/JWT_SECRET/SEED_DEMO；DATABASE_URL/REDIS_URL由Compose注入。启动SEED_DEMO失败只记日志。本地开发pip install -r backend/requirements.txt，设数据库/Redis/JWT环境变量，在backend运行uvicorn src.main:app --reload；前端需/api代理，不能file://。测试/截图/日志放批次test-artifacts/gb-4109，源码不混入。MIT License。
