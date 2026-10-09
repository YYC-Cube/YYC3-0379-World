---
file: YYC3-本地运维智能面板-全链路设计提示词.md
description: 面向技术运维场景的纯本地可视化智能看盘 + 全维度中端面板操作系统 —— 全页面体系 / 全维度动效体系 / 轻量化智能能力 / 本地性能约束 完整设计提示词
author: AI Tutor <Intelligent Application Implementation Expert>
version: v1.0.0
created: 2026-10-09
updated: 2026-10-09
status: active
tags: [frontend],[ops-dashboard],[design-system],[animation],[offline-first],[nextjs16],[shadcn],[local-monitoring]
category: guide
supersedes: []
---

# YYC³ 本地运维智能面板 · 全链路设计提示词（v1.0.0）

> **一句话定位**：一套**纯本地自用、离线可运行**的可视化智能看盘与全维度中端面板操作系统，把 YYC³ 网关/Registry/推理节点/容器日志/GPU 的全量观测、告警、配置与日志查询收敛到一个本地应用，作为运营与排障的「单屏控制台」。
>
> **交付要求**：本文档为可**直接交给前端生成器/工程师落地**的完整设计指引，必须严格遵守项目真实数据契约（本仓库《05-监控告警与Runbook》指标矩阵、Registry 端点、Loki 日志标签），**禁止虚构不存在的指标、字段或端点**。所有数据源一律走本地内网，不依赖任何外部公网服务。

---

## 0. 角色与项目 Prompt（可直接投喂）

```text
正文（角色与项目，可直接投喂给前端生成器）：

你是资深前端架构师 + 运维可观测性产品专家 + 动效工程专家 + 本地性能优化专家。
项目：为「YanYuCloudCube」设计并指导落地一套纯本地自用的可视化智能看盘与
全维度中端面板操作系统（Local Ops Panel OS）。

硬性约束：
1. 纯本地/离线优先：所有数据来自本机与内网（Prometheus/Loki/Registry/Redis/本地 env），
   无公网依赖；Service Worker 全离线可用，断网降级读取本地快照。
2. 数据契约真实：所有指标/字段/端点必须来自《05-监控告警与Runbook》与 Registry API，
   禁止虚构不存在的 metric、label、端点。
3. 动效齐全但克制：必须覆盖 页面过渡 / 数据刷新增量 / 阈值告警联动 / 组件反馈 /
   面板拖拽缩放 / 状态平滑过渡 六大动效，全部 transform+opacity 优先，本地资源占用低。
4. 智能但要轻量：异常自动识别高亮 / 布局记忆自适应 / 快捷调用 / 异常上下文关联 /
   操作路径提示 五项智能，全部前端本地规则+轻推理，不依赖外部 AI 服务。
5. 性能达标：本地持续刷新 8h 内存平稳，60Hz 下长任务 <50ms，滚动/拖拽不卡顿，
   关闭监听时页面 Timer 停摆。

技术栈（锁定，禁止降级）：
  Next.js 16.3 LTS · React 19 · TypeScript 5.9 strict · Tailwind CSS 4.3
  shadcn/ui (React 19) · TanStack Query v5 · Zustand v5 · Recharts
  TanStack Table v8 · react-hook-form + zod · lucide-react · date-fns
  实时通道：WebSocket(/ws/monitor) + SSE(fetch+ReadableStream) + 轮询降级
  离线层：Service Worker + IndexedDB + localStorage 布局持久化
  前端口袋数据：apps/console-components（与 Token 控制台同源解耦）

设计令牌（复用 YYC³ 品牌）：
  品牌主色 #6C5CE7，信息青 #00D4FF，健康绿 #22C55E，告警橙 #F59E0B，熔断红 #EF4444
  暗色优先，字体 Inter/思源黑体，代码 JetBrains Mono，断点 1440/1280/1024/768
  WCAG 2.2 AA，对比度 ≥4.5:1，支持 prefers-reduced-motion

输出范围：页面体系（主仪表盘/数据监控/实时指标/告警中心/配置管理/日志查询/系统状态）
+ 交互逻辑规范 + 动效触发条件与参数标准 + 智能能力实现路径 + 本地性能约束。
```

---

## 1. 项目定位与数据源契约（落地事实基线）

### 1.1 定位

