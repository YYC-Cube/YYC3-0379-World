# TP=2 双机张量并行 · 已验证实操模式（ray 版，2026-09-02 实测通过）

> 与 `docker-compose-dgx-tp2.yml`（NIM 版）并存的**已验证路径**：无需 NIM/NGC 凭据，用官方
> `vllm/vllm-openai` 镜像 + 容器内 `pip install ray` 实现。实测：双节点 Active、TP0(N1)+TP1(N2)
> 分布式编译加载、`:8001` OpenAI API 输出正常，双机内存对称（56G/76G 含组件）。

## 关键参数（已踩坑修正）
1. 镜像 vllm/vllm-openai:latest **不含 ray** → 启动脚本先 `pip install -q ray`
2. 模型路径必须指向 **snapshots/<hash>** 层（HF 缓存根无 config.json）
3. 双机模型需在**相同容器内路径**（worker 挂载 N2 副本到与 N1 一致的 /model）
4. `--distributed-executor-backend ray` 必须显式指定
5. **先停单机 vLLM**（N1 yyc3-vllm-service 0.85util≈85G + N2 nemoclaw-vllm 64G 会触发 ray OOM killer/内存不足）
6. NCCL 三参数照门禁口径：NCCL_SOCKET_IFNAME=enp1s0f0np0 / NCCL_IB_HCA=mlx5_0 / NCCL_NET_GDR_LEVEL=5

## 复现命令
```bash
# N1 (head+serve, :8001)
docker run -d --name tp2-head --network host --gpus all --shm-size 16g \
  -e NCCL_SOCKET_IFNAME=enp1s0f0np0 -e NCCL_IB_HCA=mlx5_0 -e NCCL_NET_GDR_LEVEL=5 \
  -v /home/yyc3/models/hf-cache/models--Qwen--Qwen3.6-27B-FP8:/model:ro \
  --entrypoint bash vllm/vllm-openai:latest -c \
  'pip install -q ray && ray start --head --port 6379 --disable-usage-stats && sleep 3 && \
   exec vllm serve /model/snapshots/e89b16ebf1988b3d6befa7de50abc2d76f26eb09 \
   --served-model-name qwen3.6-27b-tp2 --tensor-parallel-size 2 \
   --distributed-executor-backend ray --max-model-len 32768 \
   --gpu-memory-utilization 0.35 --kv-cache-dtype fp8 --trust-remote-code \
   --enable-prefix-caching --port 8001 --host 0.0.0.0'

# N2 (worker)
docker run -d --name tp2-worker --network host --gpus all --shm-size 16g \
  -e NCCL_SOCKET_IFNAME=enp1s0f0np0 -e NCCL_IB_HCA=mlx5_0 -e NCCL_NET_GDR_LEVEL=5 \
  -v /home/yyc3/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B-FP8:/model:ro \
  --entrypoint bash vllm/vllm-openai:latest -c \
  'pip install -q ray && exec ray start --address=10.100.168.2:6379 --block --disable-usage-stats'
```
验收：`curl localhost:8001/v1/models` → qwen3.6-27b-tp2；head 重启后 **worker 必须重启**（旧连接失效）。

---

## ⚠️ 2026-09-03 关键勘误：v0.26.0 镜像在 GB10 上输出乱码（已修，换 nightly）

**现象**：TP=2 集群 startup complete、双机内存对称，但输出乱码（greedy raw `The capital of France is` → `e-9, 1e-9...`），21:31 容器重启后出现（此前输出连贯性未复验，无法排除更早）。

**排除过程**（每一项都有实证）：
| 嫌疑 | 验证 | 结论 |
|------|------|------|
| 权重损坏 | 双端 51 文件 sha256 全对官方（hf-mirror tree API LFS oid） | ✅ 完好 |
| NCCL 通信 | GDR=5 / GDR=0 / NCCL_IB_DISABLE=1 三模式**逐字节同乱码** | ✅ 排除 |
| ray/通道 | Gemma3 4B 小模型同参数 TP=2 双机输出完美（Paris ✓） | ✅ 排除 |
| 量化路径 | `--quantization fp8` 通用与 `deepseek_v4_fp8` 专属**逐字节同乱码** | ✅ 排除 |
| 分词器 | `--tokenizer-mode auto` 同乱码 | ✅ 排除 |
| **vLLM v0.26.0 sm_121 FP8 kernel** | **换 nightly 输出立即恢复正常** | ❗ 根因 |

**修复（当前生产配置）**：
```bash
# 双机均需：
docker pull docker.m.daocloud.io/vllm/vllm-openai:nightly
# digest 锁定（防漂移，2026-09-03）:
#   docker.m.daocloud.io/vllm/vllm-openai@sha256:31a59e7704a9c2fcd967b84f649442c7d8b...
# 启动命令与原版一致，仅镜像名换 nightly（v0.26.0 latest 标签勿再用，直至上游发修复版）
```

**验证记录（09-03 08:20）**：raw greedy → ` Paris.` ✓；chat 连贯中文 ✓；NAS 网关全链路（X-YYC3-Upstream: flagship-dsv4 + SSE 流式）✓；双机 104G/102G 对称。
