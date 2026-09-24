#!/bin/bash
# 2026-09-24 W1 窗口：util 0.72→0.66 —— 为 N2 第三服务（OCR 0.10）让出显存，
# 消除 UMA 剖析期重平衡级联。KV 每 rank ~13G→~5G（FP8 KV+prefix caching）。
pip install -q -i https://pypi.tuna.tsinghua.edu.cn/simple ray 2>&1 | tail -1
ray start --head --port 6379 --node-ip-address 10.100.168.2 --disable-usage-stats 2>&1 | tail -1
sleep 3
export VLLM_HOST_IP=10.100.168.2
exec vllm serve /model \
  --served-model-name deepseek-v4-flash \
  --tensor-parallel-size 2 \
  --distributed-executor-backend ray \
  --max-model-len 65536 \
  --gpu-memory-utilization 0.66 \
  --kv-cache-dtype fp8 \
  --trust-remote-code \
  --enable-prefix-caching \
  --port 8001 --host 0.0.0.0
