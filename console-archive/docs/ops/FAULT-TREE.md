# 故障树 — 症状 → 根因 → 处置（15 场景全覆盖）

> 每棵树：症状 → 根因分支 → 处置命令 → 验证。定位不了的走 RUNBOOK 升级路径。
> 判例标记 ★ = 本仓真实发生过（审计链有据）。

---

## T1 · 部署起不来（服务启动失败）★

**症状**：pm2 `errored` 反复重启 / curl 拒连 / 日志 EADDRINUSE 或抛栈。
```
启动失败
├── A 端口被占 (EADDRINUSE ★两遇: S12 lighthouse 残留 / S14 旧实例)
│   └── 处置: lsof -nP -i :PORT 找 pid → 确认归属 → kill；起服务前先查端口
├── B env 未注入 (pm2 restart --update-env 无效 ★ECS 判例)
│   └── 处置: pm2 delete yyc3-console → cd 部署目录 → set -a; . ./console.env; set +a → pm2 start → pm2 save
├── C DIST_DIR 路径不符 (★L-01: ECS 布局 console/dist vs 默认 ../dist)
│   └── 处置: console.env 补 DIST_DIR=dist → 重启 → curl -H "Accept: text/html" /console/ 见 <!doctype
├── D dist 未构建
│   └── 处置: 本地 pnpm build (或 build:console) → scp 产物 → 重启
├── E Node 版本/路径 (nvm 环境)
│   └── 处置: 用绝对路径 /mnt/volume2/.nvm/versions/node/v24.18.0/bin/pm2
└── F 未知 → pm2 logs yyc3-console* --lines 50 → 升级 L2
```

---

## T2 · HMAC 鉴权失败（登录 401 / 会话失效）

**症状**：登录 401（密码正确却拒）/ 登录成功但穿门 401 / 全员被登出。
```
鉴权失败
├── A 密码/env 漂移 (★L-01: cred 29 位 vs env 16 位)
│   ├── 处置: 服务端从 env 再生 cred → chmod 600 → 重试（禁回显密钥）
│   └── 预防: cred 与 env 单源（env 为唯一事实源）
├── B env 未注入 pm2（→ 实际是空密码在比对）
│   └── 处置: pm2 env <name> | grep CONSOLE 确认 → delete + env 注入 + start
├── C 双端时钟偏移 >TTL 界
│   └── 处置: 对比 date +%s 与标准源；exp=now+12h, 偏移分钟级无害
├── D Cookie 被中间层剥离（Traefik/反代配置）
│   └── 处置: 对比登录响应 Set-Cookie 与后续请求 Cookie 头；查反代转发策略
└── E 全员被登出（重启后 jti Map 清空属正常, 非缺陷 ★S6 论证）
    └── 处置: 重新登录即可；多管理员需求出现再做持久化（backlog L-06）
```
**验证**：`curl -c /tmp/c -d '{"password":<cred>}' .../auth/login` → 200；带 Cookie `/console/gw/v1/models` 非 401。

---

## T3 · Ollama 代理不可达

**症状**：LAN 形态 `/proxy/ollama/*` 502/超时；service-test Ollama 项失败。
```
代理不可达
├── A Ollama 服务未起
│   └── 处置: 目标机 curl http://<host>:11434/api/tags → 起服务/拉模型
├── B OLLAMA_HOST/PORT 配置漂移
│   └── 处置: 核对 server.mjs env 与实际监听 (ss -tln | grep 11434)
├── C CORS/白名单
│   └── 处置: ALLOW_ORIGIN/ALLOW_ORIGIN_CIDR 按需放行（精确来源, 禁 "*" 出内网）
└── D 网络分段（跨网段防火墙）
    └── 处置: nc/curl 从 server 所在主机探测目标 11434
```

---

## T4 · 内网服务不可达（Prometheus/Loki/Redis/PG/NAS）

**症状**：Grafana 无数据 / 网关日志 UndefinedTable / 健康检查段失败。
```
内网不可达
├── A Prometheus 容器起但端口未发布 (★S1: 三面 000 实证)
│   └── 处置: docker compose up -d prometheus（声明态=具名卷, 037dac3）; 镜像缺失先 tag daocloud 源
├── B Loki 503 未就绪
│   └── 处置: 等 ready（S1 实测 503→200 自愈）；查容器日志
├── C Redis/PG 仅回环监听（设计内）
│   └── 处置: 在 NAS 本机 ss -tln 验证 127.0.0.1 监听即正常；跨机访问需改绑定=架构变更须评审
├── D compose 网络调和被拒 (★S1: active endpoints)
│   └── 处置: 勿强删网络；先 docker ps 确认存量服务, 逐服务 up -d --no-deps
└── E fnOS Docker Hub 直连超时
    └── 处置: 用本地已有镜像 tag（daocloud 源判例）再 compose up
```

