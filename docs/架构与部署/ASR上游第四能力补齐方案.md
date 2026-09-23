---
file: ASR上游第四能力补齐方案.md
description: /v1/audio/transcriptions 第四能力上游补齐——候选路线论证、推荐架构与落地步骤
author: YanYuCloudCube Team
version: v1.0.0
created: 2026-09-14
status: active
tags: [asr],[speech],[capability],[方案]
category: guide
---

# ASR 上游第四能力补齐方案（分析/论证/落地）

> 前置事实：网关端点 `/v1/audio/transcriptions` **已就绪**（`core/api/api/proxy.py` capability=asr，multipart 透传 + 熔断降级 + X-YYC3-Upstream 头），当前 502 仅因无上游。本文解决"上游选型→部署→池接入→公网验收"。

## 一、候选路线论证

| 路线 | 代表 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A. Qwen3-ASR 自建 | Qwen3-ASR-0.6B/1.7B（**N1 已在盘**） | 模型零下载；中文强；轻量(~4G) | 需自写 FastAPI 服务层（transformers pipeline 包装+ffmpeg）；非官方容器 | **备选**（中文精度优先时切换） |
| B. FunASR/SenseVoice | 阿里 SenseVoice-Small | 中文识别顶级；生态成熟 | 非 OpenAI 兼容（websocket 协议）需适配层；镜像国内拉取一般 | 备选 |
| C. faster-whisper 系 | `speaches` / faster-whisper-server | **OpenAI 兼容开箱即用**（/v1/audio/translations 原生）；whisper.cpp/GGUF 生态最全；int8 显存 ~3G | 中文略逊 SenseVoice | ✅ **首选** |
| D. NVIDIA NIM | Parakeet/Canary | 性能强 | **nvcr NIM 目录对 CN IP 封锁（实测 DENIED）** | ❌ 排除 |

**判定依据**：网关 proxy 的 asr 路径按 OpenAI Whisper 风格透传（`file` + `model` multipart）——路线 C 上游零适配；A/B 需在 N 侧加一层 OpenAI 兼容壳。优先 C 快速闭环，A 作为第二上游（池多上游降级天然支持）。

## 二、推荐架构

```
公网 /v1/audio/transcriptions → NAS 网关(proxy, capability=asr)
   → 上游池 asr-n2 (N2 :8004, speaches/whisper-large-v3, GPU int8 ~3G)
   → [降级位] asr-n1 (N1 :8004, Qwen3-ASR-1.7B 自建, 后续)
```

- **部署位 N2**（chroma 旁）：worker 0.72 后余量最大；与 Agents/Chroma 无 GPU 冲突（whisper int8 常驻 ~3G）
- 模型 `whisper-large-v3-turbo`（int8，~1.6G 权重，中文可接受）起步；质量不满足再升 large-v3 / 切路线 A

## 三、落地步骤（约 40 分钟）

```bash
# 1. N2 起容器（speaches：OpenAI 兼容 faster-whisper server；镜像走 daocloud）
docker run -d --name yyc3-asr --restart unless-stopped --gpus all -p 8004:8004 \
  -e SPEACHES__MODEL_ID=Systran/faster-whisper-large-v3-turbo \
  -e SPEACHES__ENABLE_WHISPER_API=1 \
  ghcr.io/speaches-ai/speaches:latest        # 若 ghcr 拉取失败换 daocloud 前缀

# 2. 本机验收（OpenAI 兼容）
curl http://127.0.0.1:8004/v1/models
curl -F file=@test.wav -F model=whisper-large-v3-turbo \
  http://127.0.0.1:8004/v1/audio/transcriptions

# 3. NAS 池注入（.env 的 OPENAI_COMPATIBLE_UPSTREAMS 追加）
{"name":"asr-n2","base_url":"http://100.76.167.103:8004","models":["whisper-large-v3-turbo","whisper*"],"capability":"asr","priority":1}

# 4. 网关重建 + 公网验收
bash /Volume2/yyc3-33/rebuild-gateway.sh
curl -F file=@test.wav -F model=whisper-large-v3-turbo -H "X-API-Key: $K" \
  https://api.0379.world/v1/audio/transcriptions   # 期待 X-YYC3-Upstream: asr-n2
```

## 四、风险与对策

| 风险 | 对策 |
|------|------|
| ghcr.io 国内拉取失败 | daocloud 前缀 `docker.m.daocloud.io/ghcr.io/...`；或 Mac 拉取 docker save | 
| speaches 首载下载模型（HF） | 容器内 HF_ENDPOINT=hf-mirror.com；或预挂模型目录 |
| N2 GPU 余量收紧（GLM 线重来） | ASR 容器降 CPU 模式（faster-whisper CPU int8 可用，延迟升高） |
| 中文精度不达标 | 池第二上游切路线 A（Qwen3-ASR-1.7B 在盘，写 ~80 行 FastAPI 壳） |

## 五、验收清单

- [ ] N2 :8004 /v1/models 200
- [ ] N2 本机转写中文 wav 出正确文本
- [ ] NAS 池 asr-n2 注入 + SMOKE_PASS
- [ ] 公网 /v1/audio/transcriptions 带 `X-YYC3-Upstream: asr-n2` 返回文本
- [ ] `/v1/models` 不出现 asr 模型（capability≠chat 过滤已内建 ✓）

> 第四能力闭环后，五能力仅剩 OCR（Nemotron-OCR 容器化，同模式 capability=ocr）与视频（见《MiniMax-H3 第五能力审核》异步任务 API）。
