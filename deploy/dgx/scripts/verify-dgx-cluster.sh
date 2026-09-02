#!/usr/bin/env bash
# DGX 双机集群部署前门禁验证（B 方案 TP=2 启用前置）
# 依据: docs/架构与部署/DGX-Spark双机推理部署指南.md §5 + §12
# 在 N1 (yyc3-101) 上执行；全部通过后方可启用 docker-compose-dgx-tp2.yml
set -euo pipefail

N1_QSFP="${N1_QSFP:-10.100.168.2}"   # N1 QSFP 地址 (rank0)
N2_QSFP="${N2_QSFP:-10.100.168.1}"   # N2 QSFP 地址 (rank1)
PASS=0; FAIL=0

ok()   { echo "✅ PASS: $1"; PASS=$((PASS+1)); }
bad()  { echo "❌ FAIL: $1"; FAIL=$((FAIL+1)); }

echo "== 1. 集群连通性（SSH 免密 / iperf3 / 拓扑） =="
ssh -o BatchMode=yes -o ConnectTimeout=5 "${N2_QSFP}" true \
  && ok "SSH 免密到 N2" || bad "SSH 免密到 N2"
iperf3 -c "${N2_QSFP}" -t 5 >/dev/null 2>&1 \
  && ok "iperf3 带宽测试可达" || bad "iperf3 不可达（先在 N2 起 iperf3 -s）"
nvidia-smi topo -m >/dev/null 2>&1 && ok "nvidia-smi topo" || bad "nvidia-smi 不可用"

echo "== 2. NCCL all_reduce_perf 冒烟（GB10 UMA int32 根因复测，唯一硬门禁） =="
# 预期: 正常完成且输出 bus bandwidth；若挂起/OOM(-24GB malloc) → 维持 ADR-4，禁用 TP=2
docker run --rm --gpus all --shm-size=16g \
  -e NCCL_SOCKET_IFNAME=enp1s0f0np0 \
  -e NCCL_IB_HCA=mlx5_0 \
  -e NCCL_NET_GDR_LEVEL=5 \
  nvcr.io/nvidia/pytorch:25.05-py3 \
  python -c "
import torch.distributed as dist, os, time
dist.init_process_group('nccl', init_method='env://')
t = torch.cuda.Stream(); x = torch.ones(1024**3, dtype=torch.uint8, device='cuda')
dist.all_reduce(x.view(torch.float32) if x.numel() % 2 == 0 else x[:1024].float())
print(f'all_reduce OK on rank {dist.get_rank()}')
dist.destroy_process_group()
" && ok "NCCL all_reduce（双机需配 MASTER_ADDR/PORT 环境变量再跑一次留档）" \
  || bad "NCCL all_reduce 失败/挂起 → 维持 ADR-4，退回 A 方案"

echo "== 3. 服务健康（已在运行的推理容器） =="
for url in "http://localhost:8000/v1/models" "http://${N2_QSFP}:8000/v1/models"; do
  curl -sf --max-time 5 "$url" >/dev/null && ok "$url" || echo "⏭️  SKIP: $url（未启动）"
done

echo
echo "结果: PASS=${PASS} FAIL=${FAIL}"
[ "$FAIL" -eq 0 ] && echo "✅ 门禁通过，可部署 docker-compose-dgx-tp2.yml（先 rank0 后 rank1）" \
                  || echo "❌ 存在失败项；TP=2 未解锁，按 ADR-4 走 A 方案编排（n1/n2 compose）"
exit "$FAIL"
