---
file: 04-模型接入与Agent注册实施总结报告.md
description: 0379-World 模型接入与 Agent 注册全面实施推进总结 - 2026-09-28
author: AI Tutor <yyc3-expert>
version: v1.0.0
created: 2026-09-28
updated: 2026-09-28
status: stable
tags: [summary],[implementation],[registry],[a2a],[model-asset]
category: report
---

# 📋 模型接入与 Agent 注册实施推进总结报告

## 一、任务背景与输入

| 属性 | 值 |
| ---- | ---- |
| **任务指令** | 基于 `docs/模型接入与注册/`（六文档体系）+ `docs/模型资产与路径/`（资产详情），全面实施推进模型接入与 Agent 注册；按新文档体系更新项目 README 和代码注释；生成详细总结日志 |
| **执行日期** | 2026-09-28 |
| **规范基线** | 上一会话整合产出的六文档体系（现状基线 01 / Registry 目标架构 02 / 热切换 03 / Agent 注册 04 / Runbook 05 + README 索引） |
| **资产输入** | NAS `/Volume1/yyc3_hd/data` 32 权重目录 8.40TB（DeepSeek/GLM/Qwen/Kimi 等七族）+ yyc3-22 本机 25 目录（2026-09-27 四轮实测快照） |

## 二、交付总览（四件实施 + 双对齐）

| # | 交付物 | 类型 | 规模 | 测试 |
| - | ------ | ---- | ---- | ---- |
| ① | [model_asset_verify.py](../../core/scripts/model_asset_verify.py) 资产完整性校验 | 脚本（规范 01 §2.3 P1） | 223 行 | 12 用例 ✅ |
| ② | [model_sync_to_node.py](../../core/scripts/model_sync_to_node.py) NAS→节点增量同步 | 脚本（规范 01 §2.4 P1） | 134 行 | 8 用例 ✅ |
| ③ | Registry Phase A MVP（五表 + 服务层 + 12 端点 + 双通道合并） | 服务（规范 02 §3/§4.1/§4.4） | SQL 95 行 + svc 600 行 + api 300 行 | 29 用例 ✅ |
| ④ | A2A Agent 演进层（三管理端点 + 扩展元数据） | 端点（规范 04 §4） | protocol +35 行 / api +55 行 | 10 用例 ✅ |
| ⑤ | README + 代码注释 + .env.example 对齐 | 文档 | 4 文件 | doc_links ✅ |
| ⑥ | 规范 README 状态总览表 8 项 📋→✅ | 文档 | 1 文件 | — |

## 三、实施细节

### 3.1 实施①：资产完整性校验脚本

**三项校验**（对齐规范 01 §2.3）：

1. **分片对账**：`model.safetensors.index.json` 的 `weight_map` 引用分片 vs 实际文件——缺分片即 fail；未引用的额外分片仅提示不阻断（LoRA/适配器混存场景）；无 index 的单文件/量化包形态放行
2. **头部 magic**：每文件前 8 字节校验 safetensors magic（`0x5A4B53CD` 小端）——识别截断（<8B）与损坏；`--sample N` 抽检提速（TB 级目录）
3. **配置存在性**：config.json / tokenizer.json / tokenizer_config.json 必需；词表双形态兼容（vocab.json / vocab.txt / tokenizer.model 任一）

**工程语义**：报告落盘 `model_checksum.report`（规范要求）；CLI 退出码 0/1/2 = 通过可上线/失败禁上线/目录不存在；`--json` 供 CI 集成；报告写失败（只读挂载）降级 stderr 告警不阻塞。

### 3.2 实施②：NAS→节点增量同步脚本

- **rsync 封装**：`-a --info=progress2 --partial`（断点续传，权重 GB~TB 级必需）；排除 `model_checksum.report`/`*.tmp`/`.DS_Store`
- **三模式**：直跑（NFS 挂载源）/ `--ssh yyc3-45`（远端源）/ `--dry-run`（预检）
- **`--plan` 增量计划**：不经 rsync 的本地 diff（待传/已同步/残片续传三分类——同名但目标更小 = 上次中断残片）
- **同步后门禁**：自动复用 ① 的分片对账校验目标侧，失败退出码 3（对账不过 = 同步不完整）

### 3.3 实施③：Registry Phase A MVP（本轮核心）

**架构定位**（规范 02 §4.1 Phase A）：Registry 与 env 双通道共存，Registry 优先 env 兜底，`REGISTRY_ENABLED` 灰度开关（默认 false = 纯 env 现状行为零变化）。

