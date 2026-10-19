# FAQ — 高频问题（全部来自本仓真实判例）

> 每条带 Owner 与关联文档。新 FAQ 按「Q/A/关联/Owner」四段追加。

**Q1：为什么 `pnpm doctor` 报「未知命令」或跑了别的东西？**
**A**：裸 `pnpm doctor` 被 pnpm 内建命令抢占。项目脚本必须 `pnpm run doctor`。同类：`pnpm knip` 是 knip 原始输出（有 findings 即 exit 1），死代码门禁是 `node scripts/knip-check.mjs`。
**关联**：AGENTS.md 自诊断节 · EXIT-CODES.md
**Owner**：门禁 Owner

**Q2：测试突然大批失败，但单独跑某个文件又是绿的？**
**A**：多 worker 资源竞争（R3 判例：28 失败隔离全绿）。已将 maxWorkers 封顶 8。复现时先隔离复跑定位，勿慌改代码；大批 agent/重任务结束后歇一拍再跑重门禁。
**关联**：ADR-011 · S4 stage-4.summary.json
**Owner**：测试 Owner

**Q3：为什么 hooks 里不能 `import { nodeStore } from "../stores/..."`？**
**A**：分层契约（boundaries 六层 elements）：hooks 只能引 hooks/lib/types。组件域数据由组件取好后经参数传入 hooks。
**关联**：ADR-002 · BOUNDARIES.md §1
**Owner**：架构 Owner

**Q4：e2e 报浏览器不存在（Executable doesn't exist）？**
**A**：全局 Playwright 浏览器缓存被其他项目升级/清理。`pnpm exec playwright install chromium`（EBUSY 半途失败就重试一次）。当日两遇判例。
**关联**：S11 stage-11.summary.json
**Owner**：测试 Owner

**Q5：为什么我加的中文界面文案，英文界面显示键名？**
**A**：双语包必须同步。en-US 类型是 `DeepStringify<typeof zhCN>`，少键会编译错；若绕过（如 as any）会被 i18n-consistency 测试拦。补键后跑 `pnpm exec vitest run src/app/__tests__/i18n-consistency.test.ts`。
**关联**：ADR-008 · i18n-packs.test.ts
**Owner**：i18n Owner

**Q6：为什么 UI 里不能直接写 `#00d4ff`？**
**A**：色值基线棘轮（5486 冻结），增量即 `pnpm color:check` FAIL。用 theme.css 的 token：`text-primary` / `bg-destructive` / `chart-2/3/4/5` 或 `var(--primary)`。精确映射表见 color-budget.json 注释与 ADR-012。
**关联**：ADR-012 · CONTRACTS.md
**Owner**：设计系统 Owner

**Q7：`pnpm build:console` 和 `pnpm build` 有什么区别？**
**A**：产物双形态——`build` 出 dist/（根路径，Pages/LAN），`build:console` 出 dist-console/（/console/ 子路径，公网 HMAC 形态）。资产链接已相对路径化，双形态通吃。
**关联**：S12 · index.html 头注释
**Owner**：部署 Owner

**Q8：为什么终端补全会建议我根本没有的节点/环境变量？或反过来没建议？**
**A**：五维协同源（静态表+节点+env+路由+历史频率）实时聚合；节点/env 源异常会降级为静态兜底（catch→[]）。频率来自你的真实使用（recordCommand）。
**关联**：ADR-010 · terminal-completions.test.ts
**Owner**：lib Owner

**Q9：测试里为什么不能发真实 HTTP 请求/读真实文件/用真实时间？**
**A**：ADR-011 unit 隔离——三类依赖 = 三类 flaky。fetch 用 vi.stubGlobal（lib/http.ts 底层可拦）；IDB 走降级契约；时间用 fake timers+try/finally。真实依赖归 integration 档（显式开关）。
**关联**：ADR-011 · SELF-HEAL H3
**Owner**：测试 Owner

**Q10：登录成功了，但第二天又被登出？**
**A**：会话 TTL 12h（设计内）。若登出后旧 Cookie 在**同进程**内仍有效才是 bug（jti 吊销应拦）。进程重启后旧 Cookie 复活属已知内存态语义（backlog L-06，多管理员需求触发持久化）。
**关联**：ADR-006 · KNOWN-GAPS.md
**Owner**：安全 Owner

**Q11：为什么 audit 页能按 request_id 查网关流水，错误报告里却是另一个 traceId？**
**A**：两侧锚点独立（网关 request_id 在响应日志里，请求失败时拿不到）。错误侧 traceId 是 L-05 新增的前端锚点；跨侧检索按时间窗+source 近似；注入通道已预留（后端支持请求头后启用）。
**关联**：TRACING.md
**Owner**：可观测 Owner

**Q12：NAS 重启后 console 会自己起来吗？**
**A**：会——crontab @reboot（sleep 20 等）→ pm2 resurrect → dump 恢复。三环体检：`ops.mjs boot`。boot.log 无痕迹说明钩子未触发（查 cron 守护）。
**关联**：SELF-HEAL H4 · ADR-INDEX R10 事件
**Owner**：部署 Owner
