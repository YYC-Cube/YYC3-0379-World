# YYC³ Gateway 代码库深度分析与落地执行方案

> **文档版本**: v1.0.0 | **生成日期**: 2026-09-02
> **分析对象**: 本仓库（YYC3-0379-World，FastAPI 网关）全量代码 + 部署体系 + 测试体系
> **对照基线**: 《YYC3-高可用API架构闭环-最佳指导文档》(v1.0.0, 2026-08-30) §6 API 契约与路由表、§5.3 三级推理池、§十二实施路线
> **定位**: 承接架构文档 §十二路线中**本仓库可执行的部分**——把「规划中的网关」变成「代码里的网关」；设备侧任务（systemd 化 / 监控栈启动 / DNS）不在本文范围，仅标注依赖关系
> **执行状态（2026-09-03）**: ✅ **Phase 0 全部完成**（P0-1 配置体系/P0-2 清理/P0-3 测试地基——15 用例 CI 绿）✅ **Phase 1 全部完成**（P1-1 Registry+统一客户端/P1-2 三段式路由+record_result/P1-3 熔断+降级链+X-YYC3 头/P1-4 观测真实化）——**旗舰 deepseek-v4-flash 已对公网服务**（api.0379.world 实测）。修订：路由选择为**优先级分层**（原方案未明确，实测发现跨层随机会吞流量）；failover_manager 已删；ECS 双活降级为可选（实况=Traefik 边缘反代+NAS 单实例）。Phase 2/3 待排期。

> **结论预览**: 网关代码「骨架健全、核心未接线」——认证/限流/缓存/可观测等横切能力已达生产基线，但**智能路由未接入请求链路、上游地址全部硬编码且含过期拓扑、4 个规划端点缺失、测试形同虚设**。四个 Phase 共约 10-13 个工作日可闭环。

---

## 一、TL;DR：五个最重要的发现

| # | 发现 | 证据 | 影响 |
|---|------|------|------|
| 1 | **智能路由器是死代码**：`model_router.py` 的 EWMA 加权算法完整，但未接入任何请求路径，仅被 `/v1/router/stats` 观测端点引用；真实路由是 `chat.py:53-87` 的模型名前缀硬编码匹配 | `core/api/api/chat.py:53-87` vs `core/api/services/model_router.py:107` | 架构文档 §6.3 的核心（EWMA 路由 + 熔断 + 降级链）实际不存在；DGX 双机推理池无法被网关利用 |
| 2 | **上游地址全部硬编码且含过期拓扑**：智谱/DeepSeek/OpenAI 基址为模块常量；Ollama 三端点含旧 IP `10.200.0.3`；`config.py` 无任何 base_url 配置项；`host_ip` 默认值 `10.200.0.2` 是已废弃拓扑 | `zhipu.py:30`、`deepseek.py:20`、`openai.py:30`、`ollama.py:30-34`、`config.py:40` | 网关无法指向 NIM(:8000)/SGLang(:30000)/Ollama 双机(:11434/:11435)/TEI(:8100/8101)——§6.2 上游表 0/9 落地 |
| 3 | **API 契约缺口 4/7**：`/v1/embeddings`、`/v1/rerank`、`/v1/audio/transcriptions`、`/v1/ocr` 不存在（embedding 只是 RAG 内部服务，未暴露端点） | 全库 grep 无结果；`core/api/services/embedding.py:19` | §6.1 对外契约只有 chat/models 一半；伯乐/守护等 Agent 的能力端点无入口 |
| 4 | **测试形同虚设**：pytest.ini 要求覆盖率 ≥80%，但唯一的 Python 测试是硬编码打生产环境 `https://api.0379.world` 的脚本（无 pytest 断言、无 mock）；`core/tests/` 为空目录；Cypress 与 Playwright 两套 E2E 重复测同一批 API，Cypress 历史截图大量 failed | `tests/test_gateway_api.py`、`pytest.ini`、`tests/e2e/` | CI 的 test job 实际验证不了任何东西；改路由代码无回归防线 |
| 5 | **观测数据造假 + 悬空引用**：`/ws/monitor` 推送硬编码延迟数据；`/v1/models/stats` 返回硬编码 0；根 compose 挂载不存在的 `core/config/prometheus/prometheus.yml`；Makefile `docker-up` 指向不存在的 `docker-compose.stable.yml` | `websocket.py:226-234`、`main.py:507-508`、`docker-compose.yml`、`Makefile` | 监控栈起不来或起来也看不到真实路由状态；开发者 `make docker-up` 直接失败 |

