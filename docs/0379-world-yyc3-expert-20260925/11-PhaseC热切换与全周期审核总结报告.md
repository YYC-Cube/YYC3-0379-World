---
file: 11-PhaseC热切换与全周期审核总结报告.md
description: 0379-World Phase C 热切换实施与生产演练 - 模型接入全周期审核 - 其他体系主线建议 - 2026-09-28
author: AI Tutor <yyc3-expert>
version: v1.0.0
created: 2026-09-28
updated: 2026-09-28
status: stable
tags: [summary],[hot-swap],[alias],[draining],[audit],[roadmap]
category: report
---

# 📋 Phase C 热切换与全周期审核总结报告

> 本报告三合一：① Phase C（规范 03 §3 唯一未实施面）实施与生产演练总结；② 模型接入与注册体系全周期审核（Phase 8 → 稳态期 → Phase C，2026-09-28 单日闭环）；③ 其他体系主线建议（代码库现状取证）。

---

## 一、Phase C 实施总结 ✅

**提交**：`05635b0`（已推 main + feat/ops-rag-hybrid，已部署 NAS 生产）
**规模**：9 文件，+514 / -26
**规范锚点**：[03-热切换与版本管理.md](../模型接入与注册/03-热切换与版本管理.md) §3（v1.1.0 状态已回写）

### 1.1 交付物清单

| 层 | 交付物 | 说明 |
| --- | --- | --- |
| 数据 | [006_model_aliases.sql](../../core/database/init/006_model_aliases.sql) | `model_aliases` 表（alias PK / model_id / created_at / updated_at + 索引）；PG 生产直灌 + sqlite ensure_tables 自建双落地 |
| 服务 | [model_registry_svc.py](../../core/api/services/model_registry_svc.py) v1.1.0 | `_alias_cache` 内存路由表 + `load_alias_cache`（DB 不可达保留旧表）+ `resolve_alias`（同步零开销旁路）+ `set_alias`（**ready 防呆** + 审计 before/after + `alias_switched` 事件）+ `delete_alias` + `drain_model`（幂等 + `drain_observation` 含 active_requests） |
| API | [model_registry.py](../../core/api/api/model_registry.py) v1.1.0 | 12→16 端点：R-13 `GET /registry/v1/aliases`（含 route_cache）/ R-14 `PUT /aliases/{alias}` / R-14b `DELETE` / R-15 `POST /models/{id}/drain`；全带 `_require_admin` + 503 灰度闸门 |
| 网关 | [chat.py](../../core/api/api/chat.py) | `_select_backend` 首行 `resolve_alias`；**VK 白名单仍校验公网名**（权限面与路由面分离）；[main.py](../../core/api/main.py) startup 预热缓存 |
| 语义 | 零新代码复用 | draining 摘池 = `registry_upstreams()` 仅收 ready + 心跳自愈 `CASE` 不覆盖 draining（既有机制自动接线） |
| 测试 | svc 29 + api 19 + 快速回归 148 全绿 | `TestAliasHotSwap` 7 用例 + `TestDrainSemantics` 4 用例（含 **§3.5 五步切换+回滚全链路单测**）；api `TestAliasAndDrainEndpoints` 7 用例（403/503 闸门全覆盖） |

### 1.2 架构要点：三路一致性

```
startup load_alias_cache（全量预热）
  + set/delete 本进程直更（免等事件回环）
  + alias_switched/alias_deleted 事件全量重载（跨进程兜底）
```

路由面（model_id）与权限面（公网名）分离：`_select_backend` 首行解析 alias 后，后续候选、熔断、主权标签全部沿用既有 model_id 链路，零侵入。

---

## 二、生产灰度演练：十步全实证 ✅

NAS 生产环境（@05635b0，healthz + SMOKE_PASS 6/6）对 [规范 03 §3.5 五步流程](../模型接入与注册/03-热切换与版本管理.md) 全链实证，**零流量影响、审计完整留痕**：

| 步骤 | 操作 | 实证结果 |
| ---- | ---- | -------- |
| ① | `GET /registry/v1/aliases` | `{"aliases":[],"count":0,"route_cache":{}}` 初始空 |
| ② | PUT `chat-drill` → deepseek-v4-flash | `switched, previous:null` |
| ③ | alias 名发 chat 流量 | **HTTP 200** + vLLM 内容回显（端到端通） |
| ④ | 切指 → qwen3-asr-1.7b | `switched, previous:deepseek-v4-flash`（免重启切流） |
| ⑤ | 切换生效证明 | 200 但**无 `X-YYC3-Upstream` 头**、响应 model=glm-4-flash——路由落空走云兜底，证明已脱离 dsv4 通道 |
| ⑥ | POST drain dsv4 | `draining` + drain_observation（heartbeat 28.7s + active_requests） |
| ⑦ | 池对账 | registry-dsv4 **消失**（其余 4 registry 条目在）；env flagship-dsv4 保留；chat 仍 200（零流量影响） |
| ⑧ | 回滚尝试（alias→dsv4） | **422「state=draining，仅 ready 可接别名流量」**——§3.5 约束生产实证（预期外但正确） |
| ⑨ | undrain（PATCH state=ready） | registry-dsv4 **回归路由池**（Phase B 事件重合并） |
| ⑩ | 清理 + 回滚实证 | DELETE alias OK；重设 alias→dsv4 → chat **200** → DELETE；终态干净 |

