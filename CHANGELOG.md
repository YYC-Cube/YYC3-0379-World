---
file: CHANGELOG.md
description: YYC³ 0379-world 项目版本变更日志
author: YanYuCloudCube Team <admin@0379.email>
version: v1.1.0
created: 2026-04-04
updated: 2026-09-23
status: active
tags: [changelog],[version],[history]
category: project
language: zh-CN
---

> ***YanYuCloudCube***
> *言启象限 | 语枢未来*
> ***Words Initiate Quadrants, Language Serves as Core for Future***
> *万象归元于云枢 | 深栈智启新纪元*
> ***All things converge in cloud pivot; Deep stacks ignite a new era of intelligence***

---

# 变更日志 (Changelog)

本文档记录 YYC³ 0379-world 项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [Unreleased] - 待发布

### 修复 (Fixed)

- 🐛 CI 全红修复：dependabot 自动合并的 `numpy>=2.5.3` 需 Python≥3.12，与 CI/生产基础镜像 `python:3.11` 冲突（lint job 装依赖即失败，NAS 生产 rebuild 同因必挂）→ 回调兼容区间 `numpy>=1.26.4,<2.5`，py3.11/3.12 双端 dry-run 解析实证通过
- 🐛 dependabot.yml 增加 numpy ignore 规则（`>=2.5`）：升级须与基础镜像升 3.12 作为同一显式变更执行，防自动合并复发
- 🐛 CI integration 建表三段式重构：① 建表步骤经 tests/conftest.py 注册 app 包后调 `init_db()`（app 包系 importlib 手工映射，裸 sys.path 必挂 ModuleNotFoundError）；② ORM 基础 7 表 + 002–006 init SQL 幂等增量（补齐 virtual_keys/spend_logs/task_prices/model_aliases 与 model_registry 扩展列，对齐 NAS 生产「ORM 先建、SQL 增量」惯例）；③ PG service 镜像换 `pgvector/pgvector:pg15` + 目标库显式 `CREATE EXTENSION vector`（原 postgres:15-alpine 无 pgvector，`Vector(1536)` 列建表即挂）；④ 预建 yanyu 角色（002 GRANT 依赖）+ 002 种子 INSERT 包 DO 块防御（ORM 先建表场景 NOTICE 跳过，生产空库路径不变）
- 🐛 CI test job 移除遗留 `AUTH_ENABLED="false"`（76e6690 起）：RBAC 用例（pricing_admin 403）依赖鉴权开启，用例自带正确 key header；本地 `-m integration` 全量 218 passed 实证（10.5min）
- 🐛 CI test job 补装 `aiosqlite==0.22.1`：Registry 三测试文件的 sqlite 内存库 fixture 依赖（requirements.txt 不含，本地 .venv 历史安装掩盖）；上一 run 已 341 passed，53 errors 全为该缺位
- 🔧 CI deploy 冒烟 401 主因修复：GitHub `PROD_API_KEY` secret 与生产失同步（疑 9-26 网关密钥轮换遗留）→ 以 NAS 网关 `.env` API_KEYS 为源公网验证 200 后同步（管道传入不落日志）；main 近 100 run 无 success 的历史遗留开始收敛
- 🔒 main 分支保护生效（required checks：代码质量检查/单元测试/安全扫描/构建镜像）：dependabot 红 PR 自动落 main 的根源封死；admin 应急直推通道保留（enforce_admins=false）
- 🚀 旗舰 DeepSeek-V4-Flash 恢复（停摆 5 天 → 四绿）：A 预案执行——8B rerank 退役 + 双机 TP=2 重建 + 孤儿清障（emb8b/0.6B reranker 三重实证零引用后停用）；启动参数 `--enforce-eager`（NVRM CUDA graphics context OOM 实锤）+ `--max-model-len 65536→32768`（UMA profiling 峰值减半），双备份可回滚；终验 health 200 / 契约 healthy / 公网对话 `x-yyc3-upstream: flagship-dsv4`
- 🔧 方案 a 破稳定性循环：旗舰交付后 ~40min 复燃（N2 就绪态仅余 8G、崩溃周期实测 ~20min）→ 停用 `yyc3-asr`（8.6G，禁自启，一键回滚脚本 N2:/home/yyc3/asr_rollback.sh）→ 稳态余量 17G，DeepGEMM warmup 首次 100%，health/推理/公网复验全绿

### 新增 (Added)

