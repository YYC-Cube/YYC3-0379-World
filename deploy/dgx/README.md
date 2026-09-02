# DGX 双机推理部署编排（yyc3-101 N1 / yyc3-102 N2）

依据 [DGX-Spark双机推理部署指南](../../docs/架构与部署/DGX-Spark双机推理部署指南.md) §5 / §9 / §12，将文档中的编排落为可执行文件。

## 文件

| 文件 | 用途 | 执行位置 |
|------|------|---------|
| `docker-compose-n1.yml` | A 方案 · N1 组件服务机（OCR/嵌入/重排/安全/ASR/路由 LLM/面板） | yyc3-101 |
| `docker-compose-n2.yml` | A 方案 · N2 旗舰推理机（DeepSeek NIM / Qwen-VL / Ollama） | yyc3-102 |
| `docker-compose-dgx-tp2.yml` | B 方案 · TP=2 张量并行（主推，需先过门禁） | 双机各一份，`RANK=0/1` 区分 |
| `scripts/verify-dgx-cluster.sh` | 部署前门禁：SSH/iperf3/拓扑 + NCCL all_reduce_perf 复测 | yyc3-101 |

## 部署顺序

```bash
# 1. 门禁验证（B 方案前置；NCCL 失败则维持 ADR-4 走 A 方案）
bash deploy/dgx/scripts/verify-dgx-cluster.sh

# 2. A 方案（服务级分工）
ssh yyc3-101 'docker compose -f deploy/dgx/docker-compose-n1.yml up -d'
ssh yyc3-102 'docker compose -f deploy/dgx/docker-compose-n2.yml up -d'

# 3. B 方案（TP=2，门禁通过后）：先 rank0 等 29500 监听，再起 rank1
ssh yyc3-101 'RANK=0 docker compose -f deploy/dgx/docker-compose-dgx-tp2.yml up -d'
ssh yyc3-102 'RANK=1 docker compose -f deploy/dgx/docker-compose-dgx-tp2.yml up -d'

# 4. 验收（指南 §12）
curl -s http://10.100.168.2:8000/v1/models
curl -X POST http://10.100.168.2:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-ai/deepseek-v4-flash","messages":[{"role":"user","content":"ping"}],"max_tokens":32}'
```

## 回滚

TP=2 任一异常（挂起 / `malloc -24GB` 根因复发）→ 停止 tp2 编排，`docker-compose-n2.yml` 单机 TP=1 秒级恢复（指南 §9.3 / §14.1）。

## 前提

- 双机 Docker + NVIDIA Container Toolkit（`--gpus all` 可用）
- 模型权重已挂载于 `/mnt/yyc3_hd/data/...`（见指南 §4 资产池）
- 集群 YanYuCloud（2 devices, direct connection）互联就绪（210.76 Gbps 实测留档）
