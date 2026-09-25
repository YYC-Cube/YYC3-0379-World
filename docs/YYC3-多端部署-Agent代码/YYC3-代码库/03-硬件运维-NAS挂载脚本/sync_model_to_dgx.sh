#!/bin/bash
# ==============================================================
# ② 模型分发同步脚本 sync_model_to_dgx.sh
# 数据流：NAS RAID6 -> 双DGX节点本地缓存
# 功能：NIM模型镜像闲时分发，--bwlimit 限速50MB/s 不占业务带宽
# 触发方式：crontab 每日凌晨2点执行
# ==============================================================

LOG_FILE="/volume1/scripts/logs/sync_model_$(date +%Y%m%d).log"
MODEL_SOURCE="/volume2/RAID6/yyc3-data/nim-model-repo/"
DGX1_ADDR="10.0.0.11"
DGX2_ADDR="10.0.0.12"
DGX_MODEL_PATH="/data/nim-model-cache/"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始同步模型至DGX集群" >> $LOG_FILE

# 同步至DGX节点1
rsync -avz --delete --bwlimit=50000 \
    $MODEL_SOURCE \
    root@$DGX1_ADDR:$DGX_MODEL_PATH >> $LOG_FILE 2>&1

# 同步至DGX节点2
rsync -avz --delete --bwlimit=50000 \
    $MODEL_SOURCE \
    root@$DGX2_ADDR:$DGX_MODEL_PATH >> $LOG_FILE 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 模型同步完成" >> $LOG_FILE