- 🆕 pytest 分层体系（P1-1）：默认快速回归层 `-m "not integration"`（34 用例 ~1.6s）；`make test-fast` / `make test-integration` / `make test`（全量）三目标；CI 按事件分层分发（PR 快速层 / main 全量）
- 🆕 三云适配器 + ollama 全链路测试套件 `tests/test_cloud_adapters_fullpath.py`（15 用例：同步/流式 × 参数化、reasoning 折叠、错误分支、主备切换、全塔断路、host 归一）
- 🆕 pytest.ini 注册 `fast` marker，`integration` marker 语义明确化
- 🆕 CI release job（P2-4）：tag 推送 → 版本一致性门禁（tag ↔ CHANGELOG 定版段 ↔ README 徽章三方对齐）→ ReleaseNotes 自动提取 → GitHub Release（tag 含 `-` 自动 prerelease）
- 🆕 docs 内链检查器 `core/scripts/check_doc_links.py`（P2-5）：markdown 相对链接→文件存在性静态检查，进 CI lint job 正式门禁
- 🆕 ADMIN_API_KEYS 分离语义测试 `tests/test_admin_key_separation.py`（P2-6，6 用例：回退/互斥/容错/模板锚）
- 🆕 API认证使用指南「管理面密钥分离」章节：语义契约 + 生产 runbook + 90 天轮换策略
- 🆕 ADMIN_API_KEYS 生产验证脚本 `core/scripts/verify_admin_keys.sh`（三连验证一键化：403/200/200 + 精准处置提示）
- 🆕 生产 .env 写入示例命令固化：API认证使用指南 runbook 升级四步可复制（生成/幂等写入/滚动生效/三连验证）+ 轮换与回滚段
- 🆕 A2A 通信协议层 `core/api/services/a2a_protocol.py`：Redis Stream 消费者组原语（ensure_group BUSYGROUP 幂等 / poll_messages 非阻塞修正 / send_task/result / nack+DLQ / XAUTOCLAIM claim_stale_messages 兼容 2·3 元响应）
- 🆕 外置 Agent Worker 装配 `core/api/services/agent_workers.py` + 独立进程入口 `core/scripts/agent_worker.py`（A2A_ENABLED × AGENT_WORKER_ENABLED 双控；3 Agent 单机装配）
- 🆕 A2A 投递端点 `POST /v1/agent/a2a/tasks` + 同步闭环端点 `POST /v1/agent/a2a/tasks/sync`（注册聚合器 → 投递 → drain 追平 → wait_one 等齐，超时不丢任务）
- 🆕 ResultHub 结果流消费端 `core/api/services/a2a_result.py`：sender 覆盖式幂等聚合 + asyncio.Event 事件驱动 wait_one/wait_all + XAUTOCLAIM 挂起回收（60s 空闲阈值 / 30s 扫描）+ 孤儿回执审计
- 🆕 多 Agent 编排端点 `POST /v1/agent/a2a/orchestrate`：capability 在线 Agent 全量扇出 + wait_all 等齐（completed/partial/timeout + 部分 results）
- 🆕 vk（虚拟密钥）计费门控接入 `/v1/agent/**`：三端点内联门控（白名单 403 / 预算 402 / TPM 429，task_type 作 model 语义）+ 中间件协同事务记账（X-A2A-Cost > X-Total-Cost 双探针 + 兜底 0.001 USD，请求内 await 落队）
- 🆕 A2A 可观测面 `core/api/services/a2a_metrics.py`：孤儿/回收/死信 Counter + DLQ 深度/结果流堆积/双端 PEL Gauge（XAUTOCLAIM dryrun 只读采集，30s 周期随消费端生命周期）+ Grafana `a2a-observability` 七面板（堆积阈值 500/2000 告警配色）
- 🆕 A2A 审计流 Loki 消费端 `core/api/services/a2a_audit.py`：stream:audit:log → Loki 批量推送（labels job=a2a-audit/event/agent，推送成功才 XACK，抖动退避）；A2A_ENABLED × A2A_AUDIT_LOKI_ENABLED 双控；Grafana Loki 数据源 provisioning 补齐 + 告警规则三条（死信/孤儿/回收停滞）
- 🆕 A2A 成本直报：pricing.py 任务类型固定定价表 TASK_TYPE_PRICES + task_cost()；三端点回填 X-A2A-Cost 响应头（编排=单价×扇出数），中间件记账双探针优先取直报值
- 🆕 A2A Worker 扩面：格物·宗师（content_validation/code_review）+ 演启·乾行（content_formatting）入编，编队 3→5；A2A_WORKER_AGENTS 配置化部署
- 🆕 协同事务价格表管理端点：GET/PUT `/v1/admin/pricing/task-types`（TASK_TYPE_PRICES 运行时覆盖，负价 422 / 未知类型预置 / RBAC）
- 🆕 编排器独立部署面：`core/scripts/orchestrator.py`（--consumer/--no-metrics/--with-audit）+ compose `orchestrator` profile；内嵌/独立/混合三形态
- 🆕 生产灰度修复：compose grafana 挂载 provisioning（数据源/告警/仪表盘随启动加载）+ Loki local-config 补建（原挂载目标缺失）+ 灰度验证脚本（Redis→shipper→Loki 端到端 + Grafana 告警联系人路由绑定，实环境三连全通）
- 🆕 NAS 生产栈全套灰度：nas compose 补 agent-worker（5 编队）+ orchestrator profile + 网关 A2A 全 env（A2A_AUDIT_LOKI_ENABLED 缺省开闸）；监控 compose 补 Loki（named volume）；容器入口 app.worker_entry / app.orchestrator_entry；deploy 脚本补 core/agents 同步 + NAS 布局 Dockerfile（修复部署链断点：Worker 依赖原先不在部署目录）
- 🆕 协同事务价格表 PG 持久化：004_task_prices.sql 迁移 + load_task_prices_from_db 启动加载（表覆盖内存）+ upsert_task_price_persisted 双写（DB 不可达降级仅内存，响应 persisted 标志）
- 🆕 A2A 开放 API 契约：docs/架构与部署/A2A开放API契约.md（端点/认证/计费/错误码/可靠性语义）+ 三端点 OpenAPI tags/summary/description
- 🆕 A2A 测试体系 `tests/test_a2a_{protocol,worker,result}.py`（68 integration 用例）+ conftest 顶层统一密钥注入（收集顺序加固：测试文件只读不写，合跑 9 failed → 全绿）
- 🆕 Bearer OpenAI 生态兼容：`Authorization: Bearer <sk-*/vk-*>` 按 API Key 链认证（JWT 三段式无前缀零冲突），解锁 OpenAI SDK 标准 Bearer 姿势接入 vk 计费链；`tests/test_auth_bearer_compat.py` 5 用例
- 🆕 NAS 数据库拓扑对齐（2026-09-27）：OPS-RECOVERY 新增数据库拓扑节（kb 主库 :5434 / 家族备库 :5433 只读 / PG14 退役 / 系统 PG13 勿连红线）+ 系统上下文/变量清单/设备全量信息三文档同步
- 🆕 模型接入规范文档体系整合：原两份平行规范（模型接入 v2.3.0 / Agent 注册 MRS-2026，重复 40% 且细节冲突）拆分为 `docs/模型接入与注册/` 六文档——现状基线（01）/Registry 目标架构（02）/热切换版本管理（03）/Agent 注册（04，A2A 生产契约消除双轨）/监控 Runbook（05）+ README 索引（实现状态总览表）；四处幽灵脚本显式标注规划、统一设备命名/心跳 TTL/元数据载体口径；原文档归档 `docs/archive/`
- 🆕 模型注册中心（Registry）Phase A MVP：005 迁移五表（存量 model_registry 增量列 + model_versions/model_heartbeats/model_events/model_audit_log，TEXT 存 JSON 防 asyncpg 绑定坑）+ `services/model_registry_svc.py`（幂等 CRUD/版本回滚防盲滚/心跳 TTL 三级阶梯 90s→180s→300s/事件 PG+Redis 双投递/审计）+ `api/model_registry.py` 12 端点（含 SSE 事件流先回放再订阅防漏）+ `upstream_registry.merge_registry_upstreams()` 双通道合并（registry-{model_id} 命名隔离 env 兜底，REGISTRY_ENABLED 灰度开关默认 false）
- 🆕 A2A Agent 注册演进层：GET `/v1/admin/a2a/agents`（全量含离线+在线计数）/ PATCH `{id}`（tools/timeout_seconds/限流白名单扩展元数据）/ DELETE `{id}`（注销），均入审计流；内置编队自愈语义文档化（停用走 A2A_WORKER_AGENTS env）
- 🆕 模型资产工具链：`core/scripts/model_asset_verify.py`（分片对账/safetensors 头部 magic/配置存在性三校验 + model_checksum.report 落盘 + CLI 退出码语义）+ `core/scripts/model_sync_to_node.py`（rsync 断点续传/--dry-run/--plan 增量计划/残片续传检测/同步后分片对账门禁）
- 🆕 Registry/演进层测试 59 用例（快层 21 + integration 38）：svc 15（CRUD/幂等/回滚/心跳 TTL 阶梯/sqlite-UTC 时区归一）+ API 14（12 端点/RBAC 403/灰度 503/幂等）+ a2a admin 10（列表/PATCH/DELETE/审计/白名单）+ 脚本 20
- 🆕 Registry 生产灰度开闸（2026-09-28，NAS 生产十连验证全通）：005 迁移上网关栈 PG + REGISTRY_ENABLED=true；双通道合并生产实证（探针上游入路由池）；两项生产修复——nas compose 补 REGISTRY_ENABLED env 传递（b2c0c2d）、enabled 列 PG boolean 参数化（fac630a，sqlite=1 习惯在 PG 报 UndefinedFunctionError）；OPS-RECOVERY cron 锚定实测定论（全 NAS 无 cron 挂载，两脚本为手动触发范式）
- 🆕 五生产上游双写 Registry 入中心（2026-09-28 TOP1）：dsv4/embedding/rerank/asr/ocr 注册 ready（node_id 对齐 yyc3-101/102）——startup merge 合并 5，路由池 12 上游同池（registry 5 + env 7，priority 5 零切换零风险）；Phase A 手动模式定型（不发心跳免 TTL 衰减，语义入 svc docstring）；README/.env.example 生产态对齐
- 🆕 注册 Agent + Phase B 事件驱动增量合并（2026-09-28 TOP2/TOP3，cffd3cd）：`model_register_agent.py`（stdlib 零依赖：就绪探测/注册/ready/30s 心跳/优雅 offline，TTL 300s 兜底）；svc pub/sub 消费者（`yyc3:registry:events` 驱动运行时入池/定点摘除，**生产免重启四态闭环实证**）；修 merge 全量对账缺口（registry-* 陈旧条目随重合并清池）；变量清单新增「网关应用变量」节；N1:8001 502 定论（dsv4-head 僵尸容器，Ray 宿主 OOM 杀 TP worker 09-26 23:54，建议 restart + OOM 缓解）
- 🆕 下轮 TOP3 全闭环（2026-09-28，513aab7/4c1e649）：dsv4-head 重启恢复（:8001 200，网关旗舰 502→200；OOM 实勘 mem_limit=0 + recreate 建议）；`model_smoke_test.py` 九用例冒烟（生产首验旗舰 8/8 + embedding 9/9，能力面感知修复）——**规范附录 A 规划项全部落地清零**；五服务注册 Agent 实拉起（101×3+102×2 常驻，心跳 2.7~4.0s，TTL 自愈语义激活，dsv4 agent 自动跟随引擎恢复零人工）
- 🆕 稳态期 TOP3 + 自愈固化（2026-09-28，7946f76/5d412fd）：systemd 双模板常驻（root/user 版入库，101 enabled×3 + 102 user×2）；dsv4-head OOM recreate（RAY_memory_usage_threshold=0.95 + mem_reservation 100g，原 mem_limit=0）；canary 实勘定论 alpine 空壳退役；心跳观测（Gauge×2 入 Prometheus 20 series + 断流翻转 warning 入 Loki）；🚨 pkill 竞态事故复盘 → `heartbeat()` 自愈回升 offline→ready（draining 除外）+ 事件驱动 Phase B 重合并——生产全链自动复原实证（回升→3→4→5 入池→chat 200）
- 🆕 稳态收尾：观测告警 + 运维资产（2026-09-28）：Prometheus 三告警规则（HeartbeatStale 120s/ReadyLost/MetricsGap）部署 NAS volume + 热重载加载实证 + 入库 deploy/nas/prometheus-rules/；canary 终局（dsv4-head-canary + canary-plain 双 rm，canary-gpu 保留有据）；日志轮转双模板（101 logrotate.d / 102 crontab+state）入库 deploy/nodes/；102 linger 无远程提权路径待用户一条命令（sudo loginctl enable-linger）
- 🆕 Phase C 热切换落地（2026-09-28，05635b0，规范 03 §3 唯一未实施面）：`model_aliases` 表（006 迁移）+ 内存路由表 `_alias_cache`（startup 预热 + 本进程直更 + `alias_switched`/`alias_deleted` 事件跨进程刷新三路一致）+ `resolve_alias` 网关首行零开销解析（VK 白名单仍校验公网名，权限面与路由面分离）+ `/registry/v1/aliases` GET/PUT/DELETE 与 `POST /models/{id}/drain` 四端点（admin + 503 灰度闸门）+ `set_alias` ready 防呆（仅 ready 可接别名流量）+ `drain_model` 幂等排空观测（既有机制零新代码接线：registry_upstreams 仅收 ready + 心跳自愈不覆盖 draining）；测试 svc 29（含 §3.5 五步切换+回滚全链路单测）+ api 19 全绿；NAS 生产十步灰度演练全实证（切流 200/免重启切指/drain 摘池零流量影响/422 防呆/回滚闭环，审计 6 条留痕，零回滚）；规范 03 v1.1.0 + 体系 README v1.2.0 状态回写——模型接入与注册体系 A→B→C 全周期收官
- 🆕 P1 RAG 混合检索深化·rerank 精排层（2026-09-28，4bd62df/925b805）：`services/rerank_svc.py`（Qwen3-Reranker 生成式打分：judge 三段式模板 + completions logprobs 取 yes 概率；复用上游池 capability 路由/降级链/熔断/模型改写；与 proxy /v1/rerank 解耦——对外 vk 记账走 proxy，内部检索重排零 HTTP 自调）+ ops_rag v1.1.0 挂 rerank 钩子（候选池 ≤top_k×4 重排，分数语义 rerank>RRF>向量，失败自动降级原序）+ /v1/rag/ops rerank 参数；生产对照实证（rerank by rerank-n1，Top1 更换 + yes 概率分数）；测试 rerank_svc 11 用例 + test_ops_rag NAS 版收编入库 + rerank 5 用例（快层 159/integration 71 全绿）
- 🩹 P1 同场三项生产修复（2026-09-28）：① ops_rag 出站端点 7 处 `10.100.168.1`（N1↔N2 背对背 mtu9000 网段，NAS 网关经路由器不可达、生产首调 500）→ N2 tailscale `100.76.167.103`（925b805）；② N2 三服务恢复（yyc3-reranker/yyc3-embedding Exited(137) 三周 + yyc3-chroma 僵死 8 天，docker start/restart，reranker 打分实测通）；③ importlinter 架构红线清偿（model_registry.py R-11/R-12 裸 SQL+app.db 直连下沉 svc：get_manifest_by_hash/list_audit_logs；四条 api→services 传递闭包豁免 → 3 kept 0 broken，遗留 CI 红一并转绿）
- 🆕 P1 下轮 TOP3 全闭环（2026-09-28，3c01591）：golden set v3 40 题固化（v2 未存档按 chroma main 库 373 唯一对重建，前缀匹配）+ ops_rag_eval.py 零依赖四配置跑批器 + 4 用例——**main 库 8B 量化：vec 67.5% → rerank 75.0%（+7.5pp/相对 +11.1%），hybrid 语义型负载零增益**；8B 嵌入根因定论（原 nohup 形态 09-19 宿主重启失联→三 8B 库恒降级）并容器化常驻（yyc3-emb8b :8103 + docker-compose-rag.yml v1.1.0 embedding-8b 服务 + emb8b_entry.sh UMA 补丁入口入库）；Exited(137) 定论=人工 docker stop（非 OOM 非崩溃，unless-stopped 本就配置）；yyc3-102 linger 补全（sudo -n NOPASSWD 修正前轮结论，双用户 Linger=yes）
- 🆕 P1 深化二轮：语料治理 + 8B 重排定产 + golden v4 终评（2026-09-28）：① DGX 双版去重（新版 13 chunks 标题复刻旧版衍生物，chroma v2 delete 430→417 + N2 全量备份回滚件 + BM25 reindex 同步）→ 40 题 vec 70.0%/rerank 80.0%；② Qwen3-Reranker-8B 容器化上探（:8104，KV 教训：8192+util0.15 KV 剩 0.86G<需 1.12G 必挂 → 4096+0.16；去 --runner pooling 保 /v1/completions 生成式打分兼容）——**同题对照 8B 74.0% vs 0.6b 54.0%（+20pp，0.6b 负收益）→ 生产池终态 rerank-n2-8b prio=1**；③ golden v4 100 题（+60 覆盖 AI-Family/高可用API/DEVICE/资产/NemoClaw 等）终评：vec 65.0 / hybrid 61.0（负收益 -4pp，两轮无增益判裁撤候选）/ **rerank-8B 74.0（+9pp）**——生产定案 `{"library":"main","rerank":true}`，相对 09-27 基线 55%→**74%（+19pp）**
- 🆕 P1 深化三轮：hybrid 负收益根因三修 + 时延实验定案 + 会话语料摘除（2026-09-28）：① 归因（逐题 diff 退步10/恢复6）——rrf_fuse 同 key 多 chunk 占 N rank 位逐位累加灌分霸榜（19-chunk 重复标题吞 5 题，主因）+ BM25 索引无 heading + 中文单字歧义；三修（ops_rag v1.2.0）：RRF 同 key 首现去重（duplicate_key_no_stuffing 回归护栏）+_index_text heading 前置 +_tokenize CJK bigram——**hybrid 61.0→81.0%（+20pp，276ms 零时延）登顶四配置，生产定案改 `hybrid=true`（rerank 降备选），P1 全程 55%→81%（+26pp）**；② CUDA graph 时延实验：0.16 下 graph 捕获吞 KV 必挂 → 0.20 成功但仅 ~4% 提升判无价值（瓶颈=prefill 总量）→ 保持 eager 定案入档；③ 会话文档 23 chunks 摘除（417→394）+ reindex + N2 回滚件
- 🆕 P1 终局 + P3 用量报表（2026-09-28）：① 19 miss 拆解——8 题为评测器伪失（emoji/「YYC³ 」/「使用 」装饰前缀致 startswith 误判）→ eval v4.1（is_hit 去 emoji+contains，护栏×3）；真 miss 主因 AI-Family 档案/创新范式双目录全量重复（55 标题 100% 子集）→ 去重 76 chunks（394→318）——**终评 vec 73.0/hybrid 89.0（+8）/rerank 85.0，P1 全程 55%→89%（+34pp）**；② 语料准入黑名单（ops_rag v1.2.1）：会话文档三件精确名单（勿 ^0\d- 模式防误伤 golden 目标）reindex+查询双口径拦截；③ P3 用量报表新主线：`GET /v1/admin/usage/summary`（usage_summary svc 分组列白名单字典取值零拼接 + NULL 容错 + admin RBAC 闸门 + 非法 422；6 用例，快层 170）——NAS 生产实测真实数据回放，计费链「账可算可看」收官
- 🆕 契约端点与看板化（2026-09-28，e757153）——11 报告 P1/P2/P3 三主线全收官：① ops_rag v1.3.0 候选池双通道 key 去重（同 source::heading 只占 1 slot + BM25 源扩 ×8；NIM 兄弟取证 overlap 3/9 非子集不删）→ hybrid 89→**90.0%（P1 全程 55→90，+35pp 平台期）**；🚨 同场摁出并修复静默降级缺陷（v1.3.1）：rebuild 容器 data 非持久卷致 BM25 索引丢失，hybrid 无提示退化纯向量（评测险误判）→ 索引不可用 notes 显式留痕 + reindex 指引；② register_agent v1.1.0 契约端点（规范 02 §2）：`--contract-port` 内嵌 stdlib 契约服务 `/v1/model/{metadata,capabilities,health}`（注册元数据同源直出/capabilities>model_type 降级链/health 实时探测）——102 双试点（asr@9101/minicpm@9102 systemd drop-in）三端点全通 + NAS 跨节点实证，+5 ephemeral 用例；③ admin_ui 全局用量区块（分组下拉 fetch usage/summary，账单面可视化）。快层 176（+6）
- 🩹 #problems 双文件类型清零（2026-09-29，d5a9d5，basedpyright 全库归零）：mcp_client 5 错（build_mcp_command 注解 List[str]→Tuple 实为注解错连锁误报/未用形参下划线化/tool_descriptions 值域 Any/LocalMCPManager Optional）+ virtual_key_manager 3 错（RPOP isinstance 收窄/rowcount getattr 兼容桩缺口/secrets+uuid import 移头部 E402 债清偿）——全部运行时零行为变更；门禁 lint+importlinter 3 kept+快层 176+vk/auth/rbac integration 12+NAS 三端点冒烟 200；同场第三次实证 rebuild 索引丢失（v1.3.1 留痕机制生效捕获），已 reindex 恢复，根治列升温 TOP3#1
- 🆕 升温 TOP3：索引持久化 + 契约全网 + 平台期固化（2026-09-29）：① nas compose gateway 挂 gateway-data:/app/data 命名卷——**二次 rebuild 实证 BM25 索引跨重建存活（`hybrid:True|notes:[]`），三丢问题根治摘牌**；② 101 契约端口补齐（dsv4=9103/embedding=9104/reranker=9105 drop-in，五服务全网覆盖 + 模板入库 deploy/nodes/ + README 状态表 📋→✅）；③ 四配置复测：hybrid 90.0 稳定复现，**hybrid+rerank 90.0 持平（rerank 零增量，平台期固化）**；④ 🚨 契约端点首个生产捕获——旗舰 TP=2 昨日 OOM 下线 13h（N2 拉双 8B 窗口 UMA 挤压杀 Ray worker → restarts=99 loop → ray session 失配 GPU 不上报），处置=worker 容器 rm+run 重建（清 session；--entrypoint bash 坑）+ head 协同重启，终验移交下轮

