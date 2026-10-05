#!/bin/bash
# container_map.tsv 刷新（cn.lua v2 数据源）：docker 容器 id12→name 映射
# 由 container-map.timer 每 5 分钟触发；经 docker cp 注入 fluent-bit 容器
# （容器内 lua 读 /fluent-bit/etc/container_map.tsv；mv 换 inode 会破坏 bind mount，故用 docker cp）
D=/home/yyc3/logging
docker ps --format '{{.ID}}  {{.Names}}' > "$D/container_map.tsv.tmp" 2>/dev/null
docker cp "$D/container_map.tsv.tmp" yyc3-fluent-bit:/fluent-bit/etc/container_map.tsv
rm -f "$D/container_map.tsv.tmp"