| 维度 | 值 |
| ---- | -- |
| 使用场景 | 纯粹本机/内网可视化智能看盘 + 全维度中端面板操作系统，单租户自用 |
| 运行方式 | 本地 dev 端口 **3030**（YYC³ 团队约定），生产本地建服务，全离线可跑 |
| 观测对象 | 网关、Registry、模型实例/注册 Agent、推理节点(GPU)、容器日志、Redis/消费组 |
| 关键能力 | 一览总览 · 分域监控 · 实时看板 · 告警管理 · 配置下钻 · 日志检索 · 系统健康自检 |

### 1.2 数据源（全部内网/本地）

| 源 | 访问方式 | 承载内容 |
| -- | ------- | ------- |
| Prometheus | 内网 `/metrics`（prometheus-fastapi-instrumentator） | 标准指标 `http_requests_total` / `http_request_duration_seconds` 等 |
| 规划指标（05 §2.2） | Prometheus 或网关扩展 | `model_backend_latency_ms` · `model_backend_error_rate` · `active_requests` · `gpu_utilization` · `gpu_memory_used` · `model_instance_heartbeat_status` · `registry_sync_lag_seconds` · `sse_ttft_p95` · `breaker_open_count` · `rollback_triggered_total` |
| Loki | 内网 `100.65.172.88:3100`（NAS，30 天保留） | 全量容器日志 + 崩溃关键字查询；标签 `job="dgx-containers"` + `container_name`(真名) + `host` |
| Registry API | 内网 `/registry/v1/*`（需 X-API-Key） | 模型注册/心跳/别名/Canary/Shadow/回滚/SOP-04 触发卡 |
| Redis | 内网 | 心跳状态、Canary hash、消费组、TPM/记账 |
| 本地 env/系统 | 本地文件 | 连接配置、节点 NODE_ID、容器映射表（container-map） |

**离线降级策略**：任一上游不可达 → 数据源状态徽标变「离线」→ 面板切换为该源最近一次本地快照（IndexedDB）+ 明确「快照时间」。整个应用仍可运行、可浏览、可编辑本地配置。

---

## 2. 页面体系（全页面层级）

> 导航信息架构（IA）：左侧一级导航，顶部全局栏（实时时钟 / 数据源连接状态聚合点 / Cmd+K 全局搜索 / 告警铃铛）。
> 每个页面标注：功能模块划分、交互逻辑要点、动效触发点、所依赖的真实指标/端点。

### 2.1 全局壳（App Shell）

| 模块 | 说明 |
| ---- | ---- |
| 侧边导航 | 主仪表盘 · 数据监控 · 实时指标 · 告警中心 · 配置管理 · 日志查询 · 系统状态；可折叠（768 断点收进抽屉） |
| 顶栏 | 当前页标题 · 数据源连接状态聚合点（绿/橙/红 圆点 + 下拉详情）· 本地时钟 · 告警铃铛（未读角标）· Cmd+K 快捷面板 |
| 浮层引擎 | Toast / Drawer / Modal / CommandMenu / ContextPanel 统一弹层，可被任何页面调度 |

**动效挂载（Global）**：侧边折叠 200ms cubic; 顶栏数据源状态点跳动（新增异常时一次 glow); 告警铃铛未读变化时的脉冲（见 4.3）。

### 2.2 主仪表盘（Overview）`/`

| 功能模块 | 内容与数据源 |
| -------- | ----------- |
| 核心 KPI 区 | 总请求 / 总 Token / 平均延迟(p95) / 错误率 / 熔断数 / 活跃请求（06 §2/§2.2） |
| 资源健康带 | 网关服务状态（ollama/zhipu/redis/postgresql）+ GPU 利用率/显存（04/05 §2.2） |
| 心跳总览卡 | 各模型实例心跳年龄 + TTL 三级阶梯视角（90/180/300），断流者醒目红描边（05 §1） |
| 异常速览区 | 自动识别到的异常指标 TopN（智能能力①）→ 一键展开上下文（智能能力④） |
| 快捷操作区 | Cmd+K 同源：打开实时指标 / 查日志 / 进告警中心 / 触发健康自检 |
| 迷你时间轴 | 近 1h 请求 / 错误率 sparkline（下采样渲染） |

**交互要点**：KPI 卡点击 → 跳对应分页并自带目标过滤；心跳卡 hover 显示「最近上报时间 + 节点网络」；异常速览每项带「溯源」按钮。