### 变更 (Changed)

- 🔄 AuthMiddleware `_authenticate` api_key 分支提取 `_authenticate_vk_or_static` 类方法（vk 校验链优先、静态/管理键降级语义不变；可测试打桩）
- 🔄 CI 六 job 补 `timeout-minutes`（lint 10 / test 25 / security 10 / build 30 / deploy 15 / release 10），防 runner 挂死空转
- 🔄 test_gateway_api / test_admin_rbac / test_proxy_api 三文件标记 `integration`（TestClient 全链路归集成层，语义不变）
- 🔄 CI test job 分层：`pull_request` 且非目标 main 时跑快速层；push/PR→main 跑全量
- 🔄 CI 触发器补 `tags: ["v*.*.*"]`

### 修复 (Fixed)

- 🔧 生产 403 遗留定案（下轮 TOP1）：根因 = API Key 走 `Authorization: Bearer` 头被按 JWT 解析必然失败（键值无误、中间件静态链完好，X-API-Key 实测 200）+ `virtual_keys` 表 0 行（vk 链无键可命中）；由 Bearer 兼容增强修复
- 🔧 vk 创建/更新 PG 全阻修复：`model_whitelist` JSON 串误绑 `TEXT[]` 列（asyncpg DataError）→ PG 方言直绑 list、sqlite 兜底保持 JSON 串；`tests/test_vk_whitelist_bind.py` 3 用例回归锚
- 🔧 vk 记账完整性修复：`_flush_batch` 补 `virtual_keys.spent_usd` 增量 UPDATE（原仅 INSERT+内存同步，重启后预算闸门从 PG 读旧值失守；docstring 与实现对齐）
- 🔧 `yyc3_db_backup.sh` PG14 备份链路拆除（原 127.0.0.1:5432 现为系统 PG13，勿动勿连红线——防误连）
- 🔧 `setup-macmax-replica.sh` 退役标注（源端 NAS Docker PG :54320 已随 PG14 下线，现行家族备库 NAS:5433 就位）
- 🔧 `redis.exceptions.ResponseError` 改 `from redis.exceptions import ResponseError` 直接导入（test_a2a_worker / test_a2a_result 两处；消除 IDE 类型桩「exceptions 不是 redis 已知属性」误报）
- 🔧 覆盖率缺口补齐：deepseek 24→87% / openai 27→83% / ollama 53→84% / zhipu 13→86% / key_guard 30→100%
- 🔧 README 版本徽章漂移修复（v9 提交意外回退 v2.2.0 → 恢复 v2.3.0，由 release 门禁逻辑在验证时发现）
- 🔧 存量死链修复 32 处：core/README 幽灵架构文档链重指 SSOT 真身；操作指南三文件"相关文档"段四机时代旧链重写；验收系统两文档旧目录名修正；MCP README 四处 BigModel 死链降级；.env.0379-world 两文档根级幽灵链重写

