#!/usr/bin/env bash
# file: seed-monitoring.sh
# description: 观测栈 named-volume 播种——把仓库配置/面板复制进卷（绕开 TOS ACL：容器内 root 复制）
# author: YanYuCloudCube Team | version: v1.0.0 | created: 2026-09-24
# 用法：NAS 工作树根执行 bash deploy/nas/seed-monitoring.sh
set -e
D=/Volume3/@apps/DockerEngine/dockerd/bin/docker
ROOT=/Volume2/yyc3-33
P=yyc3-33   # compose 项目名（工作树目录名）

echo "[seed] 复制 prometheus.yml → ${P}_prometheus-conf"
$D run --rm --user root \
  -v ${P}_prometheus-conf:/dst \
  -v ${ROOT}/deploy/nas:/src:ro \
  --entrypoint sh docker.m.daocloud.io/prom/prometheus:v2.53.0 \
  -c "cp /src/prometheus.yml /dst/ && chmod 644 /dst/prometheus.yml"

echo "[seed] 复制 grafana provisioning → ${P}_grafana-provisioning"
$D run --rm --user root \
  -v ${P}_grafana-provisioning:/dst \
  -v ${ROOT}/core/config/grafana:/src:ro \
  --entrypoint sh docker.m.daocloud.io/grafana/grafana:11.1.0 \
  -c "cp -r /src/provisioning/. /dst/ && find /dst -name '._*' -delete && chmod -R a+rX /dst"

echo "[seed] 复制 dashboards → ${P}_grafana-dashboards"
$D run --rm --user root \
  -v ${P}_grafana-dashboards:/dst \
  -v ${ROOT}/core/config/grafana:/src:ro \
  --entrypoint sh docker.m.daocloud.io/grafana/grafana:11.1.0 \
  -c "cp -r /src/dashboards/. /dst/ && find /dst -name '._*' -delete && chmod -R a+rX /dst"

echo "[seed] grafana-data 属主 472"
$D run --rm --user root \
  -v ${P}_grafana-data:/dst \
  --entrypoint sh docker.m.daocloud.io/grafana/grafana:11.1.0 \
  -c "chown -R 472:472 /dst"

echo "[seed] 重启生效"
$D restart yyc3-prometheus yyc3-grafana
echo "[seed] ✅ 完成"