**一句话诊断**：本仓库目前是一个「多云适配器集合 + 横切能力齐全」的 v1 网关，而架构文档要求的是「三级推理池统一入口 + 智能路由」的 v2 网关——中间隔着一次**路由层实装 + 配置体系重构**，而不是推倒重写。

---

## 二、现状全景：代码 vs 架构文档逐项对照

### 2.1 横切能力（已达生产基线，保持不动）

| 能力 | 实现 | 证据 | 评价 |
|------|------|------|------|
| 认证 | JWT(Bearer) + API Key(X-API-Key) 双通道，放行 /health /healthz /metrics 等；WebSocket 走 query token | `middleware/auth.py:226-264, 51-66` | ✅ 完备 |
| 限流 | Redis ZSET 滑动窗口 + Lua 原子脚本，Redis 故障自动降级内存窗口；IP 500/min + 用户 1000/min；TRUSTED_PROXIES 含 Tailscale 网段 | `middleware/rate_limit.py:40-96` | ✅ 超出文档要求 |
| 缓存 | Redis LLM 响应缓存，TTL/LRU/tag 失效，配套 4 个管理端点 | `services/cache.py`、`main.py:323-355` | ✅ |
| 可观测 | prometheus-fastapi-instrumentator /metrics + 自定义 MetricsManager + psutil 资源 | `main.py:116`、`utils/metrics.py` | ✅ 指标有了，但路由维度数据是假的（见 2.3） |
| 数据层 | SQLAlchemy 2.0 async + asyncpg；表：model_registry / usage_log / 知识库三件套 + pgvector chunks | `db.py:53-203` | ✅ |
| 错误处理 | error_handler + with_retry 装饰器 | `errors/handler.py` | ✅ |
| 部署 | 多阶段 Dockerfile（非 root + HEALTHCHECK）+ NAS 专用 compose（凭据全 .env 化）+ 部署脚本带旧凭据检测 | `Dockerfile`、`deploy/nas/` | ✅ 基本健全 |

### 2.2 路由与上游（核心差距，Phase 1 主战场）

| 架构文档要求 (§5.3/§6.2/§6.3) | 代码现状 | 差距 |
|------|------|------|
| 上游池 9 类：NIM 旗舰 / SGLang / Ollama×2 / TEI×2 / OCR / ASR / Safety / 兜底×2 | 4 个云适配器（智谱/DeepSeek/OpenAI/Ollama），基址硬编码 | **0/9 可配置接入** |
| EWMA 延迟 + 错误率 + 负载加权路由 | 算法存在于 model_router.py，**未接入 chat 链路** | 算法→接线 |
| 熔断：连续 3 次健康失败 → 摘除 30s 半开恢复 | 无状态机，只有 UNHEALTHY 标记 | 新建 |
| 降级链：旗舰 N2 → N1 → 本地 Ollama → 云 API（degraded 头） | 仅一条硬编码：Ollama 失败 → glm-4-flash（`chat.py:169-195`） | 泛化为配置驱动 |
| 会话粘性（prefix cache 命中优先） | 无 | P2 可选 |
| QSFP 主路径 + Tailscale 备路径双上游 | 无 | 新建（每上游双地址） |
| Token 预算 → 治理中枢 :25700 | 无对接 | P3（依赖 N2 治理中枢就绪） |

### 2.3 数据真实性（Phase 1 收尾必须清除）

- `/v1/models/stats`：`avg_latency_ms=0.0`、`error_rate=0.0` 硬编码（`main.py:507-508`）
- `/v1/models/errors`：返回硬编码空列表（`main.py:515-518`）
- `/ws/monitor`：推送硬编码「ollama: 85ms / zhipu: 120ms, online」（`websocket.py:226-234`）

### 2.4 死代码与不一致清单（Phase 0 清理）