### 移除 (Removed)

- 🗑️ core/scripts 旧本地模型路线 5 文件：cogagent_chat.py / cogvideox_generator.py / deploy-cogvideox.sh / test-local-models.py / update-model-configs.sql（全仓零引用；推理已 DGX 化）
- 🗑️ 变量清单 MODEL_COGAGENT_*/ MODEL_COGVIDEOX_* 环境变量 6 行（消费者已删）

---

## [2.3.0] - 2026-09-23

### 新增 (Added)

- 🆕 流式 SSE chunk 级 PII 脱敏（carry 缓冲拼接跨 chunk 截断 PII，流末 flush 滞缓冲）
- 🆕 vk 管理看板与 Playwright 真浏览器 e2e 基建（chromium channel=chrome）
- 🆕 三层防御体系：vk 403 / 预算 402 / TPM 429
- 🆕 错误重试测试套件 `tests/test_error_retry.py`（6 用例，含零空转断言）
- 🆕 三云适配器 Key 校验参数化矩阵（`_CLOUD_ADAPTERS` 表驱动，断言面=声明面）
- 🆕 IDE 导入解析三件套：`pyrightconfig.json` + 根级 `app` symlink + `.markdownlint.json`
- 🆕 Redis 从节点部署 (yyc3-45:6399)，避开系统 Redis 6379
- 🆕 CodeGeeX4 Agent 实现 (`agents/yyc3_code_agent.py`，唯一真源)

