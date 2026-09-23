---
file: 04-zhipu同步入口漏接修复测试报告.md
description: zhipu.chat_completion 同步入口漏接 _ensure_key 缺陷的修复验证与回归测试报告
author: AI Tutor <glm5-turbo>
version: v1.0.0
created: 2026-09-23
updated: 2026-09-23
status: stable
tags: [test-report],[bugfix],[zhipu],[error-handling]
category: report
---

# 🧪 测试报告：ZHIPU 同步入口漏接 `_ensure_key` 修复验证

## 基本信息

| 属性 | 值 |
| --- | --- |
| **缺陷编号** | BUG-v5-001 |
| **严重程度** | High（功能性缺陷：配置缺失场景返回误导性状态码） |
| **发现途径** | v5 轮全局深度扫描（安全审计 + 修复完整性复查） |
| **修复提交** | `5f58240` fix(tooling+gateway): IDE 导入解析三件套 + zhipu 同步入口漏接 _ensure_key 修复 |
| **测试环境** | macOS / Python .venv（fastapi 0.141.1）/ pytest 7+ / `--strict-markers` |
| **报告日期** | 2026-09-23 |

---

## 一、缺陷概述

### 1.1 背景与声明差异

v4-T1 轮（2026-09-20）为解决「ZHIPU_API_KEY 空 Key 时拼出非法请求头 → 模糊 502」问题，在 [zhipu.py](/Users/yanyu/YYC-Cube/YYC3-0379-World/core/api/services/zhipu.py) 新增 `_ensure_key()` 前置校验，并在 03 文档中声明「**双入口**均接入」。

v5 轮深度扫描复核发现：**修复仅落地了流式入口，同步入口被遗漏**。

### 1.2 缺陷代码位置