**四层落地**：

| 层 | 文件 | 关键设计 |
| -- | ---- | ---- |
| 迁移 | [005_model_registry.sql](../../core/database/init/005_model_registry.sql) | 存量 `model_registry` 表 `ADD COLUMN IF NOT EXISTS` 增量扩展 26 列（**禁止 DROP 重建**——NAS 网关栈已有生产数据）；四张新表（versions/heartbeats/events/audit_log）；结构化列统一 TEXT 存 JSON 串（**规避 asyncpg JSONB 绑定坑**，7bf98c8 TEXT[] 教训） |
| 服务 | [model_registry_svc.py](../../core/api/services/model_registry_svc.py) | 幂等注册（重复=覆盖+版本历史追加）；回滚防盲滚（目标版本必须在历史中）；心跳 TTL 三级阶梯**读时判定**（90s→degraded / 180s→unreachable / 300s→摘除，无后台任务）；事件双投递（PG 持久 Pull 源 + Redis pub/sub 实时 Push 源）；`registry_upstreams()` 产出 env 同构条目；DB 不可达一律空返回+告警（env 通道兜底，绝不阻塞网关） |
| API | [model_registry.py](../../core/api/api/model_registry.py) | 12 端点全落地；SSE 事件流（R-10）连接建立先回放 `model_events` 在途事件防漏，再订阅 `yyc3:registry:events`，`: ping` 保活帧 + 超时自断；写操作端点内校验 admin（`request.state.user.admin`）；灰度关未开时写端点 503（`registry_disabled` 显式语义） |
| 集成 | [upstream_registry.py](../../core/api/services/upstream_registry.py) `merge_registry_upstreams()` | `registry-{model_id}` 命名与 env 上游隔离；幂等合并（同名保留熔断/EWMA/负载运行时状态，仅刷新静态配置）；main.py startup 挂载（REGISTRY_ENABLED=true 时执行） |

**UTC 时区坑（本轮最有价值的 Debug）**：sqlite `CURRENT_TIMESTAMP` 写 UTC 无时区字符串，`time.mktime` 按本地时区（Asia/Shanghai +8）解析 → 心跳 age 虚增 28800s → 全部误判 unreachable。修复 `_to_epoch` 用 `calendar.timegm` 按 UTC 解释（naive datetime 同路径处理）；PG TIMESTAMPTZ 经 asyncpg 返回 aware datetime 不受影响。

### 3.4 实施④：A2A Agent 演进层

以现有 A2A 生产契约为基线扩展（**不另起第二套注册体系**，规范 04 消双轨决策）：

| 端点 | 语义 | 设计要点 |
| ---- | ---- | ---- |
| GET `/v1/admin/a2a/agents` | 全量列表（含离线） | 在线/离线计数；扩展元数据随卡片返回；capability 过滤 |
| PATCH `/v1/admin/a2a/agents/{id}` | 局部更新扩展元数据 | **白名单字段**（tools/timeout_seconds/max_concurrent/rate_limit_per_minute/agent_type/protocol 等 15 项）；保留 register_time/last_heartbeat；变更入审计流 |
| DELETE `/v1/admin/a2a/agents/{id}` | 注销 | HDEL；**内置编队 30s 心跳循环自愈回归**——停用内置成员走 `A2A_WORKER_AGENTS` env（语义已在 docstring 文档化） |

### 3.5 对齐：README / 注释 / env

- [README.md](../../README.md)：核心特性段新增「模型注册中心」块（12 端点/双通道/五表/工具链）；API 文档段新增认证方式 Bearer 兼容行 + 「关键端点族」表（三端点族 → 规范文档映射）
- [upstream_registry.py](../../core/api/services/upstream_registry.py) / [a2a_protocol.py](../../core/api/services/a2a_protocol.py) 顶部 docstring 补双通道/演进层说明与规范引用；全部新文件带 `# spec:` 头注释指向规范章节
- [.env.example](../../core/config/.env.example)：新增 `REGISTRY_ENABLED` 段（语义/迁移指引/默认 false）
- [规范 README](../模型接入与注册/README.md)：实现状态总览表 **8 项 📋→✅**（五表/12端点/双通道/心跳TTL/演进层三端点/MCP tools 声明/双脚本），仅剩模型服务侧契约端点、热切换、alias、register_agent、smoke_test 五项 📋

## 四、质量门禁记录