### 变更 (Changed)

- 🔄 ZHIPU/DeepSeek/OpenAI 三云适配器 Key 前置校验同构化（`ensure_api_key` 公共件落位 `app/errors/key_guard.py`）
- 🔄 DeepSeek/OpenAI Key 从模块级快照改为延迟读取（运行时热加载）
- 🔄 4xx 确定性失败跳过重试（`ErrorHandler._is_retryable`，终结空转重试）
- 🔄 ZHIPU 同步入口接入 `_ensure_key()`（空 Key 401 明确报错，替代模糊 502）
- 🔄 Gateway 容器 (NAS) 配置修正：DB_HOST/REDIS_HOST/HOST_IP 指向正确地址
- 🔄 Gateway 健康检查从 `curl` 改为 `python3 urllib`（容器内无 curl）
- 🔄 Gateway 重启策略从 `unless-stopped` 改为 `no`（防止无限重启崩溃系统）

### 修复 (Fixed)

- 🔧 **P0 致命**: 修复 Gateway 容器 `unhealthy` → `healthy`
  - 根因：DB_HOST=127.0.0.1 导致启动失败 + restart 无限循环 → 系统崩溃
  - 方案：修正环境变量指向实际服务地址，禁用自动重启
- 🔧 **P0 致命**: Redis 从节点端口冲突解决
  - 根因：Docker Redis 映射 6379 与 NAS 系统 Redis 冲突（TANS/TOS 缓存）
  - 方案：使用端口 6399 避开系统服务，建立主从复制
