# 环境变量矩阵 — 跨脚本统一视图（S17）

> 按消费方分组；「敏感」列 = 是否凭据类（凭据只经 env/密钥文件，禁入库——红线）。

## 本地开发 / CI（package.json scripts 消费）

| 变量 | 必填 | 默认 | 敏感 | 消费方 | 说明 |
| --- | --- | --- | --- | --- | --- |
| YYC3_TEST_INTEGRATION | integration 档 | 未设 | 否 | vitest projects | 显式开关（零外部依赖红线出口） |
| CI | playwright/eslint | 未设 | 否 | reporter 形态切换 | CI=true 用 github reporter |
| VITE_BASE | build:console / e2e webServer | / | 否 | vite base | console 子路径形态 |
| NODE_ENV / import.meta.env.PROD | SW 注册门控 | — | 否 | sw-register | PROD 才注册 SW |

## 部署件（deploy/server.mjs · console-server.mjs 运行时读取）

| 变量 | 必填（形态） | 默认 | 敏感 | 说明 |
| --- | --- | --- | --- | --- |
| PORT | 否 | 3100(console)/3118(LAN 内建) | 否 | 监听端口 |
| HOST | 否 | 127.0.0.1 | 否 | NAS 形态 0.0.0.0 |
| DIST_DIR | 否 | ../dist | 否 | **ECS 布局=dist**（L-01 判例） |
| CONSOLE_AUTH_SECRET | 公网形态 | 空=鉴权关 | **是** | openssl rand -hex 32；与 PASSWORD 同时配置才启用 |
| CONSOLE_ADMIN_PASSWORD | 公网形态 | 空 | **是** | 凭据文件 600 留档 |
| GW_ORIGIN | 公网形态 | http://127.0.0.1:8800 | 否 | 上游网关 |
| GW_ADMIN_KEY | 公网形态(穿门) | 空→gw 503 | **是** | 网关容器 env 取, 服务端注入 |
| OLLAMA_HOST / OLLAMA_PORT | LAN 代理 | 本机/11434 | 否 | Ollama 反代目标 |
| ALLOW_ORIGIN | server.mjs | 仅同源 | 否 | 逗号分隔精确来源 |
| ALLOW_ORIGIN_CIDR | server.mjs | — | 否 | IPv4 网段 |

## 运维台（scripts/nas-console-ops.mjs）

| 变量 | 默认 | 敏感 | 说明 |
| --- | --- | --- | --- |
| CONSOLE_BASE | http://127.0.0.1:3210 | 否 | 目标（白名单 127.0.0.1/::1/192.168.3.45） |
| CONSOLE_DIR | /Volume2/yyc3-console | 否 | 部署目录 |
| PM2_BIN | nvm node24 路径/pm2 | 否 | |
| CONSOLE_CRED | ~/.yyc3-console-cred | **是**（只读） | 600 权限 |

## e2e / 测试

| 变量 | 默认 | 敏感 | 说明 |
| --- | --- | --- | --- |
| E2E_ADMIN_PASSWORD | e2e-test-password（分段拼装） | 否（测试专用值） | 与 playwright.config webServer.env 一致 |
| CHROME_PATH | — | 否 | lighthouse 指定 Chrome for Testing（spec 内自动解析） |

## 生产凭据位置（不在仓库）

| 位置 | 内容 | 权限 |
| --- | --- | --- |
| NAS /Volume2/yyc3-console/console.env | PORT/HOST/DIST_DIR/GW_ORIGIN/GW_ADMIN_KEY/CONSOLE_* | 600 |
| NAS /home/YYC3/.yyc3-console-cred | 管理员密码 | 600 |
| ECS /opt/yyc3/console/console.env | 同 NAS 结构（DIST_DIR=dist） | 600 |
| ECS /root/.yyc3-console-cred | 密码（从 env 再生, 与 env 单源同步） | 600 |
| NAS /Volume2/yyc3-33/.env | 网关 POSTGRES/DB/REDIS 密码+ZHIPU_API_KEY+JWT+API_KEYS | compose 变量化 |