| 入口 | 修复前代码 | 位置 | 状态 |
| --- | --- | --- | --- |
| 流式 `chat_completion_stream` | `Bearer {_ensure_key()}` | [zhipu.py#L142](/Users/yanyu/YYC-Cube/YYC3-0379-World/core/api/services/zhipu.py#L142) | ✅ v4 已修复 |
| **同步 `chat_completion`** | `Bearer {_get_zhipu_key()}` | [zhipu.py#L68](/Users/yanyu/YYC-Cube/YYC3-0379-World/core/api/services/zhipu.py#L68) | 🔴 **v5 发现并修复** |

---

## 二、根因与传播链分析

### 2.1 缺陷机理

`_get_zhipu_key()` 在空 Key 时返回空串，请求头拼为 `Bearer `（尾随空格的非法 HTTP 头值）。httpx 在本地构造请求时即抛异常，**请求从未发出**，异常消息形如：

```
Illegal header value b'Bearer '
```

### 2.2 错误传播链（修复前，同步路）

```
chat.py _handle_sync (L388)
  └─ with_retry(max_retries=2, delay=1.0)(backend.chat_completion)  # zhipu, L435 附近
       └─ zhipu.chat_completion L68: Bearer {_get_zhipu_key()}      # 空串
            └─ httpx 抛 Illegal header value（非 YYC3Error 类型）
                 └─ error_handler.handle(e)  [handler.py#L51 _classify_error]
                      └─ 字符串分类："illegal header value" 不含 timeout/network/api/validation 关键词
                           └─ 兜底归类 "api" → APIError(status_code=502)  [handler.py#L95]
                                └─ raise HTTPException(status_code=502, detail=...)
```

**用户侧表现**：`502 API_ERROR`，message 为 httpx 内部异常文本——既不指示根因（Key 未配置），状态码语义也完全错误（401 配置问题伪装成 502 网关故障）。运维排障时会在「上游网关」方向空耗时间。

### 2.3 传播链（修复后）

```
chat.py 同步路
  └─ zhipu.chat_completion L68: Bearer {_ensure_key()}
       └─ 空 Key → 抛 APIError(status_code=401, message="智谱 AI 未配置：请设置 ZHIPU_API_KEY 环境变量")
            [exceptions.py#L62 APIError 为 YYC3Error 子类]
                 └─ handler.py#L91 _format_response: isinstance(error, YYC3Error) → error.to_dict() 原样保真
                      └─ raise HTTPException(status_code=401, detail={"error":"API_ERROR","message":"智谱 AI 未配置：…","status_code":401,"details":{"env":"ZHIPU_API_KEY","hint":"…"}})
```

**用户侧表现**：`401 API_ERROR` + 明确的 env 变量名与申请指引，可自愈排障。

---

## 三、修复内容

### 3.1 产品代码（1 行）

```python
# core/api/services/zhipu.py L68
-  "Authorization": f"Bearer {_get_zhipu_key()}",
+  "Authorization": f"Bearer {_ensure_key()}",
```

### 3.2 回归测试（新增 1 用例）

[test_zhipu_empty_key_raises_401](/Users/yanyu/YYC-Cube/YYC3-0379-World/tests/test_guardrails_and_providers.py#L151)（`@pytest.mark.anyio` 异步用例）：

```python
monkeypatch.delenv("ZHIPU_API_KEY", raising=False)          # 清 env
monkeypatch.setattr(zhipu.settings, "zhipu_api_key", "")    # 清 settings 兜底

# 断言 1：同步入口
await zhipu.chat_completion(...)   →  APIError, status_code == 401, "ZHIPU_API_KEY" in message

# 断言 2：流式入口（async 生成器首次迭代时触发校验）
async for _ in zhipu.chat_completion_stream(...)  →  APIError, status_code == 401
```

**设计要点**：
- 双重隔离（env + settings）防止宿主机残留 `ZHIPU_API_KEY` 导致假阴性；
- 流式入口为 async generator，`_ensure_key()` 在**首次迭代**时才执行，故用 `async for` 驱动触发，而非仅构造调用；
- 断言消息含 `ZHIPU_API_KEY`，锁定「可自愈排障」这一行为契约，防未来退化为无消息的裸 401。

---

## 四、测试执行结果

### 4.1 分层执行矩阵

| 层级 | 命令 | 结果 | 耗时 |
| --- | --- | --- | --- |
| 单用例（verbose） | `pytest tests/test_guardrails_and_providers.py::test_zhipu_empty_key_raises_401 -v --no-cov` | **1 passed** | 0.16s |
| 文件级回归 | `pytest tests/test_guardrails_and_providers.py -q --no-cov` | **9 passed**（8 既有 + 1 新增，无回归） | 0.20s |
| **全量回归** | `pytest tests -q --no-cov` | **42 passed, 1 warning** | 502.71s |
| 编译检查 | `py_compile core/api/services/zhipu.py` | 0 错误 | <1s |
| 架构契约 | `PYTHONPATH=scripts/importlinter_boot lint-imports` | 3/3 KEPT | — |

> warning 为既有的 starlette TestClient 弃用提示，与本次修复无关（全量基线中持续存在）。

### 4.2 修复前后行为对照

| 场景 | 修复前 | 修复后 |
| --- | --- | --- |
| 同步请求（空 Key） | 502 / `Illegal header value b'Bearer '` | **401** / `智谱 AI 未配置：请设置 ZHIPU_API_KEY 环境变量`（含 env 名 + 申请指引） |
| 流式请求（空 Key） | 401 / 明确提示（v4 已修复） | 401 / 同上（回归锁定） |
| 正常 Key | 200 正常推理 | 200 正常推理（全量 42/42 佐证无行为回归） |
| 错误保真 | APIError 经 `_format_response` 被重新包装为 502 | `to_dict()` 原样透传 status_code/message/details |

---

## 五、残余观察与改进建议

| 编号 | 观察 | 影响 | 建议 | 优先级 |
| --- | --- | --- | --- | --- |
| OBS-1 | ~~同步路 401 经 `with_retry(max_retries=2)` 仍会重试 2 次（间隔 ~3s）——4xx 配置错误重试必败，纯增延迟~~ | ~~空 Key 场景响应慢 ~3s（仅降级路径与云直连路径）~~ | ✅ **已修复**（2026-09-23）：[handler.py](/Users/yanyu/YYC-Cube/YYC3-0379-World/core/api/errors/handler.py) 新增 `_is_retryable`——YYC3Error/httpx 响应状态码 ∈ [400,500) 且 ≠429 时 `retry` 立即抛出；6 用例回归（含装饰器链路耗时 <0.5s 断言） | ~~P2~~ 已闭环 |
| OBS-2 | `deepseek.py` / `openai.py` 同类云适配器无 `_ensure_key` 等价前置校验 | 同类空 Key 场景可能复现误导性报错 | 复刻 `_ensure_key` 模式至三云适配器（或抽公共 helper） | P2 |
| OBS-3 | 03 文档 v4-T1 行声明「双入口」与实际落地不符（流程性缺口：修复声明未经双入口测试锁定） | 已由本报告测试契约补齐 | 声明性修复须伴随「断言面 = 声明面」的测试（本次已示范） | P3（流程） |

---

## 六、结论

| 维度 | 评价 |
| --- | --- |
| 修复正确性 | ✅ 同步入口 1 行修复，传播链端到端验证（APIError 401 → to_dict 保真 → HTTPException 401） |
| 回归安全性 | ✅ 全量 42/42 通过，无任何既有用例受影响 |
| 测试完备性 | ✅ 双入口断言 + 消息契约断言 + 双重环境隔离 |
| 遗留风险 | 低（OBS-1/2 为性能与同构性改进，非正确性问题） |

**审核结论**：通过。
**下次复验建议**：OBS-2 三云适配器同构化落地时，将本用例扩展为参数化三适配器矩阵。

---

> 「YYC³ 五维驱动」映射：属性维（错误语义正确性）· 事件维（异常传播链）· 关联维（三处 app 包映射机制 + 错误处理器契约）
