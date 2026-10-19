# 回滚剧本 — 按变更类型（S20）

> 通用前置：回滚也是变更——走 CHANGE-MANAGEMENT 分级（回滚通常 C1/C2），触发即建事故档（INCIDENT-LOG 模板）。
> 时长标注为实测/估算；**"上一稳定版" = 部署目录旁 backup 判例（ECS backup-20261016-* 形态）或 git tag**。

---

## R1 · 前端静态产物（Pages / LAN dist）

- 触发：渲染缺陷 / 性能骤降（Lighthouse <90）/ 功能回归。
- 快速回滚：
  1. Pages 形态：`git revert <bad-commit> && git push` → pages.yml 自动重部署（≈3min）。
  2. LAN/NAS：`scp` 上一 tag 的 `build:console` 产物（或 `git checkout v<prev> && pnpm build:console`）→ 覆盖部署目录 → 无需重启（静态直读）。
- 时长：Pages ≈3min / 自托管 ≈5min。
- 验证：e2e 冒烟（auth 401 门 + 路由挂载）+ Lighthouse 一次性跑。
- 数据一致性：无服务端数据；IDB/LS 用户本地态向前兼容（schema 由 hooks 降级契约守）。

## R2 · 服务端部署件（deploy/*.mjs 四件）★高频类型

- 触发：代理/鉴权/静态服务缺陷（如 settings 内容协商类回归）。
- 快速回滚：
  1. `scp deploy/backup 上一版四 mjs`（或 ECS `backup-<ts>/` 目录回拷——L-01 实测形态）；
  2. NAS：`ops.mjs restart`；ECS：`pm2 delete yyc3-console && set -a; . ./console.env; set +a; pm2 start console-server.mjs --name yyc3-console && pm2 save`（判例：restart --update-env 无效）。
- 时长：≈3min/端。
- 验证：八点（L-01 步骤）：401 门/login/settings 双形态/jti/审计流。
- 数据一致性：console-audit.log 只追加不受影响；console-settings.json 用户设置保留。

## R3 · 基线棘轮（color/dup/size/knip JSON 或基线表）

- 触发：基线下调误判 / 门禁误伤正常提交。
- 快速回滚：`git revert` 对应基线提交（JSON/脚本同 revert）。
- 时长：≈2min。
- 验证：对应 check 命令复跑 PASS + 负例探针（调低基线必 FAIL）仍有效。
- 数据一致性：无。**红线**：上调仍禁——回滚只允许回到"下调前"，不允许无证据抬高。

## R4 · 后端网关（YYC3-0379-World 容器）★服务端指标回滚实体

- 触发：BackendErrorRateHigh P1 / RegistryRollbackTriggered P0（自动回滚已发生）/ 模型全失联。
- 快速回滚：
  1. **镜像/代码**：NAS `git checkout <prev-tag>` → `deploy-nas-gateway.sh`（L-13 加固版：--wait+轮询+fail 收口）；
  2. **仅配置**：容器 env 回退 + `docker compose up -d --force-recreate gateway`；
  3. **热更回滚**：RegistryRollbackTriggered 触发即表示网关已自动回滚——值守核对企业+模型 ready 恢复即可。
- 时长：构建+启动 ≈5-10min（L-13 健康收口兜底 120s）。
- 验证：/healthz 200 + /v1/models 列表 + registry ready=1 + Prometheus targets up。
- 数据一致性：**spend_logs/registry 表不回滚**（append-only 流水）；仅配置类回滚。风险：迁移已应用则代码回滚需兼容新 schema（后端迁移纪律：只加不改）。

## R5 · 数据库迁移（core/database/init/*.sql，C4）

- 触发：迁移后网关起不来 / 业务致命。
- 快速回滚：迁移文件**只加不改**纪律下，回滚 = 新增反向迁移（如 008_drop_xxx）而非删 007——**已应用迁移文件永不修改**。
- 时长：视数据量。
- 验证：`scripts/pg-verify-replication.sh` + 网关健康 + 关键表抽查。
- 数据一致性：**最高风险区**——回滚前 dump（pg_dump 相关表）；回滚演练（C4 要求）必须在测试库先行。

## R6 · 全量回滚（灾难级：整版撤回）

- 触发：多域同时回归 / 不可定位复合缺陷。
- 快速回滚：全端回到上一 tag——NAS 仓库 `git reset --hard <tag>`（bundle 通道）+ gateway 脚本重建 + console backup 回拷 + Pages revert push。
- 时长：≈30min（三端并行）。
- 验证：S14 双形态全套 + e2e 13/13。
- 数据一致性：逐项核对（R4/R5 原则）；事故档必建（SEV1）。