### 2.3 数据监控面板（Data Monitoring）`/monitor`

| 功能模块 | 内容与数据源 |
| -------- | ----------- |
| 模型域 | `model_backend_latency_ms`(p95) · `model_backend_error_rate`(>10% 标红) · `active_requests`(超 batch 告警) |
| 实例域 | `model_instance_heartbeat_status` · `gpu_utilization` / `gpu_memory_used`(>90% 警告) · `registry_sync_lag_seconds`(>60s P1) |
| 网关域 | `http_requests_total` · `http_request_duration_seconds` · `breaker_open_count`(>3 P2) · `rollback_triggered_total`(>0 P0) |
| 分域时间轴栏 | 每域各自可切 15m/1h/6h/24h，跨域联动（同一时间轴拖选） |
| 探索面板 | 任意选择 metric → 查看原始 PromQL/TS、下钻 label、导出 |

**交互要点**：分域卡通网格布局；时间轴拖选后所有域图表同步缩放；metric 卡片可 pin 到「实时指标看板」。

### 2.4 实时指标看板（Live Board）`/live`

| 功能模块 | 内容与数据源 |
| -------- | ----------- |
| 看板页签 | 用户自定义多看板（如「GPU」「网关」「Registry」），可增删 |
| 面板容器区 | 拖拽/缩放/叠放/钉选面板（复用 .9 动效） |
| 面板类型 | 折线/柱/仪表 Gauge/热力/表格/单位文本（KPI 大字）/状态列表 |
| 订阅入口 | 以 5s 轮询 / WebSocket 增量推送订阅任意 metric 或日志关键字流 |
| 快照/导出 | 当前画面一键截图、批量导出为静态 PNG/CSV |

**交互要点**：面板标题栏含「刷新间隔 / 告警阈值 / 面积开关 / 删除」；点击面板边缘触发拖拽缩放；面板右键/三点菜单进入阈值联动配置。

### 2.5 告警管理中心（Alert Center）`/alerts`

| 功能模块 | 内容与数据源 |
| -------- | ----------- |
| 告警列表 | 活动/已确认/已恢复 三态；字段：级别(P0-P3)·规则·目标·首次触发·持续时间·状态 |
| 告警详情抽屉 | 触发时刻上下文（右侧智能④ 事件上下文）、影响范围、关联日志按钮、建议操作（智能⑤） |
| 规则管理 | CRUD 阈值规则（指标+比较符+持续周期+级别+P0 自动回滚开关）；本地持久化 |
| 抑制/路由配置 | 分级渠道 P0→critical / P1-P2→alerts / P3→info（对齐 05 §2.3） |
| 告警记录时间轴 | 触发→确认→恢复 全生命周期，便于事后复盘 |
| 联动枢纽 | 触发瞬间通知全局（毛刺/呼吸顶栏铃铛），一键跳实时看板或日志查询页 |

**交互要点**：告警行状态颜色严格对齐 05 §2.3 分级；确认动作二次确认；P0 触发自动回滚项需红色紧急标识 + 「回滚」直达按钮（调 Registry）。

### 2.6 配置管理模块（Config）`/config`

| 功能模块 | 内容与数据源 |
| -------- | ----------- |
| 下游上游配置 | env `OPENAI_COMPATIBLE_UPSTREAMS` 可视化编辑（models/capability/priority/weight 字段校验合法性） |
| 路由策略只读 | 五枚举 ADAPTIVE/WEIGHTED_LATENCY/LEAST_CONNECTIONS/RANDOM/ROUND_ROBIN 展示 + 当前生效预览 |
| Canary/Shadow | weight 步进(5→10→30→50→100)、rollback(weight=0)、finalize(alias+DELETE canary)、shadow 采样（对齐 SOP-02） |
| 注册/别名 | Registry `/registry/v1/aliases` 别名接管，归档模型 SOP-04 五命令触发卡一键执行 |
| 本地偏好 | 主题/密度/时区/默认看板/刷新默帧率 |

**交互要点**：所有写操作先 Dry-Run 校验再执行；破坏性操作（清缓存/回滚/归档）需二次确认输入关键字；每项配置显示「来源文件 + 是否落盘/生效」。

### 2.7 日志查询界面（Logs）`/logs`

