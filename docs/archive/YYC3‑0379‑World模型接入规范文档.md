# YYC³‑0379‑World 模型接入规范文档

**文档版本**：v2.3.0‑20260927
**归属项目**：YYC³‑0379‑World 全链路AI模型网关 · 智能协同平台
**适用对象**：运维、部署、模型研发、CI/CD流水线
**前置背景**：本规范适配现有架构：NAS `/Volume1/yyc3_hd/data` 作为**统一模型资产仓库**；算力节点包含DGX‑N1/N2、yyc3‑22(Mac M4 Max)；网关基于FastAPI，上游池机制`OPENAI_COMPATIBLE_UPSTREAMS`，OpenAI兼容协议；配套YYC³ AI Family Agent平台；遵循五维驱动、五高五标五化体系。

> 目的：统一本地HF/vLLM模型资产接入API网关全流程，实现**模型标准化入库、动态注册发现、零停机版本切换、版本回滚、状态监控告警**；新增/更新模型无需修改网关业务代码。

## 修订记录

|版本|日期|变更人|变更说明|
|---|---|---|---|
|v2.3.0‑20260927|2026‑09‑27|YanYuCloudCube Team|初始交付版本，对齐生产v2.3.0实况，对接NAS模型仓库、DGX推理池、Mac Runner|

## 目录

