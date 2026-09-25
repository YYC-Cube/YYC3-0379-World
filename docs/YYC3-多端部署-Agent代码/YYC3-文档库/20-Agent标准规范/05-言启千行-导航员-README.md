<!--
  ============================================================
  YYC³ AI Family — 人从众曌众从人
  亦师亦友亦伯乐 · 一言一语一协同
  拟人为本，AI为核，纯粹为心
  ============================================================
  Document : 05 言启·千行 Navigator 标准规范
  Version  : v1.1.0
  Contact  : admin@0379.email
  Homepage : https://matrix.yyc3.top
  License  : Apache-2.0 · 永久开源
  ============================================================
-->

# 05 言启·千行 Navigator — 导航员 · 意图识别

![言启·千行](https://img.shields.io/badge/言启·千行-导航员-%230088cc?style=for-the-badge&logo=compass)

> 🌹 **YYC³ AI Family** — 人从众曌众从人 · 亦师亦友亦伯乐，一言一语一协同
> 「一言启千行」—— 一句自然语言，启航千行协同。

## 一、成员档案（拟人化协同架构对齐）

```
┌──────────────────────────────────────────────┐
│ 🧭 言启·千行 Navigator                       │
│ 导航员 · 意图识别 ｜ 业务执行层               │
│ 家族角色：用户与全体成员的连接枢纽            │
│ 九层架构定位：第八层 · AI Family层（入口）    │
└──────────────────────────────────────────────┘
```

**核心职责**
- 用户意图识别与分类
- 任务路由与 Agent 调度
- 对话上下文管理
- 进度跟踪与状态同步

**🔗 五维映射**
- ⏱时间维：意图识别 <200ms
- 💾空间维：轻量级快速响应
- 🏷属性维：意图准确率 >95%
- 📝事件维：全链路追踪（trace_id 透传）
- 🔗关联维：连接用户与所有 Agent

## 二、五维五高五标五化对齐

| 维度 | 对齐项 |
| ---- | ------ |
| 五高-高性能 | nemotron-mini-4b 多实例并发，单请求 <200ms |
| 五高-高可用 | LLM 降级自动切换关键词规则兜底路由，链路永不断航 |
| 五高-高扩展 | 标准意图分类集可插拔扩充，新增意图不改路由框架 |
| 五标-标准化 | 8类标准意图 × 3级复杂度（simple/complex/multi_agent）判定规范 |
| 五标-规范化 | trace_id 格式 `trace-YYYYMMDD-xxxxxx`，全链路唯一 |
| 五标-可视化 | `format_output` 置信度头 + 风险提示尾 |

## 三、ReAct-C 协同工作流对齐

- **Step2 意图识别与任务路由**：LLM 分类 → JSON 解析 → 合法性校验 → trace_id 生成
- 输出结构标准：`{intent, complexity, need_rag, trace_id}`
- **末段格式化**：最终结果结构化输出给用户（对齐架构 T8：附带置信度与风险提示）

**标准意图分类集**：data_analysis / trend_forecast / report_polish / creative_brainstorm / personnel_development / knowledge_query / code_development / multi_agent_comprehensive

## 四、接口规范

| 方法 | 签名 | 说明 |
| ---- | ---- | ---- |
| `run` | `(prompt, context="") -> dict` | 意图识别与路由（重写基类返回结构化 dict） |
| `_rule_based_route` | `(user_input) -> dict` | 关键词规则兜底（内部方法） |
| `format_output` | `(final_output, confidence, risk_notes) -> str` | 结构化格式化输出 |

详细参数表、错误码与调用示例见 [API.md](API.md)。

## 五、模型与部署映射

nemotron-mini-4b-instruct ｜ 节点2 ｜ 多实例并发 ｜ 与知遇伯乐共享轻量基座服务

## 六、协同关系

- **上游**：用户请求第一站（Step1 安全过滤之后）
- **下游路由**：按意图分发至语枢/预见/创想/知遇，multi_agent 交元启天枢
- **映射定位**：管-管理流程主责（与格物宗师协同）、高-高效执行主责（与语枢万物协同）、协-协同化主责（与创想灵韵协同）

## 七、典型场景

- 综合经营报告请求 → 识别 multi_agent_comprehensive → 路由元启天枢总指挥
- 代码问题 → code_development → 无需 RAG 快速直达
- LLM 故障期间 → 规则兜底保障基础导航能力

## 八、代码

见 [yanqi_qianhang_agent.py](yanqi_qianhang_agent.py)。

---
<p align="center">
  🌹 <b>YYC³ AI Family</b><br>
  人从众曌众从人 · 亦师亦友亦伯乐<br>
  <sub>永久开源 · 感恩前行 · <a href="https://matrix.yyc3.top">matrix.yyc3.top</a></sub>
</p>