| 功能模块 | 内容与数据源 |
| -------- | ----------- |
| 查询编辑器 | Loki LogQL：标签选择器 `{job="dgx-containers",container_name=~"xxx"}` 追加匹配算子与关键字；带语法高亮与常用片段 |
| 快捷范围选择 | 时间范围 / 崩溃关键字一键模板（正则 OR 拼接：died unexpectedly、Traceback、RuntimeError）/ 按容器名下拉 |
| 结果结果表 | 虚拟滚动日志行（时间·容器名·host·级别·消息），点击行进上下文展开 |
| 崩溃回放视图 | 命中崩溃关键字的日志自动聚合为「崩溃事件卡片」，支持按事件折叠回放（05 §2.4 崩溃告警诉求） |
| 导出 | 范围导出本地文件 / 剪贴板 |

**交互要点**：日志行增量追加时使用 5.2 增量动效；崩溃事件卡点击 → 自动以此时间窗跳转实时指标看板（智能④ 时间对齐）；Ctrl+Enter 执行查询。

### 2.8 系统状态页（System Status）`/status`

| 功能模块 | 内容与数据源 |
| -------- | ----------- |
| 健康自检 | 一键运行三层健康检查（网关 `/healthz`/`/health`、模型实例 health_path、Registry 心跳 TTL）并输出清单 |
| 节点/容器矩阵 | 按 NODE_ID 聚合推理容器状态、日志外送接管状态、container-name 映射生效状态 |
| 依赖清单 | Prometheus/Loki/Redis/NAS、各自连通性与最近采样时间 |
| 自检报告 | 结构化结果（通过/降级/失败）+ 一键复制/导出，作为排障取证 |
| 恢复中心 | 挂接 `dsv4-recover.sh` 五模式(CHECK/RECOVER/ROOTCAUSE/LOGS/WATCH) 入口 + 根因矩阵（05 §6） |

**交互要点**：健康条每项带「重跑」；节点卡异常时红描边 + 进入 5.3 告警联动动效；WATCH 自愈开关可见状态切换动画（6.6）。

---

## 3. 交互逻辑规范

### 3.1 全局交互基线

- **五态覆盖**：每个页面/组件必须具备 默认/加载(Skeleton)/空(EmptyState)/错误(ErrorState)/成功 五态；实时页追加 流式中/中断 两态。
- **键盘可达**：全部可交互元素可 Tab 聚焦且有可见焦点环；Cmd+K 全局命令面板；Esc 关弹层；方向键导航表格/看板。
- **破坏性操作确认**：分三级——轻(Toast)/中(ConfirmDialog)/重(输入关键字二次确认)，参考 `config`/`alerts` 破坏性路径。
- **数据新鲜度标识**：每个数据区带「xx 秒前更新」与刷新按钮；离线降级区用「快照 xx:xx」灰标注区分。
- **响应式**：1440 主 / 1280 / 1024 / 768（侧边收进抽屉）；看板网格列数随断点缩减。

### 3.2 实时数据流规范

| 通道 | 用途 | 重连策略 |
| ---- | ---- | ------- |
| WebSocket `/ws/monitor` | 低延迟增量（心跳翻转/告警/Canary 事件） | 指数退避 1s→2s→4s…上限 30s |
| SSE(fetch+ReadableStream) | 指标增量订阅、SSE 流式 | 同上；失败自动切轮询 |
| 轮询 | 通配降级（5s 默认，看板面板可独立配） | TanStack Query refetchInterval |

> ⚠️ 禁止使用 `EventSource`（形如 Token 控制台约定：需 POST/自定义头时一律 fetch+ReadableStream）。

### 3.3 统一状态色彩令牌（跨全站）

| 语义态 | 色值 | 用途 |
| ------ | ---- | ---- |
| ready/healthy | #22C55E | 正常、心跳存活、熔断 closed |
| warning/degraded | #F59E0B | 预警、half_open、降级路径 |
| danger/open | #EF4444 | 熔断 open、P0、心跳丢失 |
| info/observe | #00D4FF | 观察、Shadow、信息提示 |
| neutral/offline | 灰阶 | 快照态、配置态、无关数据 |

状态映射为语义 token（`color/status/*`），禁止硬编码色值。

---

## 4. 全维度动效体系

> **总原则**：动效是「信息传达」不是「装饰」。所有动效只操作 `transform`/`opacity`（GPU 合成层），禁用触发重排的属性；统一 `prefers-reduced-motion: reduce` 时全部降级为 0ms 或透明度渐隐。
> **默认动效字表**：默认 `cubic-bezier(0.4,0,0.2,1)`；入场 `cubic-bezier(0.16,1,0.3,1)`（ease-out-expo）；出场缓慢 `cubic-bezier(0.4,0,1,1)`。

