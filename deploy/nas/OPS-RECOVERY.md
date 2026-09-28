# NAS 栈运维与灾后恢复手册（OPS-RECOVERY）

> 2026-09-27 建档。依据：09-26/27 TOS 批量整理 + NAS 整机重启事故复盘（《YYC3-数据库统一架构-2026-09》17 号）。

## 三条平台铁律（TOS NAS）

1. **TOS 容器清理跟随 compose labels**——TOS 侧应用管理操作可能连带删除同项目容器与 compose 文件。独立服务（非 0379 栈）用 `docker run` 直建（如 gitbucket），不给 TOS 关联句柄。
2. **手工 compose 必带 `--project-directory`**——漏掉则 `.env` 不加载，`REDIS_PASSWORD` 等展开为空导致 redis/postgres 启动 FATAL。
3. **开机自启只有两条路**：`/usr/local/etc/rc.d/*.sh`（当前 S99postgres.sh 覆盖 PG15 双实例 5433/5434 + Redis8 :6399 + frpc 隧道；PG14 okm 已于 2026-09-27 退役，勿加回）与 TOS 注册应用（/etc/init.d）。自建 init.d 目录无效。

## 标准命令

```bash
# docker 入口（宿主 docker CLI 无权限时）
D=/Volume3/@apps/DockerEngine/dockerd/bin/docker

# 核心栈（重建/升级）
cd /Volume2/yyc3-33
$D compose -p yyc3-33 --project-directory /Volume2/yyc3-33 -f deploy/nas/docker-compose.nas.yml up -d
$D compose -p yyc3-33 --project-directory /Volume2/yyc3-33 -f deploy/nas/docker-compose.monitoring.yml up -d

# 冒烟
curl -s http://192.168.3.45:8000/healthz     # {"status":"alive"...}
bash deploy/nas/smoke-test.sh                # 全量冒烟
```

## 灾后恢复序列（容器全失场景）

数据均在宿主 bind 卷，零丢失前提：

1. `cd /Volume2/yyc3-33 && git status`（工作树应为 clean 或仅 auto-deploy 运行痕迹）
2. 缺镜像先补：`$D pull docker.m.daocloud.io/library/<img> && $D tag ... <img>`（DockerHub 直拉超时）
3. 按"标准命令"重建核心栈 + 监控栈
4. 数据库层：`bash /usr/local/etc/rc.d/S99postgres.sh`（幂等）
5. 验证：`/healthz` 200 + `pg_stat_activity` + compose ps 全 healthy
6. 全家巡检：`bash /Volume2/@apps/yyc3_pg.sh status-all`（三实例+Redis）

## cron 路径锚定（2026-09-28 实测回填）

- `auto-deploy.sh` / `rebuild-gateway.sh` 为**仓库分发副本**（deploy/nas/，随 git 同步至 /Volume2/yyc3-33 工作树）
- ✅ 实测定论（09-28 `crontab -l` + `/etc/config/crontab` + spool + TOS sch 四路核验）：**全 NAS 无 cron/计划任务挂载**——两脚本实为**手动触发范式**（auto-deploy.log 中 `rebuild at <C>` 条目均为手动执行 rebuild-gateway.sh 产物）
- 部署语义：版本推进 = `git fetch && git reset --hard origin/main` + `bash deploy/nas/rebuild-gateway.sh`（后者不做 fetch，依赖工作树已推进）
- 处置：仓库副本**保留**（标准化手动入口 + smoke 挂载点；若未来加 cron 直接引用工作树路径 `bash /Volume2/yyc3-33/deploy/nas/auto-deploy.sh`）

## 端口契约（勿回退到 0.0.0.0）

gateway 8000 / grafana 3000 / gitbucket 8080·29418 —— 均绑 `192.168.3.45` + `100.65.172.88`（LAN+Tailscale）。

## 数据库拓扑（2026-09-27 更新）

| 实例 | 端口 | 用户 | 可用库 | 连接串（本机/家族设备） | 状态 |
| --- | --- | --- | --- | --- | --- |
| kb 主库（生产） | 5434 | postgres | yyc3_kb | `postgresql://postgres@192.168.3.45:5434/yyc3_kb` | ✅ 实测可写（197,558 行） |
| 家族备库（只读） | 5433 | yanyu | Mac 全部 13 业务库镜像 | `postgresql://yanyu@192.168.3.45:5433/<库名>` | ✅ 只读，复制 lag=0 |
| PG14 | 5432 | — | — | 已退役（连接必失败） | ⚰️ 09-27 退役（终末备份 `/Volume1/retired-pg14-20260927.tar.gz`） |
| 系统 PG13 | 5432 | — | — | 仅 NAS 本机 127.0.0.1 | 🚨 **勿动勿连**（红线） |

> ⚠️ 网关栈数据库 = compose 容器内 PG15（服务名 `postgres` 直连），与宿主上表实例互不相干；
> `.env` 的 `DB_HOST=127.0.0.1`/`DB_PORT=5432` 为历史残留（compose 字面量覆盖，不生效），勿据此连宿主库。