1. [概述](#1-概述)
2. [术语定义](#2-术语定义)
3. [模型资产仓库规范（NAS层）](#3-模型资产仓库规范nas层)
4. [模型元数据标准](#4-模型元数据标准)
5. [后端模型服务部署规范（vLLM）](#5-后端模型服务部署规范vllm)
6. [模型注册与发现机制](#6-模型注册与发现机制)
7. [API网关上游池配置规则](#7-api网关上游池配置规则)
8. [模型上线、版本切换、回滚完整流程](#8-模型上线版本切换回滚完整流程)
9. [健康检查、监控与告警规范](#9-健康检查监控与告警规范)
10. [模型接入验收冒烟测试用例](#10-模型接入验收冒烟测试用例)
11. [容量与约束说明](#11-容量与约束说明)
12. [故障排查清单](#12-故障排查清单)
13. [附录](#13-附录)

---

## 1. 概述

### 1.1 范围

本规范定义从NAS模型资产仓库，到算力节点部署vLLM推理服务，再到YYC³‑0379‑World网关动态注册、公网OpenAPI对外暴露完整流程。
包含：

- NAS模型文件存储、完整性校验标准
- 模型元数据Schema定义
- vLLM后端服务部署约束
- 动态注册、自动发现机制
- 模型上线、热切换、版本回滚操作流程
- 监控告警、冒烟验收、故障排查

> **重要架构约束**
>
> 1. **API网关不加载权重文件**，网关仅做鉴权、限流、路由转发、可观测；权重全部由后端vLLM服务加载。
> 2. NAS `/Volume1` 仅作为**只读资产仓库**；生产推理优先使用算力节点本地SSD缓存模型；挂载NFS仅用于调试，禁止高并发生产推理直接NFS读取权重。
> 3. 所有后端推理服务必须实现**OpenAI兼容接口契约**，网关不做模型业务适配。

### 1.2 设计目标

1. 标准化：新增HF格式模型，遵循规范即可接入，无需修改网关代码。
2. 自动化：新模型部署完成后自动注册，网关自动感知更新路由。
3. 高可用：支持**不中断公网API服务**完成模型版本切换、灰度、回滚。
4. 可观测：全链路状态监控，加载异常、熔断、延迟超标自动告警。
5. 可审计：模型上线、切换、下线全部操作留日志，可追溯。

### 1.3 引用文档

1. YYC³‑0379‑World README.md v2.3.0
2. docs/架构与部署/API全链路闭环文档.md
3. docs/架构与部署/CI‑CD部署配置指南.md
4. YYC3‑Models‑资产详情.md（NAS、DGX、Mac模型资产清单）

## 2. 术语定义

|术语|说明|
|---|---|
|模型资产仓库|NAS `/Volume1/yyc3_hd/data`，存放原版HF模型，统一备份、完整性校验，**只读**，禁止推理业务直接读取（生产）|
|模型实例|某算力节点上运行的vLLM服务实例，绑定一个模型版本，拥有独立`endpoint`（内网HTTP地址）|
|model_id|全局唯一标识，格式：`{模型名}-{版本标记}`，例：`qwen3.8‑flash‑next‑v1`|
|model_alias|模型别名，公网API调用使用，一个别名可映射不同model_id，用于版本切换；例：`qwen3.8‑flash‑next`|
|上游池|网关环境变量`OPENAI_COMPATIBLE_UPSTREAMS`维护后端推理服务池，支持fnmatch模型匹配、熔断、降级|
|注册Agent|部署在算力节点侧代理脚本；vLLM就绪后，把模型元数据写入Redis/PostgreSQL注册中心，持续上报心跳TTL|
|draining状态|排空状态：不再接收新流量，等待存量SSE/流式请求完成后下线实例，用于热切换|

## 3. 模型资产仓库规范（NAS层）
>
> 路径根目录：`/Volume1/yyc3_hd/data/`
>
### 3.1 目录组织规范

```
/Volume1/yyc3_hd/data/
├─Qwen/                 # Qwen系列全部HF模型
├─DeepSeek/             # DeepSeek系列
├─GLM/                  # GLM系列
├─MiniCPM‑V‑4.6/        # 多模态
└─…其他模型家族
```

每个模型版本独立`snapshots/{版本标识}`目录，参考示例：
`/Volume1/yyc3_hd/data/Qwen/Qwen3.8‑Flash‑Next/snapshots/master`

### 3.2 文件要求（HF标准模型）

必须包含以下文件，缺失则判定资产不完整：

- `config.json`、`generation_config.json`
- `tokenizer.json`、`tokenizer_config.json`、`vocab.json`、`merges.txt`
- `chat_template.jinja`
- `model.safetensors.index.json` + 全部分片`model‑xxxx‑of‑xxxxx.safetensors`
- LICENSE、README.md（可选，建议保留）

### 3.3 模型完整性校验（入库必做）

模型放入NAS仓库后，**必须执行完整性校验脚本**，输出校验报告，保存至模型目录`model_checksum.report`。
校验项：

1. 统计safetensors分片数量，与`model.safetensors.index.json`权重映射清单比对，确认无缺失文件。
2. safetensors文件头部校验，识别文件截断、损坏。
3. tokenizer、config配置文件存在性校验。

> 脚本参考项目仓库：`core/scripts/model_asset_verify.py`
> 校验失败模型禁止上线到API网关。

### 3.4 模型分发策略（重要）

1. **调试场景**：算力节点NFS只读挂载NAS模型目录，直接加载。仅用于开发测试。
2. **生产场景**：算力节点执行增量同步脚本，把NAS原版模型同步到节点本地NVMe SSD；vLLM读取本地SSD路径，规避NFS IO抖动、mmap不稳定问题。
3. NAS仓库永远只读，**不在挂载客户端做模型修改**；模型更新只在NAS本机执行，更新后重新完整性校验。

## 4. 模型元数据标准
>
> 模型元数据是网关路由、监控、版本管理的唯一数据源。
> 模型元数据文件：每个模型版本目录存放`model‑meta.json`；注册Agent读取该文件上报注册中心。

### 4.1 model‑meta.json Schema

```json
{
  "model_id": "qwen3.8‑flash‑next‑v1",
  "model_name": "Qwen3.8‑Flash‑Next",
  "version": "v1",
  "alias": ["qwen3.8‑flash‑next"],
  "asset_nas_path": "/Volume1/yyc3_hd/data/Qwen/Qwen3.8‑Flash‑Next/snapshots/master",
  "backend_local_path": "/home/yyc3/models/Qwen3.8‑Flash‑Next",
  "backend": "vllm",
  "backend_endpoint": "http://10.0.0.101:8000/v1",
  "device_tag": "dgx‑n1",
  "model_type": "chat",
  "state": "offline",
  "max_context_len": 32768,
  "max_batch_size": 256,
  "gpu_memory_require_gb": 40,
  "default_params": {
    "temperature": 0.7,
    "top_p": 0.95
  },
  "performance_baseline": {
    "tps_avg": 120,
    "latency_p50_ms": 180
  },
  "tags": ["qwen","chat"],
  "created_at": "2026‑09‑27T00:00:00Z",
  "updated_at": "2026‑09‑27T00:00:00Z",
  "checksum_report_path": "./model_checksum.report"
}
```

|字段|说明|允许值|
|---|---|---|
|model_id|全局唯一ID，不可重复|字符串 `模型名‑版本`|
|alias|公网API调用别名，支持多个别名|数组；版本切换修改别名指向不同model_id|
|asset_nas_path|NAS仓库原始资产路径|绝对路径|
|backend_local_path|算力节点本地SSD路径，生产环境vLLM读取路径|绝对路径|
|backend_endpoint|vLLM服务内网地址，网关转发目标|`http://ip:port/v1`|
|device_tag|算力节点标记|`dgx‑n1`/`dgx‑n2`/`yyc3‑22‑mac`|
|model_type|模型能力类型|`chat`/`embedding`/`rerank`/`asr`/`vlm`|
|state|模型实例状态机|`offline`(离线)/`loading`(加载权重)/`ready`(接收流量)/`draining`(排空待下线)|
|max_context_len|模型最大上下文窗口|整数，来源于config.json|
|gpu_memory_require_gb|运行该模型最低显存需求|浮点，用于算力调度参考|

> 状态机流转：`offline → loading → ready → draining → offline`

### 4.2 注册中心存储

元数据同时两份存储：

1. PostgreSQL ModelRegistry表：持久存储所有模型版本、变更历史、操作审计日志。
2. Redis：内存缓存，网关实时订阅读取，实现无重启更新路由。

## 5. 后端模型服务部署规范（vLLM）
>
> 所有本地模型后端统一使用vLLM，输出OpenAI兼容接口。
>
### 5.1 启动强制约束

1. 生产模式必须读取**算力节点本地SSD路径**，禁止直接NFS挂载路径运行生产流量。
2. 必须开启健康检查端点`/health`；返回JSON包含：加载状态、GPU显存占用、队列长度。
3. 必须启用`/v1/models`端点，返回自身模型信息。
4. 不同模型实例**必须使用独立端口**，容器隔离，一个实例OOM不影响其他实例。
5. 禁止公网直接暴露vLLM端口；只允许内网访问；公网流量全部经过YYC³网关转发。

### 5.2 vLLM最小启动模板示例

```bash
vllm serve /home/yyc3/models/Qwen3.8‑Flash‑Next \
  --model qwen3.8‑flash‑next‑v1 \
  --port 8000 \
  --host 0.0.0.0 \
  --max‑model‑len 32768 \
  --trust‑remote‑code True
```

### 5.3 注册Agent工作流程

1. vLLM启动，开始加载权重，状态置为`loading`；Agent持续轮询`/health`。
2. vLLM权重加载完成，`/health`返回ready状态。
3. Agent读取模型目录`model‑meta.json`，填充运行时信息，上报注册中心PostgreSQL+Redis，状态更新为`ready`。
4. Agent每5s上报一次心跳TTL；心跳超时30s，注册中心自动将实例置为`offline`，网关自动摘除该上游。

> 两种注册方式：
> ①自动注册（推荐）：vLLM容器启动后自动拉起Agent完成注册。
> ②手动注册：管理后台录入model‑meta信息，用于临时测试模型。

## 6. 模型注册与发现机制

1. **事件驱动发现**：网关订阅Redis模型元数据变更事件；模型注册/更新/下线，网关**不需要重启**，内存路由表自动刷新。
2. `/v1/models`公网接口返回可用模型列表，数据源来自注册中心。
3. 网关收到API请求，读取请求参数`model`字段，优先匹配`alias`，解析得到`model_id`，再映射到对应后端`backend_endpoint`。
4. 同一个model_id支持多实例部署（多算力节点做负载均衡），网关内置自适应EWMA负载均衡。

> ⚠️注意：`OPENAI_COMPATIBLE_UPSTREAMS`环境变量为兼容旧版上游配置；新模型优先走注册中心动态注册。

## 7. API网关上游池配置规则

1. 旧模式：环境变量`OPENAI_COMPATIBLE_UPSTREAMS`JSON数组配置上游，适合静态配置。
2. 新模式（推荐用于新增模型）：动态注册中心，模型实例上线自动加入上游池，下线自动摘除。
3. 熔断规则沿用生产现有逻辑：连续3次失败，实例摘除30s半开模式；错误率>15%自动降级。
4. 响应头契约保留：`X‑YYC3‑Upstream`标记实际处理请求的后端实例；`X‑YYC3‑Degraded`标记是否降级。

## 8. 模型上线、版本切换、回滚完整流程

### 8.1 新模型上线流程

1. **资产入库**：模型完整文件放入NAS模型仓库；运行完整性校验脚本，生成`model_checksum.report`。
2. **元数据编写**：编写`model‑meta.json`，填写model_id、alias、参数、显存需求。
3. **算力节点同步**：通过同步脚本，把NAS模型增量同步至算力节点本地NVMe SSD。
4. **启动vLLM实例**，启动配套注册Agent。
5. Agent检测vLLM就绪，自动注册，状态变为`ready`，网关自动发现该模型。
6. **冒烟验收测试**，通过验收用例。
7. 开放公网访问。

### 8.2 无缝版本切换（不中断API服务）
>
> 场景：把别名`qwen3.8‑flash‑next`由v1切换到v2新版本。

1. 在算力节点部署新版本v2模型实例，注册进入注册中心，状态`ready`；此时**别名不指向新版本，不接收公网流量**。
2. 执行冒烟测试验证新版本功能正常。
3. 在管理后台/API接口修改别名映射：将`qwen3.8‑flash‑next`别名从`v1(model_id)`指向`v2(model_id)`。
4. Redis推送变更事件，网关内存路由表实时更新；**新请求路由新版本；存量SSE长连接继续在旧实例完成**。
5. 将旧版本实例状态置为`draining`；等待所有活跃请求全部结束。
6. 确认流量排空后，可下线旧v1实例；保留版本记录用于回滚。

> 接口：后台可调用内部接口 `/internal/model/alias/switch` 完成别名切换；所有操作写入审计日志。

### 8.3 版本回滚

1. 触发条件：新版本出现异常，需要快速切回旧版本。
2. 操作：将模型别名重新指向旧版本`model_id`。网关立刻切换流量到旧实例。
3. 回滚不需要重启网关；记录回滚操作日志，告警通知运维。

### 8.4 模型下线

1. 将实例置为`draining`；等待活跃请求排空。
2. 修改alias移除该model_id；状态更新为`offline`。
3. Agent停止心跳上报；网关自动摘除上游。
4. NAS仓库模型资产保留（归档，不删除，便于重新上线）。

## 9. 健康检查、监控与告警规范

### 9.1 三层健康检查

1. **网关层**：`/healthz`轻量存活探针；`/health`完整健康检查。
2. **模型实例层（vLLM）**：`/health`端点；Agent每5s采集。
3. **注册中心层**：心跳TTL，超时自动离线。

### 9.2 核心监控指标

采集到Prometheus：

|指标|说明|告警阈值参考|
|---|---|---|
|`model_backend_latency_ms`|模型推理延迟p95|p95>2000ms告警|
|`model_backend_error_rate`|模型后端错误率|>10%告警|
|`active_requests`|模型实例并发请求|超过max_batch_size告警|
|`gpu_utilization`|GPU利用率|>95%持续5min告警|
|`gpu_memory_used`|显存占用|超过90%告警|
|`model_instance_heartbeat_status`|实例心跳状态|心跳丢失触发告警|

### 9.3 告警渠道

- Grafana告警；推送通知运维；记录告警事件日志入库。
告警场景：模型加载超时、心跳丢失、错误率突增、显存溢出、推理延迟飙升。

## 10. 模型接入验收冒烟测试用例
>
> 模型上线必须全部通过冒烟测试，才可开放公网流量。

1. ✅ 模型资产完整性校验：无缺失分片、无损坏safetensors。
2. ✅ vLLM服务启动成功，`/health`返回ready。
3. ✅ Agent注册成功，`/v1/models`接口可查询该model_id与alias。
4. ✅ 基础chat推理调用（同步）返回正常JSON。
5. ✅ SSE流式推理调用，验证chunk输出正常。
6. ✅ 校验响应头`X‑YYC3‑Upstream`指向正确后端实例。
7. ✅ 异常边界：超过max_context_len请求返回正确错误码。
8. ✅ 多模态模型（VL/ASR/Rerank）执行对应能力冒烟。
9. ✅ 版本切换冒烟：别名切换，验证流量路由新版本；回滚验证。

## 11. 容量与约束说明

1. **注册中心可管理模型版本**：PostgreSQL+Redis层面可管理数百个模型版本；可以大量处于`offline`归档状态。
2. **同时在线提供服务模型数量**：受算力GPU显存硬约束，网关本身不限制数量。
3. 区分两个概念：
    - **注册模型版本数**：系统登记管理的全部模型版本（含离线归档）
    - **在线实例数**：加载到GPU显存，对外提供推理的实例，受DGX/Mac硬件限制。
4. 业务建议：高频模型常驻显存；低频模型使用按需加载策略，空闲超时卸载。

## 12. 故障排查清单

|现象|排查点|
|---|---|
|新模型注册后，公网/v1/models看不到|1.Agent是否成功上报；2.Redis事件是否推送；3.model‑meta.json字段是否合法；4.检查state是否为ready|
|调用模型返回503上游不可用|1.实例心跳是否超时；2.vLLM `/health`是否正常；3.检查是否被熔断摘除；4.网络连通性|
|模型冷启动加载极慢|生产环境是否直接NFS挂载；切换到本地SSD缓存模型|
|版本别名切换后流量没有更新|确认Redis事件推送，网关是否订阅变更；可调用网关内部接口刷新路由缓存|
|safetensors文件报错invalid header|NAS仓库运行完整性校验脚本，分片损坏，重新同步该分片|

## 13. 附录

### 附录A 目录脚本索引

|脚本路径|用途|
|---|---|
|`core/scripts/model_asset_verify.py`|NAS模型资产完整性校验|
|`core/scripts/model_sync_to_node.py`|NAS仓库 → 算力节点本地SSD增量同步脚本|
|`core/scripts/model_register_agent.py`|算力节点注册Agent，上报元数据与心跳|
|`tests/e2e/model_smoke_test.py`|模型上线冒烟测试脚本|

### 附录B 调用示例

```bash
# 查看公网可用模型列表
curl -H "X‑API‑Key:${API_KEY}" https://api.0379.world/v1/models

# 调用新接入模型（使用别名）
curl -X POST https://api.0379.world/v1/chat/completions \
‑H "Content‑Type: application/json" \
‑H "X‑API‑Key:${API_KEY}" \
‑d '{
    "model":"qwen3.8‑flash‑next",
    "messages":[{"role":"user","content":"你好"}]
}'
```

---

> **版权声明**：YYC³‑0379‑World · YanYuCloudCube Team，遵循MIT开源许可；本文档为运维交付文档，随项目版本迭代更新。