- 🔧 确认 NAS 系统服务安全：Redis(6379) / PG13(5032) 未受任何干扰
- 🔧 OBS-1 空转重试：401 等 4xx 确定性失败不再消耗 3 轮重试（耗时 <0.5s）
- 🔧 OBS-2 DeepSeek 空 Key 模糊 502 → 401 明确报错；OpenAI 无校验 → 补齐前置校验
- 🔧 移除重复 agent 副本 `core/scripts/yyc3_code_agent.py`（lint 清理旧版，零外部引用）

---

## [2.2.0] - 2026-09-14

### 新增 (Added)

- 🆕 DGX 双机 TP=2 公网三能力（chat/embeddings/rerank）全绿
- 🆕 上游池 env 化（`OPENAI_COMPATIBLE_UPSTREAMS`）+ 熔断降级
- 🆕 CI 五段流水线 + 四层冒烟保障
- 🆕 文档体系 SSOT 对齐（架构/部署/CI-CD/前端设计三合一）
- 🆕 生产域名 `https://api.0379.world`（ECS Traefik 边缘 → NAS 网关:8000）

### 变更 (Changed)

- 🔄 响应头 `X-YYC3-Upstream` 契约落地

---

## [2.1.0] - 2026-07-10

### 安全 (Security)

- 🔒 消除全部硬编码密钥，统一环境变量配置
- 🔒 `docs/` 敏感遗留清理