---

## T5 · PWA 离线降级未生效

**症状**：断网后白屏/刷新失败；SW 未注册。
```
离线失效
├── A 非 PROD 构建（sw-register PROD-only）
│   └── 处置: 确认跑的是 build 产物而非 dev server
├── B SW 未就绪就断网（测试时机）
│   └── 处置: e2e 判例——显式等 navigator.serviceWorker.ready
├── C 资产 404（绝对路径子路径形态 ★S11）
│   └── 处置: index.html 相对路径化已修；新资产沿用相对路径
├── D SW 更新卡旧版
│   └── 处置: DevTools Application → Unregister + Clear storage → 刷新
└── E 离线数据缺失
    └── 处置: IDB 走 yyc3-storage 降级契约（ hooks 单测背书）；真实 IDB 问题归 integration 档
```

---

## T6 · 覆盖率门禁失败

**症状**：`pnpm test:coverage` exit 1, ERROR 行低于门槛。
```
覆盖率失败
├── A 新代码带分支无测试 (★S2: 双旗标 +270 分支点)
│   └── 处置: 报告 Uncovered 行 → 补真覆盖用例（死臂翻 ! 前先证明不可构造）
├── B 重构删了覆盖它的测试
│   └── 处置: 红线禁止——恢复测试或证明测试目标已删
├── C 可证不可构造分支占比升高
│   └── 处置: 逐臂论证 + 就近注释登记（S5 33 臂判例, 禁 ignore 注释稀释）
└── D 偶发（无 ERROR 但 exit 1, DEF-06）
    └── 处置: 以 CI 契约命令 pnpm test:coverage 复跑
```

---

## T7 · 元门禁探针失败（假绿风险）

**症状**：`pnpm guardrail-probe` exit 1, 某探针「⚠️ 未拦截」。
```
元门禁失败
├── A 门禁真失效（工具升级/配置脱节 ★2026-09-24 原始事件）
│   └── 处置: 看转储的门禁输出 → 修配置/锁版本 → 重跑探针至拦截
├── B 探针样本过时 (★gitleaks: 32 位不够长 / 字母表序列被 stopwords 豁免)
│   └── 处置: 样本升级为高熵 ≥36 位；探针质量缺陷也要修（反向验证价值）
├── C 环境缺二进制（gitleaks 未装）
│   └── 处置: brew install gitleaks（8.30.1 对齐 CI pin）
└── D size 探针变异后未恢复
    └── 处置: finally 已兜底; 手动 git checkout src/app/components/ServiceConnectionTest.tsx
```

---

## T8 · 构建产物体积超标

**症状**：inject-precache 报超预算 / chunk >500KB 警告激增 / color/dup 门禁连坐。
```
体积超标
├── A 预缓存超 6MB
│   └── 处置: 查新增大资产; 图标/字体走 CDN 或按需
├── B 新依赖拖重入口 chunk
│   └── 处置: bundle-stats.mjs 看 top5 → 动态 import / manualChunks
├── C editor 语言包再增长
│   └── 处置: 按语言懒加载（L-09 判据: IDE 路由已重定向, 非紧迫）
└── D 色值/重复连坐（color:check/dup:check FAIL）
    └── 处置: 新增走 tokens / 抽 shared；门禁输出含 Top files 定位
```

---

## T9 · 六域某一域白屏（ErrorBoundary 触发）

**症状**：某路由整页错误边界 UI；控制台 pageerror。
```
域白屏
├── A 组件运行时异常（数据形状漂移 ★常见）
│   └── 处置: 复制错误报告（含 traceId L-05）→ 按堆栈定位 → 补守卫或修数据归一化
├── B 懒加载 chunk 404（发版后旧 hash 失效）
│   └── 处置: 刷新即愈（SW network-first）; 持续则查部署完整性
├── C Figma 噪声误杀（已过滤, 但形态可变）
│   └── 处置: ErrorBoundary 过滤清单扩充（App.tsx Layer 0c 唯一例外区）
└── D 未知
    └── 处置: getErrorLog() 取 AppError（traceId 关联）→ 升级 L2
```
**验证**：路由恢复渲染 + `pnpm test:unit` 相关文件绿。

---

## T10 · i18n 键不一致

**症状**：i18n-consistency/packs 测试 FAIL；界面裸键名。
```
i18n 失败
├── A 只加了 zh 缺 en（或反之）
│   └── 处置: 测试输出即缺键清单 → 补翻译（types 层 TranslationKeys 也会编译报错）
├── B 模板变量不一致
│   └── 处置: packs 测试定位键 → 双语补齐 {var}
└── C 语言键混淆（yyc3_locale 真 / yyc3-lang ide-mock ★S11）
    └── 处置: 断言/读写统一 yyc3_locale
```

