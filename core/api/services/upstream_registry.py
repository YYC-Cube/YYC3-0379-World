# file: upstream_registry.py
# description: 上游池注册表 - env 驱动的 OpenAI 兼容上游 + 熔断器 + EWMA 统计
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-09-03
# status: active
# tags: [router],[upstream],[circuit-breaker]

"""
@file: app/services/upstream_registry.py
@description: 上游池注册表。解析 OPENAI_COMPATIBLE_UPSTREAMS (JSON) 为运行时上游实例，
             提供模型匹配（fnmatch 通配）、优先级+权重选择、连续失败熔断（OPEN 30s→半开探测）、
             EWMA 延迟/错误率统计。解析失败仅告警降级为空池，绝不 crash。
@author: YanYuCloudCube Team <admin@0379.email>
@license: MIT
@copyright Copyright (c) 2026 YanYuCloudCube Team
"""

import fnmatch
import json
import logging
import os
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

BREAKER_FAILURE_THRESHOLD = 3  # 连续失败 N 次 → 熔断
BREAKER_OPEN_SECONDS = 30.0  # 熔断摘除时长，后半开单请求探测
EWMA_ALPHA = 0.3


@dataclass
class Upstream:
    """单个 OpenAI 兼容上游（vLLM/NIM/SGLang/Ollama-兼容）"""

    name: str
    base_url: str
    models: List[str]
    capability: str = "chat"
    fallback_url: str = ""  # 同一上游的备用地址（如 QSFP 主 / Tailscale 备）
    api_key_env: str = ""  # 从哪个环境变量读 API Key
    weight: float = 100.0
    priority: int = 10  # 数字越小越优先
    capacity: int = 32
    health_path: str = "/health"

    # ── 运行时状态 ──
    consecutive_failures: int = 0
    breaker_state: str = "closed"  # closed / open / half_open
    breaker_opened_at: float = 0.0
    current_load: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    ewma_latency: float = 0.0  # ms
    ewma_error_rate: float = 0.0
    last_error: str = ""
    recent_records: deque = field(default_factory=lambda: deque(maxlen=200))

    def api_key(self) -> str:
        if not self.api_key_env:
            return ""
        return os.getenv(self.api_key_env, "")

    def serves(self, model: str) -> bool:
        return any(fnmatch.fnmatch(model, pat) for pat in self.models)