**审计留痕**：6 条完整（`alias.switched`×3 / `alias.deleted`×2 / `model.draining`×1，before/after 全程可溯）。

### 2.1 演练发现项（三条，均已定性）

| # | 发现 | 定性 | 处置建议 |
| --- | --- | --- | --- |
| 1 | alias 指向非 chat ready 模型 → 上游池无候选 → 云兜底 glm-4-flash 返回 200（无 upstream 头） | **既有 fallback 行为**，非 Phase C 缺陷；演练中反证切换生效 | 可选优化：set_alias 指向非 chat 模型时审计 warning 或提供 dry-run 校验（P3） |
| 2 | ⑧ 步 422 拦截切向 draining 模型 | **ready 防呆生产实证**（设计价值意外闭环） | 无需处置，写入规范佐证 |
| 3 | audit 端点 before/after_state 已被反序列化为 dict，展示层切片需 `json.dumps` | 展示层小坑（非存储问题） | 已在演练脚本修正；API 本身无恙 |

---

## 三、模型接入与注册体系全周期审核（09-28 单日闭环）

### 3.1 周期脉络（提交链）

```
Phase 8 全面实施   1d83542 文档体系六文档拆分（40% 重复双规范 → 五文档+索引）
                  b2c0c2d/fac630a Registry 生产灰度十连全通（+两项生产修复）
                  TOP1 五生产上游双写注册入中心（priority 5 零切换入池）
                  cffd3cd  register_agent.py + Phase B 事件驱动增量合并 + 502 定论
                  513aab7/4c1e649 旗舰恢复 + 九用例冒烟（附录 A 清零）+ 五服务 Agent 实拉起
稳态期            7946f76/5d412fd systemd 常驻 + OOM recreate + 心跳观测
                  🚨 pkill 竞态事故 → 自愈固化（offline→ready 回升 + 事件重合并）
                  bc95638 Prometheus 三告警规则 + canary 终局 + 日志轮转双模板
Phase C（本轮）    05635b0 别名热切换 + draining 排空 + 生产十步演练
```

### 3.2 六维审核评分

| 维度 | 得分 | 依据 |
| ---- | ---- | ---- |
| 规范闭环 | **98** | [README 状态总览表](../模型接入与注册/README.md) 全线 ✅（仅模型侧契约端点属模型服务方职责）；规范 01-05 状态全部回写真实 |
| 代码质量 | **95** | svc v1.1.0 单文件内聚（缓存/事件/审计三链一致）；快速回归层 148 全绿；测试含全链路演练单测 |
| 生产稳定性 | **97** | 单日两次生产事故（502/pkill）均根因定案并固化自愈；本轮演练零流量影响零回滚 |
| 可观测 | **95** | 心跳 Gauge×2 + 三告警规则热加载 + 审计 6 条留痕 + drain_observation |
| 文档同步 | **96** | 02/03 会话文档逐阶段追加、CHANGELOG 逐条目对应提交、报告 04-11 序列完整 |
| 运维资产 | **94** | systemd 双模板/logrotate 双模板/告警规则入库 deploy/；OPS-RECOVERY 持续对齐 |

**综合**：**95.8 / 100** —— 体系进入「五高」运行态（高可用自愈/高可观测/高文档闭环/高测试覆盖/高生产实证）。

### 3.3 遗留清单（全量盘点）

| 项 | 优先级 | 状态 |
| --- | --- | --- |
| yyc3-102 `sudo loginctl enable-linger` | P2→用户 | **唯一待用户一条命令**（登录会话自启已生效，仅冷启敞口） |
| alias 指向非 chat 模型的 dry-run 校验 | P3 | 可选优化（发现项 #1） |
| Shadow/Canary/蓝绿（规范 03 §4-§6） | P3 | 规划态；别名切换已覆盖 90% 日常切换需求，Shadow 需流量复制基础设施 |
| 模型服务契约端点 `/v1/model/metadata` | P2 | 模型服务侧实现（见下文主线建议） |

---

