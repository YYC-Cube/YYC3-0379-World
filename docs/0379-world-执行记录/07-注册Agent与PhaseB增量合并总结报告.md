---
file: 07-注册Agent与PhaseB增量合并总结报告.md
description: 0379-World TOP2/TOP3 执行 + N1:8001 502 根因诊断 + 变量文档补全 - 2026-09-28
author: AI Tutor <yyc3-expert>
version: v1.0.0
created: 2026-09-28
updated: 2026-09-28
status: stable
tags: [summary],[register-agent],[phase-b],[502-diagnosis],[variables]
category: report
---

# 📋 注册 Agent + Phase B 增量合并 + 502 诊断总结报告

## 一、N1:8001 dsv4 502 根因诊断（P1 观察，处置建议）

### 1.1 诊断链（三层递进实证）

| 层 | 手段 | 结果 |
| -- | ---- | ---- |
| 端口矩阵（NAS 侧） | /dev/tcp 探测 N1×4 + N2×3 | 仅 **N1:8001 CLOSED**（5.6ms 拒连 = 无监听进程，非网络过滤）；8100/8101/11434/N2 全 OPEN |
| 节点登入（yyc3-101） | docker ps/inspect | `dsv4-head` 容器 **running 31h** 但为**僵尸容器**——引擎已死容器未退 |
| 引擎日志 | docker logs | **09-26 23:54:26 `RayWorkerProc rank=[1] died unexpectedly, shutting down executor`**；raylet 报 **host 内存 OOM 杀 worker**（非 GPU 显存） |

### 1.2 根因定论

Ray 宿主内存 OOM（09-26 23:55）→ TP worker rank=1 被杀 → vLLM 引擎关闭 → :8001 无监听 → 网关 502（flagship-dsv4 与 registry 镜像同地址无法互救；ollama 兜底因无该模型而 4xx）。与 Phase 7 SMOKE_FAIL 同源，宕机至今 ~2 天。

### 1.3 处置建议（生产动作，待用户执行）

1. **立即恢复**：`ssh yyc3-101 && docker restart dsv4-head`（权重冷加载需数分钟；恢复后 :8001 自愈，网关熔断 30s 半开自动回归）
2. **防再发（OOM 缓解）**：
   - 容器内存限额 + 预留：compose `mem_limit` 低于宿主 RAM，防 raylet 全量挤压
   - 或调 Ray 阈值：`RAY_memory_usage_threshold=0.9` / 关闭 monitor（`RAY_memory_monitor_refresh_ms=0`，治标）
   - 根因面：N1 常驻 worker 0.72 + canary + embed + rerank 共存——评估 canary（Up 10 天）去留释放宿主内存
3. **可观测补口**：网关主动验活对「容器活引擎死」无效（/health 不通权重减半但仍留池）——建议 dsv4 侧补进程级 watchdog（或由 register_agent 心跳语义天然覆盖：停跳 300s 自动摘除，**TOP2 落地后此缺口自愈**）

## 二、TOP2：register_agent.py（注册 Agent 落地）

**文件**：[core/scripts/model_register_agent.py](../../core/scripts/model_register_agent.py)（stdlib 零依赖，DGX/NAS python3 直跑）

**生命周期**（规范 02 §5.3）：`wait /health 200 → POST 注册（model-meta.json + --set 覆盖）→ PATCH ready → 30s 心跳（runtime 指标自 /health 尽力抽取）→ SIGTERM 优雅 offline`；心跳停超 300s 由 Registry TTL 兜底摘除。认证走 `--admin-key-env`（缺省 ADMIN_API_KEYS）。

**测试**：11 用例快层（payload 归一/覆盖语义/健康 URL/指标抽取/状态机各步骤 HTTP 桩）。

## 三、TOP3：Phase B 增量合并（事件驱动免重启）

**实现**：[model_registry_svc.py](../../core/api/services/model_registry_svc.py) 新增 `_handle_registry_event`（registered/updated → 全量重合并；deregistered → 定点摘除）+ `start/stop_merge_consumer`（pub/sub `yyc3:registry:events` 订阅循环）；[main.py](../../core/api/main.py) startup/shutdown 挂载（REGISTRY_ENABLED=true 时）。

**测试逮出并修复真实缺口**：原 merge 只增不删——ready→offline 后池内残留陈旧条目。修为**全量对账**（本次产出集之外的 registry-* 一并清池，env 条目零触碰）。

**生产免重启四态闭环验证**（cffd3cd 部署后，无任何网关重启）：

| 操作 | 池态（7s 内） | 日志 |
| ---- | ------------ | ---- |
| 注册+ready | `registry-phaseb-live` **即现**（6 条） | 事件重合并 6 上游 |
| PATCH offline | **即失**（5 条） | 对账摘除陈旧上游 |
| 重 ready | **复现**（6 条） | 事件重合并 6 上游 |
| DELETE 注销 | **即清**（5 条） | 事件摘除 |

## 四、变量文件与文档补全

| 文件 | 变更 |
| ---- | ---- |
| [变量清单.md](../核心参考/变量清单.md) | 新增「🌐 网关应用变量」节：REGISTRY_ENABLED（缺省/现值/语义）+ ADMIN_API_KEYS 复用 + env 通道关系 + Agent CLI 参数 + 代码常量（事件频道/TTL 阶梯） |
| [.env.example](../../core/config/.env.example) | REGISTRY 段补 Phase B 语义 + 注册 Agent 用法示例（生命周期一行说明） |
| [规范 README](../模型接入与注册/README.md) | 状态表：register_agent ✅（TOP2）+ Phase B 增量合并 ✅（含对账语义）——附录 A 仅剩 model_smoke_test.py 一项 📋 |

## 五、门禁与统计

| 门禁 | 结果 |
| ---- | ---- |
| 快层全量 | ✅ **142 passed**（+11 agent） |
| integration（消费者 6 + registry 27 回归） | ✅ 全绿 |
| lint 三件套 + doc_links | ✅ 通过 |
| 生产验证 | ✅ Phase B 四态闭环（免重启）+ 探针清零（池内恒 5 生产条目） |

| 指标 | 值 |
| ---- | -- |
| 新增源文件 | 1（agent 220 行）+ 测试 2 |
| 修改源文件 | 3（svc/main/upstream_registry） |
| 文档 | 3（变量清单/.env.example/规范 README） |
| 提交 | cffd3cd（已推 main，NAS 已部署验证） |

## 六、遗留与下轮建议

1. **[P1] dsv4-head 重启**（§1.3 建议，用户执行）+ OOM 缓解评估——TOP2 心跳语义部署后此类「僵尸容器」将 300s 自愈摘除
2. **[P2] model_smoke_test.py**：规范附录 A 末项（上线冒烟自动化九用例）
3. **[P2] 注册 Agent 真接入**：dsv4/embed/rerank/asr/ocr 五服务侧拉起 agent（心跳生命周期接管现手动模式注册，需节点侧 systemd/容器入口配合）
4. **[P3] canary 容器去留评估**（N1 宿主内存压力源之一）

---

**报告状态**: ✅ TOP2/TOP3 执行完毕 + 502 定论
**生产终态**: NAS @cffd3cd；池内 registry×5 + env×7；Phase B 消费者运行中
