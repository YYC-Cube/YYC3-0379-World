#!/bin/bash
# ==============================================================
# ④ 向量库冷备份脚本 backup_vector.sh
# 数据流：DGX -> NAS RAID6
# 功能：Milvus向量库每日全量备份，保留30天滚动窗口
# 触发方式：crontab 每日凌晨3点执行
# ==============================================================

LOG_FILE="/volume1/scripts/logs/backup_vector_$(date +%Y%m%d).log"
DGX1_ADDR="10.0.0.11"
DGX_VECTOR_PATH="/data/milvus-data/"
BACKUP_TARGET="/volume2/RAID6/yyc3-data/vector-backup/$(date +%Y%m%d)/"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始向量库全量备份" >> $LOG_FILE

mkdir -p $BACKUP_TARGET
rsync -avz root@$DGX1_ADDR:$DGX_VECTOR_PATH $BACKUP_TARGET >> $LOG_FILE 2>&1

# 保留30天备份
find /volume2/RAID6/yyc3-data/vector-backup/ -mtime +30 -type d -exec rm -rf {} \;

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 向量库备份完成" >> $LOG_FILE