---

## T11 · 图标链路断裂

**症状**：favicon 404 / PWA 安装横幅消失 / chain-verify missing。
```
图标断裂
├── A 绝对路径子路径形态 404 (★S11 已修, 回归即检查 index.html)
│   └── 处置: 保持相对路径; e2e 资产用例守护
├── B manifest icons 与文件不同步
│   └── 处置: node scripts/chain-verify.mjs 输出 missingIcons → 补文件或删声明
├── C 新平台/尺寸遗漏
│   └── 处置: 5 平台目录制 + 三处对齐（index.html/manifest/useYYC3Head）
└── D CDN 回退失效
    └── 处置: yyc3-icons.ts iconsCDN 可达性探测（本地优先, CDN 仅兜底）
```

---

## T12 · secret 泄漏（紧急）

**症状**：gitleaks 命中 / 外部报告泄露。
```
secret 泄漏
├── A 真实凭据入库
│   ├── 处置 1(先): 立即在来源方吊销/轮换（OpenAI/网关 API_KEYS/云控制台）
│   ├── 处置 2: git rm + 历史清理（filter-repo）——但历史已推则视同永久泄露, 轮换是唯一解
│   └── 处置 3: 复盘归档 + guardrail 复扫
├── B 公开文档向量误报 (★RFC 6455 / Figma key 判例)
│   └── 处置: 逐行核对定性 → 豁免条目（原因+复核日期+Fingerprint, 路径用位置无关后缀 ★S6）
└── C 产物目录误报 (★dist minified .exec( 判例)
    └── 处置: 确认 gitignore 生效 + 向扫描器侧说明, 源码不动
```
**红线**：先吊销后分析；任何「确认是误报」必须附行级证据。

---

## T13 · 磁盘满 / 内存泄漏

**症状**：写入失败 / pm2 进程内存持续上涨 / NAS 卷 80%+。
```
资源耗尽
├── A 磁盘: dist*/coverage/test-results/pm2 logs/jscpd /tmp 报告堆积
│   └── 处置: pnpm 清理产物 + NAS 上 console-audit.log 轮转（logrotate 或按月切）
├── B pm2 进程内存上涨
│   └── 处置: pm2 monit 定位 → 重启窗口择期（内存态: 限流计数/jti 吊销会清——单管理员已论证）
└── C 静态服务大文件重复 readFile（现实现整读）
    └── 处置: 若出现 OOM 再改流式（当前产物 <1MB/文件, 非现状）
```

---

## T14 · 长任务超时 / worker 卡死（测试/CI）

**症状**：vitest 大批超时（★覆盖率 28 超时判例）/ e2e 卡死 / CI 超 wall time。
```
卡死
├── A 多 worker 资源竞争 (★R3: 28 失败隔离全绿)
│   └── 处置: 复跑隔离验证 → maxWorkers 已封顶 8 → 仍现则收紧 4 或 isolate 竞争文件
├── B 异步未 await / 定时器未还原
│   └── 处置: fake timers try/finally useRealTimers 判例; act 需 await（React18）
├── C e2e webServer 残留占端口 (★reuseExistingServer 复用旧进程假败)
│   └── 处置: lsof :3199 → kill 残留 → 重跑
└── D flaky 明细未保存
    └── 处置: 失败当场存完整 log（R3 教训: 只 grep 汇总丢了 16 失败明细）
```

---

## T15 · 智能补全引擎异常

**症状**：终端补全缺失/排序错乱/报错。
```
补全异常
├── A 动态数据源抛错
│   └── 处置: 设计内降级（collectNodeIds/collectEnvKeys catch→[]）——补全仍出静态候选; 修数据源本身
├── B 频率数据损坏
│   └── 处置: localStorage yyc3_terminal_history 清除 → 重建（历史可弃）
├── C 路由漂移（补全与 routes.ts 不同步）
│   └── 处置: 路由对齐守卫测试 FAIL 即定位——routes.ts 是唯一事实源
└── D 排序异常
    └── 处置: recordCommand 频率表 + byFrequencyThenValue 单测回归（41 用例域）
```

---

## 通用自愈入口

```bash
# NAS console 一站式
ssh -p 9557 yyc3-45 'node /Volume2/yyc3-console/ops.mjs status|verify|heal|boot|logs'
# 本地全门禁一键
pnpm run doctor && pnpm typecheck && pnpm lint && pnpm lint:fp && pnpm test:unit && pnpm test:coverage && pnpm astgrep && pnpm size:check && pnpm color:check && pnpm dup:check && node scripts/knip-check.mjs && pnpm guardrail-probe
```