### 4.1 页面切换过渡动效

| 属性 | 参数标准 |
| ---- | ------- |
| 触发条件 | 路由切换（App Router layout 包裹出口）；首次挂载；Tab 页签切换 |
| 效果 | 内容区 crossfade + 轻微向上位移（8px）；旧页 opacity 0.15s 退场 → 新页 0.22s 入场 |
| 时长 | 退场 150ms + 入场 220ms，总 ≤ 400ms |
| 曲线 | 入场 `cubic-bezier(0.16,1,0.3,1)` |
| 性能 | 仅 opacity+transform；非首帧数据延迟水合，避免入场时刷屏闪 |
| 语义 | 同层级 Tab 切换用位移更小（4px）的「滑动」；跨层级（进详情）用「抽屉/存在感放缩」 |

### 4.2 数据刷新增量动效

| 属性 | 参数标准 |
| ---- | ------- |
| 触发条件 | 轮询/WebSocket 增量到达，且值相对上一快照发生变化 |
| 数字变化 | 差值 > 阈值时 count-up 600ms；负向用同曲线但不同颜色箭头（↑绿/↓红/持平灰） |
| 单元格高亮 | 变化行/单元底色从语义色 40% 透明度脉冲至 0，600ms，衔接下一轮 |
| 新行插入 | 日志/列表新行 translateY(12px)+opacity 进入 240ms |
| 图表更新 | 折线重绘时同步一次「数据点闪烁/面积填充」500ms；过低频（sparkline）禁用增幅 |
| 性能 | 更新批处理走 rAF；变化检测仅在 diff 后触发；离屏面板暂停其定时器 |

### 4.3 阈值告警联动动效

| 属性 | 参数标准 |
| ---- | ------- |
| 触发条件 | 某指标首次越过阈值（进入 warning/danger），或级别 P0/P1 变化 |
| 卡/行描边 | 变换为状态色 1-2px 描边 + 一次 box-shadow 外发 glow（0→8px→0，800ms）——仅 1 次，非循环，避免常耗 |
| 顶部聚合点 | 顶栏数据源状态点出现一次脉冲缩放（1→1.25，600ms）；告警铃铛未读角标用「跳动」提示 |
| 持续驻留 | 异常期间卡保持状态色描边 + 左上角小徽点常驻（无动画），直到被确认 |
| 联动扩散 | 相关面板/相关心跳卡 300ms 延迟依次高亮，形成「扩散链」提示因果 |
| 性能 | glow/脉冲不重复触发（节流 5s）；等待确认前不连续播 |

### 4.4 组件交互反馈动效

| 属性 | 参数标准 |
| ---- | ------- |
| 按钮按下 | scale 0.97，100ms；hover 背景过渡 150ms；focus 可见环 2px 品牌色 |
| 悬停浮层 | Tooltip/Popover 淡入上移 4px，150ms；延迟显现 120ms 防抖 |
| 开关/滑杆 | 常态 150ms；切换「开/自动」时 250ms 非线性 |
| 命令面板 | Cmd+K 打开 180ms + 微缩 0.98 入场；选择项高亮回弹 120ms |
| 空/错误态 | 淡入 200ms；错误态含图标呼吸指示（低频 1.5s，易重试强调） |

### 4.5 面板拖拽/缩放动效

| 属性 | 参数标准 |
| ---- | ------- |
| 触发条件 | 实时看板/主仪表盘面板网格的拖拽移动、边缘缩放、叠放 pin |
| 实现 | 全程 `transform` 随指针移动（rAF 节流 60fps），释放时吸附 8px 网格（FLIP 平滑过渡 200ms） |
| 智能吸附 | 拖拽近邻图元相邻宽/高时吸附提示（≤24px），显示对齐引导线 |
| 持久化 | 位置/尺寸变化后 `debounce 800ms` 写入 localStorage（智能能力② 的记忆层） |
| 性能 | 拖拽期间禁止 Chart 重绘（暂停订阅+降采样）；仅移动合成层；释放后再恢复 |

### 4.6 状态变更平滑过渡动效

