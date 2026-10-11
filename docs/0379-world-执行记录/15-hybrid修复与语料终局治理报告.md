---
file: 15-hybrid修复与语料终局治理报告.md
description: 0379-World P1 深化三轮——hybrid 负收益归因与三修（81%）+ 8B 时延实验定案 + 会话语料摘除 - 2026-09-28
author: AI Tutor <yyc3-expert>
version: v1.0.0
created: 2026-09-28
updated: 2026-09-28
status: stable
tags: [summary],[hybrid],[rrf],[bm25],[latency],[corpus-governance]
category: report
---

# 📋 hybrid 修复与语料终局治理报告

> 14 报告下轮 TOP3 全闭环。**头条：hybrid 三修后 61.0% → 81.0%（+20pp），以零时延代价登顶四配置**——生产推荐从 `rerank=true` 改判 `hybrid=true`。

## 一、T1 hybrid 负收益归因与三修 ✅（本轮最大收益）

### 1.1 归因（v4·100 题逐题 diff：vec 命中 hybrid 失误 10 题 / 反向 6 题）

| 病灶 | 机制 | 受害题 |
| ---- | ---- | ------ |
| **RRF 同 key 灌分**（主因） | `rrf_fuse` 对同 key（source::heading）多 chunk 在单通道占 N 个 rank 位**逐位累加** →「📂 完整功能模块组件文件树架构」19 个同标题 chunk 霸榜 | q36/q59/q13/q88/q89 |
| BM25 索引无 heading | 标题词面（如「项目目录结构」）无法直配正文词 | q32/q89 |
| 中文单字歧义 | "API/组件/链路"等泛词单字匹配淹没精确节 | q8/q37/q63/q46 |

### 1.2 三修（ops_rag v1.2.0）

1. **rrf_fuse 同 key 首现去重**：单通道内重复 key 只计首现 rank（回归护栏用例 `duplicate_key_no_stuffing` 锁死）
2. **`_index_text`**：BM25 索引文本 = heading 前置 + 正文（load/reindex 双路径统一）
3. **`_tokenize` 中文 bigram**：相邻 CJK 单字产出双字组合（跨英文词不产），消歧义

### 1.3 量化（v4·100 题 · 治理后语料 394 chunks）

| 配置 | 修复前 | 修复后 | 时延 |
| ---- | ------ | ------ | ---- |
| vec | 65.0% | 65.0% | ~270ms |
| **hybrid** | 61.0% | **81.0%（+20pp）** | **276ms（零代价）** |
| rerank-8B | 75.0% | 75.0% | 1845ms |
| hybrid+rerank | 61.0% | 81.0%（持平 hybrid） | 842ms |

**生产定案更新**：`{"library":"main","hybrid":true}`——+16pp 于 vec、零时延；rerank 降为备选（hybrid 排序已足够强，重排无增量且 3 倍时延）。**相对 09-27 起点 55% → 81%（+26pp）**。

## 二、T2 8B 时延实验定案 ✅（判：kernel 层无红利）

| 实验 | 配置 | 端到端均值 | 结果 |
| ---- | ---- | ---------- | ---- |
| 基线 | eager + util 0.16 | ~2.29s（2.11-2.50） | 现状 |
| CUDA graph | 去 eager + util 0.20（0.16 下 graph 捕获吞 KV 必挂，实测 0.11G<需 0.56G） | ~2.20s（2.05-2.36） | **仅 ~4%，判无价值** |

**归因**：瓶颈在 12 候选 × ~1000 token prefill 总量，非 kernel 执行。真优化方向（候选 ×4→×3 / doc 截断 1500→1000）因 hybrid 已 81% 不依赖 rerank 而降为低优先级。**终态：保持 eager 0.16**（重启快 + 省显存 4G），实验结论入档防重试。

## 三、T3 会话文档语料摘除 ✅

01/02/03 三份会话文档 23 chunks（5+11+7）出库（时效性语料不混知识库）：417→394，BM25 reindex 同步；v4 评测无 golden 项受损，vec/hybrid 分数不受影响（65/81 即摘除后实测）。回滚件：N2 `/tmp/main_backup_20260928_r2.json`（417 全量）+ `/tmp/deleted_session_20260928.json`（删除 ID）。

## 四、会话累计（P1 主线全程）

| 阶段 | main 库 hit@3 | 配置 |
| ---- | ------------- | ---- |
| 09-27 基线（v2·40 题） | 55% | vec（降级 0.6b） |
| 深化一轮（v3·40 题） | 75→80% | rerank 0.6b→8B + 去重 |
| 深化二轮（v4·100 题） | 74% | rerank-8B |
| **深化三轮（本轮）** | **81%** | **hybrid 三修** |

## 五、下一步建议

1. **[P2] 26% 失误带攻坚**：剩余 19 miss 集中在长尾文档（单 chunk 文档向量信号弱）——可试 chunk 重切（标题感知分块）或 query 改写
2. **[P3] 摘除常态化机制**：reindex 管道加语料准入规则（会话文档/时效文档黑名单），防再混入
3. **[P3] rerank 降级链验证**：hybrid 为主后 rerank-n2-8b 冷却，池序保留（能力面兜底）

---

**报告完** · 2026-09-28 · AI Tutor yyc3-expert
