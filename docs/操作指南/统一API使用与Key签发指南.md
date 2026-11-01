---
file: 统一API使用与Key签发指南.md
description: YYC³ 统一模型网关——三入口/认证/Key 签发生命周期/模型目录（实矩阵真值）/能力端点/运维体检/故障排查
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-11-02
updated: 2026-11-02
status: active
tags: [api],[virtual-key],[ops],[guide]
category: 操作指南
language: zh-CN
---

# 统一 API 使用与 Key 签发指南

> **定位**: 消费者视角的一站式指南——一个网关、一套认证、全部模型。所有结论来自 **2026-11-02 实弹矩阵**（`scripts/ops_model_matrix.py` 实调判据），非纸面罗列。
> **配套脚本**: `scripts/ops_vkey.py`（Key 生命周期）· `scripts/ops_model_matrix.py`（全量体检）

---

## 一、三个入口（同一网关，同一把 Key）

| 入口 | 基址 | 适用 |
|---|---|---|
| 局域网 | `http://192.168.3.45:8000` | 家内低延迟 |
| Tailscale | `http://100.65.172.88:8000` | 外出/跨设备（推荐日常用） |
| 公网 | `https://api.0379.world` | 外部服务回调（经 ECS Traefik） |

> 区分：TS 家臣线另有 `http://100.126.132.112:10086/v1`（aify 网关，`/v1` 免 key）——那是**消费端专线**；本指南的统一 API 指 NAS FastAPI 网关（本仓）。

## 二、认证（30 秒上手）

所有业务端点只认一个头：

```bash
curl -H "X-API-Key: <你的Key>" https://api.0379.world/v1/models
```

Key 分两类，权限不同：

| 类 | 形态 | 来源 | 能力 |
|---|---|---|---|
| **静态 Key** | `sk-...`（env `API_KEYS`，逗号分隔多把） | 网关 .env，改需重启 | 全模型直通；**兼管理面**（若 `ADMIN_API_KEYS` 未配） |
| **虚拟密钥 vk** ✅推荐 | `vk-...`（签发生效，**免重启**） | 本指南 §四 | 白名单/月预算/TPM 限速/用量计量，可停用吊销 |

> **管理面分离**：`/v1/admin/**` 只认 `ADMIN_API_KEYS`（独立密钥；未配置时回退静态 Key）。业务 Key 打管理面一律 403。

## 三、模型目录（2026-11-02 实弹真值）

`GET /v1/models` 列出 11 项；实调矩阵真相如下——**引用前先看此表**：

### ✅ 现役可用（放心调用）

| 模型 | 能力 | 上游 | 实测 |
|---|---|---|---|
| `nemotron-3.5-super-vl` | chat 深推理/视觉/1M ctx | svl2 TP2（DGX 双机） | ✅ 秒级·content 实答（默认关思考）；**视觉可用**（content-parts 传 PNG，11-02 实测红圆计数正确） |
| `bge-m3`（已入 /v1/models，11-02 修复） | embeddings 1024 维 | 77 Ollama | ✅ dim=1024 |

### ❌ 已知死链（勿引用，待恢复）

| 模型 | 死因 | 恢复路径 |
|---|---|---|
| `qwen3-coder-30b` | 池内上游 77 Ollama 无此模型（U9 实勘：仅 bge-m3） | 77 侧补模型或改指 DGX |
| `family-coder` | mac-mlx :11435 服务停用（SERVICES §一） | MLX-v4 改造后复用 |
| `/v1/rerank` 全部 | rerank-nim-bge 上游 404（77 无 bge-reranker；N1 rerank 容器按需停用中） | `OPS/定义/yyc3-n1-rerank-8b/rerank-按需.sh` 或 77 补模型 |
| `super-vl`（短别名） | 前缀匹配进 svl2 上游但模型名不被识别 → 500 | **用全名 `nemotron-3.5-super-vl`** |

### ☁️ 云依赖（自用不上云红线，默认封存）

`glm-4-flash` / `glm-4-plus` / `deepseek-chat` / `deepseek-coder`——云适配器通道在但 key 未配/过期（500）。**红线期间不补 key、不作为可用容量规划**。

## 四、Key 签发生命周期（vk）

### 4.1 一分钟签发

```bash
export YYC3_ADMIN_KEY=<管理密钥>     # ADMIN_API_KEYS 首把
python3 scripts/ops_vkey.py issue \
  --name ts-family --owner "TS仓" --budget 5 --tpm 60000 \
  --whitelist "nemotron-3.5-super-vl,qwen3-coder-30b"
# ✅ 输出明文 vk-... —— 仅此一次，立即存入 ~/.yyc3-keybackup/（600）
```

