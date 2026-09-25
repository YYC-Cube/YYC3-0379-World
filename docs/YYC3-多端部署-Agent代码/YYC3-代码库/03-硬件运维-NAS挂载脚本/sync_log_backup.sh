#!/bin/bash
# ==============================================================
# ③ 审计日志备份脚本 sync_log_backup.sh
# 数据流：双DGX -> NAS RAID1 高可用区
# 功能：实时备份审计日志，双副本永久留存，满足合规审计要求
# 触发方式：crontab 每10分钟执行一次
# ==============================================================

LOG_FILE="/volume1/scripts/logs/sync_audit_$(date +%Y%m%d).log"
TARGET_DIR="/volume1/RAID1/yyc3-core/audit-logs/"
DGX1_ADDR="10.0.0.11"
DGX2_ADDR="10.0.0.12"
DGX_LOG_PATH="/data/nim-logs/"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始拉取DGX审计日志" >> $LOG_FILE

# 拉取两台DGX的日志
rsync -avz root@$DGX1_ADDR:$DGX_LOG_PATH $TARGET_DIR/dgx1/ >> $LOG_FILE 2>&1
rsync -avz root@$DGX2_ADDR:$DGX_LOG_PATH $TARGET_DIR/dgx2/ >> $LOG_FILE 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 审计日志备份完成" >> $LOG_FILE