| 门禁 | 结果 |
| ---- | ---- |
| pytest 快速层全量（-m "not integration"） | ✅ **131 passed**（含新增 21） |
| pytest 新增 integration（五文件） | ✅ **38 passed** |
| flake8（CI 口径，新改文件） | ✅ 0 错误 |
| black --check / isort | ✅ 12 files unchanged |
| check_doc_links.py | ✅ 通过 |

**测试覆盖面**：CRUD 幂等 / 回滚防盲滚 / 心跳 TTL 三级阶梯（含时区归一回归）/ 双通道上游产出（ready 过滤 + 300s 摘除）/ SSE 回放 / RBAC 403 / 灰度 503 / 未认证 401 / 白名单字段注入防护 / 审计写入 / 资产校验全形态（完整/缺片/坏 magic/截断/缺配置/单文件/空目录/抽检）。

## 五、遇到的问题与解决

| 问题 | 根因 | 解决 |
| ---- | ---- | ---- |
| Registry API 测试 26 errors（socket.gaierror） | `ensure_tables` 内 `from app.db import engine` 取未 patch 的真 PG 引擎（容器主机名 DNS 失败） | fixture 补 `monkeypatch.setattr(app_db, "engine", sqlite_engine)` |
| TTL 全部误判 unreachable | sqlite UTC 字符串被 `time.mktime` 按本地时区解析（+8h = 28800s 假超时） | `_to_epoch` 改 `calendar.timegm` 按 UTC |
| 审计断言 KeyError | 桩审计条目经 `_stringify`：detail dict 已 JSON 串化 | 断言改查顶层 action 字段 |
| 测试同名目录 FileExistsError | CLI 测试两次构造同目录名 | `_make_model` 加 name 参数 |

## 六、关键决策记录

| 决策 | 备选 | 选择理由 |
| ---- | ---- | ---- |
| TEXT 存 JSON 而非 JSONB | JSONB + GIN | asyncpg 绑定层类型坑（TEXT[] 前科）；MVP 查询过滤走 enabled/state 标量列 |
| 心跳 TTL 读时判定（无后台协程） | 后台扫描任务 | 零额外资源；写入侧 upsert 已保数据新鲜；网关侧 `registry_upstreams()` 同源判定 |
| 版本历史无 UNIQUE(model_id, version) | 加唯一约束 | 版本历史是 append-only 事件日志（register→rollback 同版本多条合法） |
| 写操作端点内校验 admin | 扩展 AuthMiddleware admin 前缀 | 不动中间件全局行为；`/registry/v1/**` 保持普通认证（心跳=模型服务身份） |
| SSE 先回放再订阅 | 纯订阅 | 防漏（连接建立前的事件）；对齐 A2A result_hub 追平在途回执的同款语义 |

## 七、遗留与下轮建议

1. **[P1] NAS 生产部署 Registry**：005 迁移上 PG → `REGISTRY_ENABLED=true` 灰度 → 现有 4 生产上游（dsv4/embedding/rerank/asr/ocr）注册入中心 → `merge_registry_upstreams` 生产验证
2. **[P2] register_agent.py**：模型服务侧自动注册+心跳脚本（规范 01 附录 A 唯一未落地 P2 脚本；契约端点 `/v1/model/metadata` 随其落地）
3. **[P2] model_smoke_test.py**：上线冒烟自动化（九项用例，规范 01 §5）
4. **[P2] 热切换 Phase B**：alias 切换 + draining（规范 03，依赖 Registry 生产稳定）
5. **观察项**：SSE 事件流经反代（frpc/Traefik）需确认禁用响应缓冲（`X-Accel-Buffering: no` 已设，需链路实测）

## 八、统计数据

| 指标 | 数值 |
| ---- | ---- |
| 新增源文件 | 5（2 脚本 + 1 SQL + 1 svc + 1 api） |
| 修改源文件 | 5（main / a2a / a2a_protocol / upstream_registry / .env.example） |
| 新增测试文件 | 5（59 用例：快层 21 + integration 38） |
| 新增代码行 | ~1,700（含测试） |
| 文档更新 | 4（README / 规范 README 状态表 / CHANGELOG / 本报告） |
| 门禁 | 快层 131 + integration 38 + lint 三件套 + doc_links 全绿 |

---

**报告状态**: ✅ 实施完成
**下次会话起点**: 本报告 §七 遗留清单（P1 = NAS 生产部署 Registry 灰度）
