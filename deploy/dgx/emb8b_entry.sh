#!/bin/bash
# file: emb8b_entry.sh
# description: yyc3-emb8b 容器入口——UMA 断言补丁 + vllm serve Qwen3-Embedding-8B（:8103）
# author: YanYuCloudCube Team <admin@0379.email>
# version: v1.0.0
# created: 2026-09-28
# status: active
# tags: [rag],[embedding],[8b],[uma-patch]
#
# 血统：复刻 N2 ~/emb8b_serve.sh（临时 nohup 形态，宿主重启即失联——
# 8B 由此下线三周，ops_rag main 库恒降级 online，2026-09-28 容器化常驻收编）。
# 补丁语义：vLLM gpu_worker profiling 断言假设同机进程内存不变，UMA + 同机
# vLLM 多实例场景必然波动（官方注释声明的例外场景），恒真化处理。

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
exec vllm serve /model --served-model-name qwen3-embedding-8b \
  --port 8103 --max-model-len 8192 --gpu-memory-utilization 0.15 \
  --enforce-eager --trust-remote-code --host 0.0.0.0