| 属性 | 参数标准 |
| ---- | ------- |
| 触发条件 | 任何语义状态切换：健康↔降级↔熔断、心跳丢↔恢复、Canary weight 升降、日志外送接管 on/off |
| 效果 | 颜色以 300ms 在相邻状态间过渡（color/interpolate），图标形态切换用 FLIP/SVG 描边渐变 |
| 自动回滚可视化 | P0 回滚执行中：目标卡进入「进度环 + 倒计时」旋转动画，完成后平滑切回就绪 |
| 性能 | 过渡仅 color/transform；状态机（statechart）驱动避免无意义中间帧 |

---

## 5. 智能能力实现路径（本地轻量化，不依赖外部 AI）

> 所有智能均在本机规则引擎/统计计算内完成，数据不出内网。实现建议放 `apps/components/ops/smart/`，保持解耦可插拔。

### 5.1 数据异常自动识别与高亮（智能①）

- **多判定器**（组合计分）：静态阈值（如 `error_rate>10%`、`latency_p95>2000ms`）＋ EWMA 基线偏差（最近 1h 指数移动均值 ±3σ）＋ 滚动 z-score（窗口 30min）＋ 突变检测（相对前一窗口 jump）＋ 心跳中断（`model_instance_heartbeat_status=0` 或年龄 >90s）。
- **实现路径**：订阅原始时序 → 客户端微窗口引擎（O(n)/窗口滑动）生成 `anomaly {metric,label,timestamp,severity,reason[],sources[]}` → 存入内存告警队列 → 推送「异常速览区」并挂载 4.3 高亮动效。
- **约束**：标注「规则/偏差」来源，异常需可一键忽略/确认（写本地 rules 白名单）。

### 5.2 面板布局智能记忆与自适应（智能②）

- **记忆**：实时看板布局（面板位置/尺寸/页签顺序/每面板阈值与刷新间隔 / 每域钉选状态）序列化入 IndexedDB/localStorage（`operator:panel-*`），刷新与下次打开 100% 还原；拖拽释放 debounce 800ms 落盘（4.5）。
- **自适应**：断点切换时按设计稿栅格重排；异常高频面板可自动提升到看板顶部（由 5.1 的活跃异常数加权，可在设置开关）。
- **实现路径**：`useGridLayout` hook 封装 react-grid-layout，持久化 schema 版本号以便迁移。

### 5.3 常用功能快捷调用（智能③）

- Cmd+K 全局命令面板，对页面、动作、动画语境索引做前端模糊/前缀匹配（内存索引，构建时由路由与动作清单生成，无需网络）。
- 在实时看板/主仪表盘提供「最近使用 + 高频」快捷格（本地点击计数 TopN）。
- 深链：如 `/live?metric=gpu_utilization`、`/logs?expr=崩溃模板` 一键直达。

### 5.4 指标异常自动关联上下文信息（智能④）

- 异常触发器产生时，自动收集时间窗 [T-2min, T+30s] 的：相关 Loki 崩溃日志、相关模型/上游/Registry 状态、相关告警记录、canary/回滚事件——组装为「事件上下文抽屉」，挂在告警详情与异常速览。
- **关联规则**：按 `metric 的 label（model/container/node）` 与日志 `container_name`、告警 `rule 目标` 做标签匹配；无显式匹配时回退为同时间窗+同 `host/job`。
- **实现路径**：`correlator` 模块（标签键归一 + 时间窗对齐），查询走内网 Loki/Registry；结果缓存 5min。
- **附加**：一键「跳转日志查询页」并自动填入 `{job="dgx-containers"} |= 崩溃模板` 且时间窗对齐，形成 4.4 扩散链。

### 5.5 操作路径智能提示（智能⑤）

- **规则建议引擎**：状态机在特定状态变体下给出「下一步最佳动作」，例：心跳丢失 → 建议 `dsv4-recover.sh CHECK/ROOTCAUSE` 并给出根因矩阵命中项；Canary error_rate 恶化 → 提示 rollback；熔断 open → 提示触发 router/health 半开探测。
- **近期操作学习**：本地记录「异常→用户实际动作」序列（仅存本地），当同类异常再次出现时把历史动作置顶建议。
- **实现路径**：`advisor` 前端规则库（if-then 启发 + 最近操作加权），输出动作卡带直达按钮；所有建议标注为「本地建议」，非自动执行（除非 P0 自动回滚开关开启）。

---