| 项 | 位置 | 处置 |
|----|------|------|
| failover_manager 整体死代码，`_sync_data`/`_update_routing` 是 sleep 桩，节点列表硬编码 yyc3-33/45/77 | `services/failover_manager.py:44-45, 163-169` | **删除**（职责并入路由器熔断，节点间主备切换由 Traefik 上游健康检查承担） |
| model_router 节点硬编码（yyc3-22/33/45 + hostname 直连） | `model_router.py:114-137` | 改为 UpstreamRegistry 配置注入 |
| Ollama 端口三处不一致：`core/config/.env.example` 11435 vs `config.py:31` 11434 vs `ollama.py:31,33` 硬编码 11434 | 三处 | 统一走 `settings.ollama_*`，注释说明双机 11434(N2)/11435(N1) 语义 |
| 旧拓扑 IP：`config.py:40` host_ip 默认 `10.200.0.2`、`ollama.py:33` 兜底 `10.200.0.3` | 两处 | 默认值改为 Tailscale 网段语义 |
| mcp_client 硬编码个人 macOS 绝对路径 `/Volumes/Development/...` | `mcp_client.py:50` | 配置化或移入 .env |
| 根 compose 挂载不存在的 `core/config/prometheus/prometheus.yml` | `docker-compose.yml` | 补文件或改挂载到真实存在的 `core/database/docker/prometheus/prometheus.yml` |
| Makefile `DOCKER_FILE := core/database/docker/docker-compose.stable.yml` 不存在 | `Makefile` | 修正路径 |
| ZHIPU_API_KEY 注释标注「已过期 401」 | `core/config/.env.example:44` | 提醒更换；降级链不应依赖过期 key |
| rag.py /ask 伪造 StarletteRequest 内部调用 chat 端点 | `api/rag.py:165-181` | 重构为直接调用 service 层函数 |
| documents.py 后台任务复用已提交会话的 db session | `api/documents.py:148,303` | 改为独立会话 |

---

## 三、落地执行方案（Phase 0 → 3）

> 原则：**每个 Phase 结束都是可部署状态**；先接线后增强；所有行为变更带 pytest 回归；设备侧任务只标注依赖不纳入本仓库排期。
> 总工期估算：**10-13 个工作日**（单人全职当量）。

### Phase 0 · 地基修复（1-2 天）——让仓库「配置驱动 + 可测试」

**P0-1 上游配置体系重构**（本方案最关键的一步，后续一切依赖它）

- `config.py` 新增：

```python
# 通用 OpenAI 兼容上游池（JSON 数组，env 注入；NIM/SGLang/vLLM/Ollama-兼容全走这一类）
openai_compatible_upstreams: str = "[]"
# 各云适配器基址外部化（默认值=现硬编码值，向后兼容）
zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
deepseek_base_url: str = "https://api.deepseek.com/v1"
openai_base_url: str = "https://api.openai.com/v1"
```

- 上游 JSON schema（每个元素）：

```json
{
  "name": "nim-flagship",
  "base_url": "http://10.100.168.1:8000",
  "fallback_url": "http://100.76.167.103:8000",
  "api_key_env": "NIM_API_KEY",
  "models": ["deepseek-v4-flash", "deepseek*"],
  "capability": "chat",
  "weight": 100, "priority": 1, "capacity": 32,
  "health_path": "/health"
}
```

- 改动点：`zhipu.py` / `deepseek.py` / `openai.py` / `ollama.py` 基址全部改读 settings；新增 `services/openai_compatible.py`（Phase 1 使用）。
- `.env.example` 增加上游配置段（对照架构文档 §6.2 上游表逐项给出注释示例——这一步同时就是「网关接入双 DGX 推理池」的配置说明书）。
- **验收**：不改任何 env 时行为与现状完全一致（回归靠 P0-3 的测试）；注入一个 mock 上游 env 后 `/v1/models` 能列出其模型。

**P0-2 死代码清理 + 不一致修复**：按 §2.4 清单逐项处置（删 failover_manager、统一 Ollama 端口、补 prometheus.yml、修 Makefile 路径、去个人路径）。
**验收**：`make lint && make docker-up` 成功；grep 全库无 `10.200.0.`、无 `/Volumes/Development`。

**P0-3 测试地基重建**

- `tests/test_gateway_api.py` 重写为标准 pytest：`TestClient` + `respx`（mock httpx，不打生产）；覆盖：/health、/healthz、/v1/models、chat（4 个后端前缀 + 未知模型默认路径）、认证 401/200、限流头、缓存命中。
- 修正 `pytest.ini`：覆盖率门槛降到现实值（建议 55%→逐步上调），`--cov=core.api`；6 个未用 marker 先删或启用。
- **验收**：`make test` 本地零网络依赖通过；CI test job 首次产出真实覆盖率数字。

**依赖**：无。**产出即可部署**（NAS/ECS 现有部署方式不变）。

---

### Phase 1 · 智能路由实装（3-5 天）——本方案的核心价值

> 目标：把架构文档 §6.2/§6.3 的「上游表 + 路由策略」变成运行时行为。完成后，chat 请求第一次真正流经 EWMA 加权路由。

