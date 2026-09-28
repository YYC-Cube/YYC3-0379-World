#!/bin/bash
# file: rerank8b_entry.sh
# description: yyc3-rerank8b 容器入口——UMA 断言补丁 + vllm serve Qwen3-Reranker-8B（:8104）
# author: YanYuCloudCube Team <admin@0379.email>
# version: v1.0.0
# created: 2026-09-28
# status: active
# tags: [rag],[reranker],[8b],[uma-patch]
#
# 血统：复刻 N2 ~/rerank8b_serve.sh（原 nohup 形态）容器化常驻（同 emb8b_entry.sh）。
# 差异：原脚本 --runner pooling 只暴露 /v1/score|rerank；本版去掉该参数让 vLLM
# 自动检测（与 0.6b 同姿势）——/v1/completions 生成式打分可用，rerank_svc 兼容。

p="/usr/local/lib/python3.12/dist-packages/vllm/v1/worker/gpu_worker.py"
python3 - "$p" <<'PYEOF'
import sys
p = sys.argv[1]
src = open(p).read()
old = "assert init_free_memory >= free_gpu_memory, ("
new = "assert init_free_memory >= free_gpu_memory or True, ("
if old in src:
    open(p, "w").write(src.replace(old, new))
    print("PATCH-APPLIED")
else:
    print("PATCH-ALREADY-OR-MISSING")
PYEOF
exec vllm serve /model --served-model-name qwen3-reranker-8b \
  --port 8104 --max-model-len 4096 --gpu-memory-utilization 0.16 \
  --enforce-eager --trust-remote-code --host 0.0.0.0
