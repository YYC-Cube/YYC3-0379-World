#!/bin/bash
# 2026-09-24 W1 窗口：util 0.72→0.66 —— 为 N2 第三服务（OCR 0.10）让出显存，
# 消除 UMA 剖析期重平衡级联。KV 每 rank ~13G→~5G（FP8 KV+prefix caching）。
pip install -q -i https://pypi.tuna.tsinghua.edu.cn/simple ray 2>&1 | tail -1
ray start --head --port 6379 --node-ip-address 10.100.168.2 --disable-usage-stats 2>&1 | tail -1
sleep 3
export VLLM_HOST_IP=10.100.168.2
# 2026-10-05 修复：TP2 跨机启动竞态——EngineCore shm_broadcast cancelled 崩溃循环
# （vLLM 0.28.1rc1.dev278 breakable cudagraph 在跨机 TP 下 worker autotune/graph 收尾
#   窗口触发 APIServer startup 取消）；禁用 breakable cudagraph 规避，日志明确提供本 opt-out。
export VLLM_USE_BREAKABLE_CUDAGRAPH=0
# 2026-10-05(c2): --enforce-eager —— NVRM 实锤 CUDA graphics context OOM
# （NV_ERR_NO_MEMORY @ kgrctxAllocCtxBuffers：TP1 权重 73.84G 落位后 UMA available
#   仅 14G，graph 捕获压垮峰值 → rank died 循环）；跳过 graph 捕获，decode 代价 ~10-20%。
# 2026-10-05(c3): max-model-len 65536→32768 —— eager 后 warmup 尾部仍 OOM
# （双机 available 14-15G，profiling 激活/KV 峰值减半补缺口；当前流量远低于 32K）。
# 回滚：.bak-20261005 / .bak-eager65536（101:/home/yyc3/）。
exec vllm serve /model \
  --served-model-name deepseek-v4-flash \
  --tensor-parallel-size 2 \
  --distributed-executor-backend ray \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.66 \
  --kv-cache-dtype fp8 \
  --trust-remote-code \
  --enable-prefix-caching \
  --enforce-eager \
  --port 8001 --host 0.0.0.0