**P1-1 UpstreamRegistry + 统一 OpenAI 兼容客户端**

- 新建 `services/upstream_registry.py`：启动时解析 env 上游池 → 注册到 ModelRouter（复用现有 ADAPTIVE 算法与 EWMA 字段，`model_router.py:189-257` 不需要重写）。
- 新建 `services/openai_compatible.py`：单个 httpx 客户端函数 `chat_completion(base_url, model, payload, stream)`，NIM/SGLang/vLLM/DGX 上游全走它；QSFP 主地址失败自动切 `fallback_url`（Tailscale）。

**P1-2 路由接线（chat.py 手术）**

- `_select_backend`（`chat.py:53-87`）改造为三段式：
  1. 云前缀（zhipu:/deepseek:/openai:）→ 走原适配器（兼容保留）；
  2. 上游池模型匹配（通配符）→ `router.select(model)` 返回上游实例 → openai_compatible 转发；
  3. 兜底 → 本地 Ollama（现默认行为保留）。
- 请求完成后调用 `router.record_result()`——**补上反馈闭环的最后一块**（该方法现无生产调用方）。

**P1-3 熔断器 + 降级链**

- 熔断：连续 3 次失败/健康探测失败 → 状态 OPEN，摘除 30s → 半开单请求探测 → 恢复（实现进 model_router，~80 行）。
- 降级链：按 capability 组配置（如 chat 组：nim-flagship → nim-backup → ollama-n2 → ollama-n1 → cloud-deepseek）；命中降级时响应头 `X-YYC3-Degraded: <upstream>`（对齐 §6.3）。
- 删除 `chat.py:169-195` 的硬编码智谱降级，并入通用链。

**P1-4 观测数据真实化**

- `/v1/models/stats`、`/v1/models/errors`、`/v1/router/stats` 全部改读 ModelRouter 真实 EWMA/错误数据；`/ws/monitor` 改推 `router.snapshot()`。
- Grafana 两个预置 dashboard（`core/config/grafana/dashboards/`）字段对齐真实指标名。

**验收（含自动化）**：
- pytest 故障注入矩阵：上游 A 连续 3×500 → 断言请求切到 B 且 A 被摘除 → 30s 后（mock 时间）半开恢复；
- 降级链全断 → 最终落云 API 且带 degraded 头；
- 手工验收：本机 env 指向 NAS 网关 + N1 Ollama 真实地址，`/v1/chat/completions` 走通双 DGX。

**依赖**：P0-1。设备侧无依赖（用 mock 即可验收；真机联调随时可做）。

---

### Phase 2 · API 契约补齐 + E2E 收敛（2-3 天）

**P2-1 四个代理端点**（全部走「认证 → 限流 → 上游池按 capability 选路 → 转发」的同一模式）

| 端点 | 上游 capability | 说明 |
|------|----------------|------|
| `POST /v1/embeddings` | embedding（TEI :8100） | OpenAI 格式透传，内部 RAG 改走同一入口 |
| `POST /v1/rerank` | rerank（TEI :8101） | Cohere/Jina 风格请求体 |
| `POST /v1/audio/transcriptions` | asr（:8004） | multipart 转发 |
| `POST /v1/ocr` | ocr（:8001） | 图片/文档转发 |

**P2-2 E2E 收敛**：保留 **Playwright**（覆盖更全 + 有基础设施测试），移除 Cypress（与其重复测同一批 API）；Playwright `baseURL` 参数化（`PLAYWRIGHT_BASE_URL` env，默认 staging 而非生产）；清掉 failed 历史截图目录。

**验收**：`test:all` 绿；4 个新端点各有 happy path + 401 用例。

**依赖**：P1-1（复用 capability 选路）。设备侧：TEI/OCR/ASR 服务在线才能真机验收（mock 验收不受阻）。

---

### Phase 3 · 部署与运维闭环（2-3 天）

