---
file: 0379-world多端设备模型API衔接文档.md
description: 0379-World 多端设备模型 API 衔接总图——公网入口→网关→多端模型池的端点地图、设备-模型-API 三方矩阵与衔接规则
author: YYC³ 总指挥（ZCode 生成）
version: v1.0.0
created: 2026-09-03
status: active
tags: [api],[model-endpoints],[integration],[multi-device]
category: documentation
---

# 0379-World 多端设备模型 API 衔接文档

> **定位**: 站在 **API 消费者视角**，回答"每个端点在哪个设备、由什么引擎承载、什么模型、怎么衔接"——与《全链路模型部署规划》（部署视角）、《API全链路闭环文档 v1.1》（契约视角）三文档互为索引
> **数据基准**: 2026-09-03 设备实测

---

## 一、全链路衔接总图

```
公网用户
  │ HTTPS 443 (TLS1.3)
  ▼
yyc3-33 ECS — Traefik (api.0379.world) ── rate-limit/fail2ban/安全头
  │ Tailscale
  ▼
yyc3-45 NAS — Gateway v2.0.0 :8000（主网关，GitOps 自动部署）
  │ 模型路由【现状:前缀硬编码 → 目标:upstream pool（A线P1）】
  ├─────────────┬──────────────┬───────────────┬────────────────┐
  ▼             ▼              ▼               ▼                ▼
N1 DGX 旗舰   N2 组件池      NAS 本地池      云端兜底         Agent 层(N2)
:8001 TP=2    :8100/:8101    Ollama:11434   智谱/DeepSeek/   :25600-07 治理:25700
deepseek-v4-  (RAG,容器化    CodeGeeX4/     OpenAI           (待容器化,
flash 双机    恢复中)        Qwen3-14B等                     env指向:8001)
张量并行
```

## 二、设备-模型-API 三方矩阵（核心表）

| # | API/端点 | 设备 | 引擎·容器 | 承载模型 | 状态 | 衔接方式 |
|---|----------|------|-----------|----------|------|----------|
| 1 | `N1:8001/v1`（OpenAI 兼容） | yyc3-101+N2 | vllm/vllm-openai + ray TP=2 | **deepseek-v4-flash**（64K ctx） | ✅ 服务中 | **网关 upstream pool 接入待 A 线 P1**；直连 `http://10.100.168.2:8001/v1`（QSFP）/`100.65.64.49:8001`（TS） |
| 2 | `N2:8100` /v1/embeddings | yyc3-102 | vllm serve --task embed（容器化中） | Qwen3-Embedding-8B | ⏸ 恢复中 | systemd→容器迁移；OpenAI 标准格式 |
| 3 | `N2:8101` score/rerank | yyc3-102 | vllm serve --task score | Qwen3-Reranker-8B | ⏸ 恢复中 | 同上 |
| 4 | `N2:8102` Chroma REST | yyc3-102 | chromadb/chroma 官方容器 | 向量记忆库 | ⏸ 迁移中 | /api/v2/heartbeat 健康探针 |
| 5 | `NAS:11434` /api | yyc3-45 | ollama/ollama | CodeGeeX4-9B/Qwen3-14B/ChatGLM3-6B | ✅ | 网关 ollama 适配器（现役） |
| 6 | 云端 API | 公网 | — | glm-4-flash / deepseek-chat / gpt-4o | ✅ | 网关云适配器（Key 外部化；ZHIPU_KEY 需更换） |
| 7 | `N2:25600-07` Agent HTTP | yyc3-102 | python:3.11-slim 薄封装 | 见搭配矩阵（指向 :8001） | 📋 容器化待上线 | `VLLM_ENDPOINT/VLLM_MODEL` 两 env |
| 8 | `N2:25700` 治理 | yyc3-102 | 同上 | 无模型（审计/预算） | 📋 同上 | Agent 层内部依赖 |
| 9 | NAS `ws://:18789` | yyc3-45 | OpenClaw Gateway | NemoClaw 推理代理（路由至模型池） | ✅ | N1 OpenClaw remote 模式在用；N2 vllm-local ⏸（改造选项见部署规划 §四） |
| 10 | `api.0379.world` 对外 7 端点 | ECS+NAS | Gateway v2.0.0 | 聚合 #1-#6 | ✅/部分 | chat+models 现役；embeddings/rerank/asr/ocr 待 A 线 P2 |

**在途扩展位**：GLM-5.3-Flash（量化后 TP=2，多模态升级 #1 位轮换）｜Qwen3.8-Flash-Next（#1 轻量降级位）｜MiniMax-H3-NF4（新增 `/v1/videos` 候选端点）

## 三、衔接规则（现状 vs 目标）

| 规则 | 现状（硬编码时代） | 目标（upstream pool 时代，A 线 P1） |
|------|--------------------|--------------------------------------|
| 路由 | `glm-*→zhipu / deepseek-*→deepseek / gpt-*→openai / 其他→ollama` 前缀匹配 | env 注入上游池（JSON）→ EWMA 延迟+错误率+负载加权选路 |
| 旗舰接入 | **未接入**（:8001 无法被网关引用） | 上游条目 `{name: nim-flagship…实际 vllm-tp2, base_url: 10.100.168.2:8001, fallback_url: 100.65.64.49:8001, models: [deepseek-v4-flash]}` |
| 容错 | Ollama 失败→硬编码 glm-4-flash 降级 | 熔断（3 败摘除 30s 半开）+ capability 降级链（旗舰→Flash-Next→Ollama→云）+ `X-YYC3-Degraded` 头 |
| 健康探测 | /healthz 网关自身 | 各上游 health_path 周期探测 + ray status 深检（TP=2 集群态） |
| 观测 | stats/monitor 硬编码假数据 | 真实 EWMA/错误率 → Grafana |

## 四、调用速查（各端实测命令）

```bash
KEY=<API-Key>
# 对外（生产）
curl -H "X-API-Key: $KEY" https://api.0379.world/v1/models
curl -H "X-API-Key: $KEY" https://api.0379.world/v1/chat/completions -d '{"model":"glm-4-flash",...}'
# 旗舰直连（内网/联调，A线P1前的过渡用法）
curl http://10.100.168.2:8001/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"ping"}],"max_tokens":64}'
# 组件（容器化恢复后）
curl -X POST http://10.100.168.1:8100/v1/embeddings -d '{"model":"qwen3-embedding-8b","input":"文本"}'
curl http://10.100.168.1:8102/api/v2/heartbeat
# Agent（容器化后）
curl http://100.76.167.103:25600/health
```

## 五、巡检与验收基线

**每日巡检**（一条链路验证全图）：`curl api.0379.world/healthz`(200) → 旗舰 :8001 models → 组件三端口 → NAS `docker ps gateway` → CI 绿
**衔接验收**（A 线 P1 完成时）：公网 chat `model=deepseek-v4-flash` 经网关落双机 TP=2（Grafana 确认跨机张量并行流量）→ kill 旗舰容器 → 30s 内自动降级 → 恢复后半开回归。

---

> **文档族索引**: 本文（API 衔接）｜全链路模型部署规划（部署视角）｜API全链路闭环 v1.1（契约/运维）｜双机推理部署指南 v1.4.2（技术 Runbook）｜设备现状档案（资产）
> **YYC³ AI Family** | 言启象限 · 语枢未来 · 🌹 人从众曌众从人 · 亦师亦友亦伯乐