## 6. 本地性能约束（硬指标）

| 维度 | 约束标准 |
| ---- | ------- |
| 渲染帧率 | 持续刷新/拖拽时 FPS ≥ 55（60Hz）；滚动无 jank |
| 主线程 | 长任务 < 50ms；首屏可交 3s 内（按本机磁盘/浏览器规模） |
| 内存 | 8h 常驻内存平稳（无持续增长泄漏）；IndexedDB 快照总量配额内分片淘汰 |
| 图表 | 更新 ≤30fps 节流；长时序降采样（LTTB）后渲染；recharts 轻量化复用 |
| 列表/日志 | 虚拟滚动（react-window），单屏只渲染可见行 |
| 离屏节流 | `IntersectionObserver`/页面可见性暂停离屏与后台面板的定时器/订阅 |
| 动效 | 一律 transform+opacity；禁用 layout-thrashing 型属性（width/height/top 动画）；glow/脉冲节流防长耗 |
| 网络 | 内网高频订阅合并为 WS 增量，轮询最小 5s；突变稀少指标可 15s |
| 构建 | 路由级 Code-Splitting；图表/虚拟滚动/编辑器按需动态 import；Lighthouse Performance 目标 ≥90（本地） |

### 6.1 性能自检清单（文档门禁）

- [ ] 60Hz 持续刷新 10min：FPS≥55，无 long task>50ms
- [ ] 切换页面不丢帧，入场无序贯抖动
- [ ] 拖拽面板 60fps，释放吸附无跳变
- [ ] 1000 行日志滚动流畅，仅渲染可见区
- [ ] 8h 内存无持续增长
- [ ] 全站动效仅在 transform/opacity
- [ ] 断网降级到快照仍可完整浏览

---

## 7. 技术落地映射与路由

```text
/             Overview        主仪表盘
/monitor      Data Monitoring 数据监控
/live         Live Board      实时指标看板
/alerts       Alert Center    告警中心
/config       Config          配置管理
/logs         Logs            日志查询
/status       System Status   系统状态
```

| 组件 | 代码路径建议 |
| ---- | ----------- |
| KPI/StatCard / StatusDot / Badge | 复用 shadcn + 状态语义令牌 |
| AnomalyCard / EventContextDrawer | `components/ops/smart/AnomalyCard` · `EventContextDrawer` |
| LogVirtualList / CrashPlayer | `components/ops/logs/LogVirtualList` · `CrashPlayer` |
| LiveBoardGrid (useGridLayout) | `components/ops/live/LiveBoardGrid` |
| AdvisorCard / CommandPalette | `components/ops/smart/AdvisorCard` · `CommandPalette` |
| 状态令牌单一真源 | `app/globals.css` `@theme`(`color/status/*`) |

---

## 8. 实现落点与验收

### 8.1 建议分阶段

- **P0（骨架+总览）**：App Shell + 顶层导航 + Overview KPI/资源带/心跳卡 + Service Worker 离线 + 动效基础令牌系统。
- **P1（监控+日志）**：Data Monitoring + Logs(虚拟滚动+崩溃回放) + WS/SSE 实时通道 + 指标真实契约。
- **P2（看板+告警+智能）**：Live Board(拖拽缩放+布局记忆) + Alert Center(规则/分级/联动) + 五维智能中的异常识别①与上下文关联④。
- **P3（配置+健康+智能收口）**：Config(Canary/别名/SOP-04) + System Status(恢复中心) + 快捷调用③/操作路径提示⑤/布局自适应②。

### 8.2 验收（对照本文档）

- [ ] 七大页面全部上线，每页五态完备
- [ ] 实时通道 WS/SSE/轮询三态切换无数据断层
- [ ] 六大动效全部落地且遵循 4.x 参数标准
- [ ] 五项智能全部回调真实数据并全程本地
- [ ] 断网离线浏览任意页面可用（快照降级）
- [ ] 通过 §6.1 性能自检清单全项
- [ ] 所有指标/端点与《05-监控告警与Runbook》一致，无虚构字段

---

## 变更记录

| 版本 | 日期 | 变更 |
| ---- | ---- | ---- |
| v1.0.0 | 2026-10-09 | 初始版本：七大页面体系 + 六维动效参数标准 + 五项本地智能实现路径 + 本地性能硬约束，对齐 05 监控文档与 04 Token 控制台技术基线 |