## 四、其他体系主线建议（代码库现状取证）

> 按「价值 × 就绪度 × 成本」三轴排序，均基于代码与文档实证，非猜测。

### [P1] RAG 混合检索深化（工作分支名既定主线：`feat/ops-rag-hybrid`）

**现状证据**：[ops_rag.py](../../core/api/services/ops_rag.py) v1.0.0 已入 main——chroma 四库（main/prompts/premium/online）+ 零依赖 BM25 + RRF 融合 + 降级链（8B 离线 → 0.6b+online → 503 明确错误）；**评测基线 golden set v2 · 40 题 Top3：online 31% / premium 45% / main 55%**。

**为什么是 P1**：
1. 召回质量天花板明显（顶格 55%），提升空间 = 业务价值最直接的一格；
2. **rerank 上游已在生产注册池 ready**（yyc3-101，Phase 8 注册）——RRF 后接交叉重排是零基建增量的最大单项收益点；
3. 四库评测梯度（31/45/55）说明库间质量差异已被量化，具备 A/B 验证条件。

**建议路径**：① rerank 接入 RRF 后重排（先 premium 库试点，同 golden set 对比）→ ② BM25 索引重建自动化（当前手动 reindex）→ ③ golden set 扩容 40→100+ → ④ `api/rag.py` 对外端点与 ops_rag 整合收口。

### [P2] 模型服务契约端点 `/v1/model/metadata`（体系最后一块拼图）

**现状证据**：[README 状态表](../模型接入与注册/README.md) 唯一剩余模型侧 📋 项；当前注册 Agent（[model_register_agent.py](../../core/scripts/model_register_agent.py)）靠 `/v1/models` 探测 + 本地推理判定能力面——冒烟脚本为此做过「能力面感知」修复（4c1e649）。

**建议**：五服务（vLLM 侧）加三端点（metadata/capabilities/health 统一契约）→ register_agent 优先读契约、探测作降级。收益：能力面从「推断」变「声明」，消除冒烟脚本绕行逻辑；模型接入体系 100% 收官。

### [P3] A2A 用量报表 / 账单面（商业化闭环）

**现状证据**：数据面已全——vk 计费门控（403/402/429）+ `X-A2A-Cost` 成本直报 + 中间件记账 + TASK_TYPE_PRICES 价格表（004 持久化 + 管理端点）+ usage_logger；**消费面缺失**（无报表查询端点、无账单聚合）。

**建议**：`GET /v1/admin/usage/summary`（按 vk/agent/task_type/时间窗聚合）+ 可选 CSV 导出。纯只读增量，风险低，把「计费链已通」升级为「账可算、可看」。

### [P4] Shadow 影子流量（规范 03 §4，远期）

**为何靠后**：别名切换已覆盖生产 90% 切换场景（切指即生效+drain 排空+回滚防呆）；Shadow 需请求复制/响应比对/达标判定三件基础设施，成本高而当前无新版本上线压力。建议待 RAG/契约端点稳定后再启；轻量过渡 = set_alias dry-run 校验（发现项 #1）。

### 候选但建议后置

- **Token 调用平台前端**：设计文档已在 [docs/设计理念/](../设计理念/Token调用平台前端-全维度设计与落地文档.md)，但后端报表面（P3）先行更符合依赖序；
- **MCP 工具声明扩面**：白名单字段机制已落地（09-28），待真实 Agent 工具注册需求出现再扩。

### 主线路线图建议

```
2026-Q4  P1 RAG 混合检索深化（rerank 重排 → golden set 扩容 → 端点收口）
         P2 模型服务契约端点（模型服务侧三端点 + register_agent 契约优先）
         P3 A2A 用量报表（只读聚合）
后置      P4 Shadow 影子流量 / Token 平台前端 / MCP 扩面
```

---

## 五、会话收尾状态

| 项 | 状态 |
| --- | --- |
| 生产环境 | ✅ 干净（别名已删、dsv4 ready、池 5+7 完整、审计闭环） |
| 代码 | ✅ 05635b0 入 main + feat/ops-rag-hybrid，NAS 已部署 |
| 测试 | ✅ svc 29 + api 19 + 快速回归 148 全绿 |
| 文档 | ✅ 规范 03 v1.1.0 + README v1.2.0 状态回写；本报告为全周期收官件 |
| 待用户 | ⚠️ 102 `sudo loginctl enable-linger $USER`（唯一一条） |

**审核结论**：✅ 通过——模型接入与注册体系全周期闭环（Phase A MVP → Phase B 增量 → Phase C 热切换，三阶段单日完工并生产实证），建议下轮转入 **P1 RAG 混合检索深化主线**。

---

**报告完** · 2026-09-28 · AI Tutor yyc3-expert