**P3-1 ECS 主网关副本对齐**：CI `deploy-production` 的 5 节点矩阵与实际部署方式（`scripts/deploy.sh` / `deploy-nas-gateway.sh`）统一——现状 CI 假设 `/opt/yyc3/production` + compose pull，与真实 ECS 部署（`/root/yyc3-api-world/ecs_deploy.sh`，架构文档 §十二 P1）不一致。以本仓库 `Dockerfile` 产物 + `scripts/deploy.sh` 为唯一部署通道，CI 修正为调用它。
**P3-2 NAS 配置修复的仓库侧落点**：架构文档 RB-10（NAS Gateway Ollama 指向 N1）本质是 `.env` 修正——本仓库交付 `deploy/nas/gateway.env.example` 更新版（OLLAMA_HOST=100.65.64.49 + 上游池段落）+ 部署脚本新增「上游可达性预检」（部署前 curl 各上游 health_path，失败警告不阻断）。
**P3-3 CI 修复**：`db-migrate` 占位 target（CI migrate job 在调用它）→ 实现最小 Alembic 迁移或移除该 job；Makefile docker target 修复已在 P0-2 完成。
**P3-4 治理中枢对接（可延后）**：Token 预算审计上报 :25700——接口留桩 + env 开关，待 N2 治理中枢 systemd 化（架构文档 P0 设备侧任务）后联调。

**验收**：ECS + NAS 双网关从同一镜像/脚本部署；CI 全链路（lint→test→build→deploy→verify）绿。

---

## 四、执行顺序与依赖图

```
P0-1 配置体系 ──┬──> P1-1 Registry+兼容客户端 ──> P1-2 路由接线 ──> P1-3 熔断+降级 ──> P1-4 观测真实化
P0-2 清理      │                                                        │
P0-3 测试地基 ──┘                                                        └──> P2-1 代理端点 ──> P2-2 E2E收敛 ──> P3 部署闭环
```

- P0 三项可并行（不同文件域）；P1 内部严格串行；P2/P3 可穿插。
- 每个 Phase 合入即打 tag 部署到 NAS 备网关先行验证，再上 ECS 主网关（与架构文档「NAS 备先行」的主备策略一致）。

## 五、风险与对策

| 风险 | 概率 | 对策 |
|------|------|------|
| 路由接线引入 chat 回归（最高流量端点） | 中 | P1-2 保留旧 `_select_backend` 为第一优先级路径，上游池未配置时行为 100% 兼容；灰度开关 `ROUTER_ENABLED` |
| 云适配器基址外部化后 NAS 旧 .env 缺项 | 低 | 所有 base_url 默认值 = 现硬编码值，缺 env 不变行为 |
| 双 DGX 真机联调被设备侧阻塞（NIM 未起/端口冲突） | 中 | Phase 1 验收全用 mock；真机联调独立排期，不阻塞代码合入 |
| 上游 JSON env 配置写错导致网关起不来 | 低 | 启动时 schema 校验（pydantic parse）+ 失败仅告警降级为空池，不 crash |
| 测试重建期间 CI 覆盖率门槛卡住合入 | 低 | P0-3 同步下调门槛至现实值，路线图写明回升计划（P1 后 55%→70%） |

## 六、与架构文档 §十二（P0-P3）的映射

| 架构文档任务 | 本方案对应 | 备注 |
|-------------|-----------|------|
| （设备侧）Agent systemd 化 | — | 不在本仓库，仅注意治理中枢对接桩 P3-4 |
| NAS Gateway Ollama 指向 N1（RB-10） | P3-2 | 仓库交付配置模板 + 预检 |
| ECS Gateway 副本双活 | P3-1 | 部署通道统一 |
| 监控栈启动（ECS compose） | P1-4（数据侧） | compose 启动在 ECS 设备侧 |
| 守护三层安全管线挂接 | 未纳入（建议 Phase 4 候选） | 依赖 N1 Safety 服务 :8103 在线 |
| 智能路由质量决定集群可用性（ADR-4 结论） | **Phase 1 全部** | 本方案核心 |

## 七、里程碑

| 里程碑 | 内容 | 完成标志 |
|--------|------|---------|
| M1（P0 完） | 配置驱动 + 死代码清零 + 真实测试跑通 | `make ci` 本地全绿，无硬编码地址 |
| M2（P1 完） | 智能路由上线：EWMA + 熔断 + 降级链 + 真实观测 | 故障注入测试绿；NAS 备网关真机走通一次双上游切换 |
| M3（P2 完） | 7 端点契约齐 + E2E 单框架 | `/v1/embeddings /rerank /audio/transcriptions /ocr` 可用 |
| M4（P3 完） | ECS+NAS 同源部署 + CI 全绿 | 生产入口回归 api.0379.world 200 |

---

> **YYC³ AI Family** | 言启象限 · 语枢未来
> 本方案由代码级证据支撑（所有结论附 文件:行号），可直接作为开发排期输入
> 🌹 人从众曌众从人 · 亦师亦友亦伯乐