class UpstreamRegistry:
    """上游池：选择（熔断过滤+加权随机）→ 上报（EWMA+熔断状态机）"""

    def __init__(self):
        self.upstreams: Dict[str, Upstream] = {}
        self.load_from_env()

    # ── 加载 ──────────────────────────────────────────────

    def load_from_env(self) -> None:
        raw = (settings.openai_compatible_upstreams or "[]").strip()
        if not raw or raw == "[]":
            self.upstreams = {}
            return
        try:
            items = json.loads(raw)
            assert isinstance(items, list)
        except Exception as e:
            logger.warning(f"OPENAI_COMPATIBLE_UPSTREAMS 解析失败，降级为空池: {e}")
            self.upstreams = {}
            return
        pool: Dict[str, Upstream] = {}
        for i, item in enumerate(items):
            try:
                u = Upstream(
                    name=str(item["name"]),
                    base_url=str(item["base_url"]).rstrip("/"),
                    models=list(item.get("models", [])),
                    capability=str(item.get("capability", "chat")),
                    fallback_url=str(item.get("fallback_url", "")).rstrip("/"),
                    api_key_env=str(item.get("api_key_env", "")),
                    weight=float(item.get("weight", 100)),
                    priority=int(item.get("priority", 10)),
                    capacity=int(item.get("capacity", 32)),
                    health_path=str(item.get("health_path", "/health")),
                )
                pool[u.name] = u
            except Exception as e:
                logger.warning(f"上游池第 {i} 项配置无效，已跳过: {e}")
        self.upstreams = pool
        if pool:
            logger.info(
                f"上游池已加载 {len(pool)} 个上游: "
                + ", ".join(f"{u.name}({u.base_url})" for u in pool.values())
            )

    # ── 匹配与选择 ────────────────────────────────────────

    def candidates(self, model: str, capability: str = "chat") -> List[Upstream]:
        """按 priority 升序、weight 降序返回能服务该模型的上游"""
        hits = [
            u for u in self.upstreams.values() if u.capability == capability and u.serves(model)
        ]
        hits.sort(key=lambda u: (u.priority, -u.weight))
        return hits

    def available(self, u: Upstream) -> bool:
        """公开接口：该上游当前是否可被降级链选用（closed / half_open 探测）"""
        return self._breaker_available(u)

    def _breaker_available(self, u: Upstream) -> bool:
        """closed 可用；open 超 30s 进入 half_open 放行单次探测"""
        if u.breaker_state == "open":
            if time.time() - u.breaker_opened_at >= BREAKER_OPEN_SECONDS:
                u.breaker_state = "half_open"
                return True
            return False
        return True  # closed / half_open

    def select(self, model: str, capability: str = "chat") -> Optional[Upstream]:
        """优先级分层选择：仅在最优可用层（最小 priority）内加权随机；
        该层全部熔断/不可用才落到下一层。无可用返回 None"""
        avail = [u for u in self.candidates(model, capability) if self._breaker_available(u)]
        if not avail:
            return None
        best_tier = min(u.priority for u in avail)
        avail = [u for u in avail if u.priority == best_tier]
        weights = {}
        for u in avail:
            load_ratio = max(0.01, 1.0 - u.current_load / max(u.capacity, 1))
            penalty = 0.3 if u.breaker_state == "half_open" else 1.0
            latency_norm = min(u.ewma_latency / 500.0, 5.0) if u.ewma_latency else 0.5
            weights[u.name] = max(
                0.001,
                load_ratio
                * (1.0 - u.ewma_error_rate)
                / (latency_norm + 0.1)
                * (u.weight / 100.0)
                * penalty,
            )
        total = sum(weights.values())
        r = random.uniform(0, total)
        cumulative = 0.0
        for u in avail:
            cumulative += weights[u.name]
            if r <= cumulative:
                return u
        return avail[-1]

    def fallback_chain(self, primary: Upstream, capability: str = "chat") -> List[Upstream]:
        """降级链：自身在最前，其后是同 capability 其他上游（按优先级）"""
        chain = [primary]
        same_cap = sorted(
            [u for u in self.upstreams.values() if u.capability == capability],
            key=lambda u: (u.priority, -u.weight),
        )
        for u in same_cap:
            if u.name != primary.name:
                chain.append(u)
        return chain

    # ── 反馈上报 ──────────────────────────────────────────

    def acquire(self, u: Upstream) -> None:
        u.current_load += 1
        u.total_requests += 1

    def release(self, u: Upstream, latency_ms: float, success: bool, error: str = "") -> None:
        u.current_load = max(0, u.current_load - 1)
        u.ewma_latency = EWMA_ALPHA * latency_ms + (1 - EWMA_ALPHA) * u.ewma_latency
        u.ewma_error_rate = (
            EWMA_ALPHA * (0.0 if success else 1.0) + (1 - EWMA_ALPHA) * u.ewma_error_rate
        )
        u.recent_records.append({"t": time.time(), "lat": latency_ms, "ok": success})
        if success:
            u.consecutive_failures = 0
            if u.breaker_state in ("open", "half_open"):
                u.breaker_state = "closed"
                logger.info(f"上游 {u.name} 熔断恢复 closed")
            u.last_error = ""
        else:
            u.consecutive_failures += 1
            u.failed_requests += 1
            u.last_error = error[:300]
            if (
                u.breaker_state == "half_open"
                or u.consecutive_failures >= BREAKER_FAILURE_THRESHOLD
            ):
                u.breaker_state = "open"
                u.breaker_opened_at = time.time()
                logger.warning(
                    f"上游 {u.name} 熔断 OPEN（连续失败 {u.consecutive_failures} 次），"
                    f"{BREAKER_OPEN_SECONDS:.0f}s 后半开探测"
                )

    # ── 观测快照 ──────────────────────────────────────────

    def snapshot(self) -> List[Dict]:
        out = []
        for u in self.upstreams.values():
            out.append(
                {
                    "name": u.name,
                    "base_url": u.base_url,
                    "fallback_url": u.fallback_url,
                    "capability": u.capability,
                    "models": u.models,
                    "priority": u.priority,
                    "weight": u.weight,
                    "status": u.breaker_state,
                    "current_load": u.current_load,
                    "capacity": u.capacity,
                    "ewma_latency_ms": round(u.ewma_latency, 1),
                    "ewma_error_rate": round(u.ewma_error_rate, 4),
                    "total_requests": u.total_requests,
                    "failed_requests": u.failed_requests,
                    "consecutive_failures": u.consecutive_failures,
                    "last_error": u.last_error,
                }
            )
        return out

    def errors(self, limit: int = 50) -> List[Dict]:
        return [
            {
                "upstream": u.name,
                "error": u.last_error,
                "consecutive_failures": u.consecutive_failures,
                "breaker_state": u.breaker_state,
            }
            for u in self.upstreams.values()
            if u.last_error
        ][:limit]


registry = UpstreamRegistry()
