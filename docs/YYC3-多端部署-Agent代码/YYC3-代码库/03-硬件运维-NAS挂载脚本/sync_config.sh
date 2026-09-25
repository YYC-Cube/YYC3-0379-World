#!/bin/bash
# ==============================================================
# ① 核心配置同步脚本 sync_config.sh
# 数据流：MacMAX -> NAS RAID1 高可用区
# 功能：增量同步提示词、Agent代码，保留版本备份
# 触发方式：crontab 每小时执行一次，实时同步开发成果
# ==============================================================

LOG_FILE="/volume1/scripts/logs/sync_config_$(date +%Y%m%d).log"
MAC_SHARE="/volume1/smb_mac_upload/"
TARGET_DIR="/volume1/RAID1/yyc3-core/"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始同步核心配置" >> $LOG_FILE

# 增量同步，备份旧版本
rsync -avz --backup --backup-dir=backup/$(date +%Y%m%d_%H%M) \
    --exclude='*.tmp' --exclude='.DS_Store' --exclude='__pycache__' \
    $MAC_SHARE/dev-output/prompt-templates/ \
    $TARGET_DIR/prompt-templates/ >> $LOG_FILE 2>&1

rsync -avz --backup --backup-dir=backup/$(date +%Y%m%d_%H%M) \
    --exclude='*.tmp' --exclude='.git' \
    $MAC_SHARE/dev-output/agent-code/ \
    $TARGET_DIR/agent-code/ >> $LOG_FILE 2>&1

# 权限修正
chown -R admin:users $TARGET_DIR
chmod -R 755 $TARGET_DIR

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 核心配置同步完成" >> $LOG_FILE