---

## [2.0.0] - 2026-04-08

### 新增 (Added)

- 🆕 自适应路由引擎（EWMA 动态权重）
- 🆕 RAG 知识库
- 🆕 MCP 工具集成

---

## [1.0.0] - 2026-04-04

### 新增 (Added)

#### 核心功能

- ✅ FastAPI 应用框架搭建
- ✅ PostgreSQL 数据库集成
- ✅ Redis 缓存服务集成
- ✅ API 网关服务
- ✅ 多模型 AI 服务集成（OpenAI、智谱 AI、Ollama）
- ✅ MCP 工具集成
- ✅ Prometheus + Grafana 监控系统

#### API 服务

- ✅ CloudPivot Matrix API 服务（端口 3118）
- ✅ CloudPivot Matrix WebSocket 服务（端口 3113）
- ✅ YYC³ AIFY 服务（端口 3200）
- ✅ YYC³ MCP 服务（端口 3203）

#### 数据库

- ✅ 主数据库：0379_world
- ✅ 核心共享库：yyc3_core
- ✅ AI 助手库：yyc3_aify
- ✅ 企业管理库：yyc3_my
- ✅ MCP API 服务库：yyc3_mcp
- ✅ 开发测试库：yyc3_dev

#### 工具和脚本

- ✅ 环境变量验证脚本
- ✅ 性能基线测试脚本
- ✅ 监控启动脚本
- ✅ Grafana 仪表盘配置脚本
- ✅ 告警通知脚本