### 4.2 语义（预算/限速/白名单如何生效）

| 维度 | 行为 |
|---|---|
| `model_whitelist` | 空=全模型；非空=**仅白名单内可调**，白名单外请求被拒（vk 闸） |
| `monthly_budget_usd` | 月累计花费超限 → 429（按 token 计价，`/v1/admin/pricing` 口径） |
| `rate_limit_tpm` | 每分钟 token 上限，超限 429 |
| 计量 | 每次调用累计到 key（`spent_usd`），看板与 usage 端点可查 |

### 4.3 日常运维（全部免重启）

```bash
python3 scripts/ops_vkey.py list                     # 总览（id/状态/用量/白名单）
python3 scripts/ops_vkey.py usage <key_id>           # 按模型/上游/能力用量明细
python3 scripts/ops_vkey.py patch <key_id> --status disabled    # 临时停用
python3 scripts/ops_vkey.py patch <key_id> --whitelist "nemotron-3.5-super-vl"
python3 scripts/ops_vkey.py revoke <key_id>          # 吊销（不可逆）
```

**网页看板**：`GET /v1/admin/dashboard`（管理 Key 访问）——列表/创建/启停/预算进度条/按模型用量，与脚本同源。

### 4.4 签发纪律（红线级）

1. 明文 Key **只在签发响应出现一次**——立即入 `~/.yyc3-keybackup/`（600），绝不进 git/日志/聊天记录；
2. 一消费者一把 Key（按 owner 隔离计量），禁止共享；
3. 对外发放一律 vk（预算+白名单+可吊销），静态 Key 只留给基础设施；
4. 离职/退役消费者 → `revoke` 而非改 env。

## 五、能力端点速查（统一 API 面）

```bash
KEY=<你的Key>; B=https://api.0379.world
# chat（OpenAI 兼容；stream 可选）
curl -s $B/v1/chat/completions -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"model":"nemotron-3.5-super-vl","messages":[{"role":"user","content":"你好"}],"max_tokens":256}'
# embeddings（1024 维）
curl -s $B/v1/embeddings -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"model":"bge-m3","input":"要向量化的文本"}'
# rerank（现役死链，恢复前勿依赖）
# asr / ocr（N1 让路停用中，端点在、上游未部署 → 502）
```

兼容性：chat/embeddings 为 OpenAI 兼容格式——openai SDK / LangChain / Dify 直接改 `base_url` + `api_key` 即用。

## 六、运维体检

```bash
# 全模型可用性矩阵（统一 API「可用」的机器判据；--json 走 stdout）
export YYC3_API_KEY=<业务key>
python3 scripts/ops_model_matrix.py
# 17 项全链自检（既有）
bash scripts/health-full.sh
# 网关自身
curl http://100.65.172.88:8000/healthz     # 存活
curl -H "X-API-Key: $KEY" http://100.65.172.88:8000/v1/models/stats   # 上游池真实 EWMA
```

## 七、故障排查速查

| 症状 | 根因 | 处置 |
|---|---|---|
| 401 | Key 缺/错 | 检查 `X-API-Key` 头；`ops_vkey.py list` 确认 vk 状态 active |
| 403 "Admin privileges required" | 业务 Key 打了 `/v1/admin/**` | 换管理密钥（ADMIN_API_KEYS） |
| 429 | vk 预算/TPM 触顶 | `usage` 查明细 → `patch` 调预算或等窗口 |
| 500 且白名单外模型 | vk 白名单闸 | `patch --whitelist` 加模型或换全模型 vk |
| 500 模型在列但报错 | 死链上游（见 §三 ❌ 表） | 按恢复路径处理后重试 |
| 502 "上游降级链全部失败" | 该 capability 无活上游（如 rerank） | 按 §三恢复路径起上游 |
| content=null·finish=length | 思考吃光预算 | 网关已默认关思考；确需思考用 `chat_template_kwargs` 显式开并加大 max_tokens |

## 八、变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0.0 | 2026-11-02 | 首版：三入口/双类 Key/vk 生命周期/实矩阵模型目录/体检与排障（配套 ops_vkey.py + ops_model_matrix.py） |

---

> **YYC³ AI Family** | 言启象限 · 语枢未来
> 本文模型目录为 2026-11-02 实弹快照——上游代际更替后以 `ops_model_matrix.py` 重跑结果为准
