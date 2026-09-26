#!/bin/bash
# MacMax PG 流复制 — 一键配置脚本
# ⚰️ 已退役（2026-09-27）：源端 NAS Docker PG :54320 已随 PG14 退役下线（实测无监听）。
# 现行家族备库 = NAS 宿主 PG15 :5433（只读镜像 Mac 全部 13 业务库，lag=0），无需再从 Mac 侧建副本。
# 归档保留供回溯；勿再执行（brew 停服 + 数据目录 mv 具破坏性）。
# 从 NAS Docker PG (100.65.172.88:54320) 创建本地只读副本

set -e

echo "========================================"
echo " MacMax PG 流复制 — 一键配置"
echo "========================================"
echo ""

echo "1/4 停止本地 PG 15 服务"
brew services stop postgresql@15
sleep 2

echo ""
echo "2/4 备份旧数据到 postgresql@15.bak.$(date +%s)"
mv /opt/homebrew/var/postgresql@15 /opt/homebrew/var/postgresql@15.bak.$(date +%s)

echo ""
echo "3/4 从 NAS 拉取全量数据（流复制基准备份）"
echo "    源: 100.65.172.88:54320"
echo "    目标: /opt/homebrew/var/postgresql@15"
pg_basebackup -h 100.65.172.88 -p 54320 -U postgres \
  -D /opt/homebrew/var/postgresql@15 \
  -P -v --wal-method=stream

echo ""
echo "4/4 生成 standby 信号文件"
touch /opt/homebrew/var/postgresql@15/standby.signal

echo ""
echo "启动 PG 15 从库"
brew services start postgresql@15
sleep 3

echo ""
echo "========================================"
echo " 验证从库状态"
psql -U yanyu -p 5433 -c "SELECT pg_is_in_recovery() AS is_replica;"
psql -U yanyu -p 5433 -c "SELECT pg_last_wal_receive_lsn()::text AS last_receive_lsn;"
echo "========================================"
echo ""
echo "如果 pg_is_in_recovery 返回 t (true)，则流复制配置成功 ✅"
echo "要查看复制延迟（秒）:"
echo "  psql -U yanyu -p 5433 -c \"SELECT extract(epoch FROM now() - pg_last_xact_replay_timestamp()) AS replay_lag_seconds;\""