#### 文档

- ✅ 项目 README.md
- ✅ API 全链路架构文档
- ✅ 整体架构设计文档
- ✅ 多端架构说明文档
- ✅ 项目现状分析文档
- ✅ 部署完成总结文档

### 文档规范

#### 合规性统一

- ✅ 所有 Markdown 文档添加 YAML Front Matter 标头
- ✅ 所有 Python 代码文件添加 JSDoc 标头注释
- ✅ 文件命名规范化（snake_case）
- ✅ 项目目录结构规范化
- ✅ 创建合规性检查工具集

#### 新增文档

- ✅ CHANGELOG.md - 版本变更日志
- ✅ CONTRIBUTING.md - 贡献指南
- ✅ LICENSE - MIT 开源许可证
- ✅ Makefile - 构建脚本
- ✅ Dockerfile - Docker 构建文件

### 变更 (Changed)

#### 项目结构优化

- 🔄 重组项目目录结构
- 🔄 规范化配置文件管理
- 🔄 优化 Docker Compose 配置

#### 性能优化

- 🔄 数据库连接池优化
- 🔄 Redis 缓存策略优化
- 🔄 API 限流配置优化

### 修复 (Fixed)

#### 环境配置

- 🐛 修复环境变量配置问题
- 🐛 修复 Docker 网络冲突问题
- 🐛 修复 NFS 挂载中断问题

#### 服务稳定性

- 🐛 修复健康检查失败问题
- 🐛 修复服务自动重启问题
- 🐛 修复监控数据采集问题

---

## [0.9.0] - 2026-03-21

### 新增 (Added)

#### 基础架构

- ✅ 项目初始化
- ✅ 基础目录结构创建
- ✅ Git 仓库初始化
- ✅ 基础配置文件

#### 数据库服务

- ✅ PostgreSQL 数据库部署
- ✅ Redis 缓存服务部署
- ✅ 数据库初始化脚本

#### 容器化

- ✅ Docker Compose 配置
- ✅ 基础镜像构建
- ✅ 容器网络配置

---

## 版本说明

### 版本号格式

遵循语义化版本 2.0.0 规范：`主版本号.次版本号.修订号`

- **主版本号（MAJOR）**: 不兼容的 API 修改
- **次版本号（MINOR）**: 向下兼容的功能性新增
- **修订号（PATCH）**: 向下兼容的问题修正

### 变更类型

- **新增 (Added)**: 新功能
- **变更 (Changed)**: 对现有功能的变更
- **弃用 (Deprecated)**: 即将删除的功能
- **移除 (Removed)**: 已删除的功能
- **修复 (Fixed)**: 任何 bug 修复
- **安全 (Security)**: 安全相关的修复

---

## 路线图

### v1.1.0 (计划中)

- [ ] 完善测试覆盖（单元测试、集成测试）
- [ ] 添加 API 文档（Swagger/OpenAPI）
- [ ] 优化监控告警规则
- [ ] 添加自动化运维脚本

### v1.2.0 (计划中)

- [ ] CI/CD 流程配置
- [ ] 自动化部署流程
- [ ] 性能优化和压力测试
- [ ] 安全加固和渗透测试

### v2.0.0 (长期规划)

- [ ] 微服务架构重构
- [ ] Kubernetes 部署支持
- [ ] 多租户支持
- [ ] 插件化架构

---

## 贡献

如果您想为本项目做出贡献，请参阅 [CONTRIBUTING.md](./CONTRIBUTING.md)。

---

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](./LICENSE)。

---

**维护团队**: YanYuCloudCube Team
**联系方式**: <admin@0379.email>
**项目地址**: <https://github.com/YYC-Cube/yyc3-api-world>

---

[1.0.0]: https://github.com/YYC-Cube/yyc3-api-world/releases/tag/v1.0.0
[0.9.0]: https://github.com/YYC-Cube/yyc3-api-world/releases/tag/v0.9.0
