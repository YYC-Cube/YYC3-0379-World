# file: metrics.py
# description: 性能指标工具模块
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-03-21
# updated: 2026-04-04
# status: active
# tags: [util],[metrics],[monitoring]

"""
@file: app/utils/metrics.py
@description: 监控指标管理器，提供 Prometheus 监控指标
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-03-19
@updated: 2026-03-19
@status: stable
@license: MIT
@copyright: Copyright (c) 2026 YanYuCloudCube Team
@tags: utils,python,metrics,public
"""

import logging
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram


class MetricsManager:
    """监控指标管理器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self.request_counter = Counter(
            "api_requests_total",
            "Total API requests",
            ["method", "endpoint", "status", "backend"],
        )

        self.response_time = Histogram(
            "api_response_time_seconds",
            "API response time",
            ["method", "endpoint", "backend"],
        )

        self.error_counter = Counter(
            "api_errors_total",
            "Total API errors",
            ["error_type", "endpoint", "backend"],
        )

        self.cache_hits = Counter("cache_hits_total", "Total cache hits", ["backend"])

        self.cache_misses = Counter("cache_misses_total", "Total cache misses", ["backend"])

        self.active_requests = Gauge("api_active_requests", "Active API requests")

        self.model_usage = Counter(
            "model_usage_total", "Total model usage", ["model", "backend_type"]
        )

        self.token_usage = Counter(
            "token_usage_total",
            "Total token usage",
            ["model", "backend_type", "token_type"],
        )

        self.backend_latency = Histogram(
            "backend_latency_seconds",
            "Backend response time",
            ["backend_type", "model"],
        )

        self.rate_limit_rejections = Counter(
            "rate_limit_rejections_total",
            "Total rate limit rejections",
            ["client_type"],
        )

        self.concurrency_limit_rejections = Counter(
            "concurrency_limit_rejections_total", "Total concurrency limit rejections"
        )

        # ── 03 §9 指标先行 P0 三件套（2026-10-05：Shadow/Canary/自动回滚的数据底座）──
        self.backend_requests = Counter(
            "yyc3_backend_requests_total",
            "Backend upstream requests by upstream and outcome",
            ["upstream", "code"],
        )
        self.backend_ttft = Histogram(
            "yyc3_backend_ttft_seconds",
            "SSE time-to-first-chunk per upstream",
            ["upstream"],
            buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0),
        )
        self.registry_rollbacks = Counter(
            "yyc3_registry_rollback_total",
            "Registry rollback executions",
            ["model_id", "target_version"],
        )
        self.canary_weight = Gauge(
            "yyc3_canary_weight",
            "Current canary weight per alias (03 §5)",
            ["alias"],
        )
        self.shadow_requests = Counter(
            "yyc3_shadow_requests_total",
            "Shadow sampled requests by shadow model and outcome (03 §4)",
            ["shadow", "code"],
        )
        self.canary_failures = Counter(
            "yyc3_canary_failures_total",
            "Canary request failure signals (auto-rollback basis)",
            ["alias"],
        )

        self.logger.info("Metrics manager initialized")

    def record_request(
        self, method: str, endpoint: str, status: int, backend: Optional[str] = None
    ):
        """记录请求"""
        self.request_counter.labels(
            method=method,
            endpoint=endpoint,
            status=status,
            backend=backend or "unknown",
        ).inc()

    def record_response_time(
        self, method: str, endpoint: str, duration: float, backend: Optional[str] = None
    ):
        """记录响应时间"""
        self.response_time.labels(
            method=method, endpoint=endpoint, backend=backend or "unknown"
        ).observe(duration)

    def record_error(self, error_type: str, endpoint: str, backend: Optional[str] = None):
        """记录错误"""
        self.error_counter.labels(
            error_type=error_type, endpoint=endpoint, backend=backend or "unknown"
        ).inc()

    def record_cache_hit(self, backend: str):
        """记录缓存命中"""
        self.cache_hits.labels(backend=backend).inc()

    def record_cache_miss(self, backend: str):
        """记录缓存未命中"""
        self.cache_misses.labels(backend=backend).inc()

    def increment_active_requests(self):
        """增加活跃请求数"""
        self.active_requests.inc()

    def decrement_active_requests(self):
        """减少活跃请求数"""
        self.active_requests.dec()

    def record_model_usage(self, model: str, backend_type: str):
        """记录模型使用"""
        self.model_usage.labels(model=model, backend_type=backend_type).inc()

    def record_token_usage(self, model: str, backend_type: str, token_type: str, count: int):
        """记录 Token 使用"""
        self.token_usage.labels(model=model, backend_type=backend_type, token_type=token_type).inc(
            count
        )

    def record_backend_latency(self, backend_type: str, model: str, duration: float):
        """记录后端延迟"""
        self.backend_latency.labels(backend_type=backend_type, model=model).observe(duration)

    def record_backend_request(self, upstream: str, code: str = "200"):
        """记录上游后端请求结果（03 §9：Canary error_rate / 回滚硬条件数据源）"""
        self.backend_requests.labels(upstream=upstream, code=code).inc()

    def observe_ttft(self, upstream: str, seconds: float):
        """记录流式首字节延迟（03 §9：ttft 硬条件 >3s 数据源）"""
        self.backend_ttft.labels(upstream=upstream).observe(seconds)

    def record_rollback(self, model_id: str, target_version: str):
        """记录回滚执行（03 §9：P0 告警数据源）"""
        self.registry_rollbacks.labels(model_id=model_id, target_version=target_version).inc()

    def set_canary_weight(self, alias: str, weight: int):
        """维护当前灰度权重（03 §9 P1 指标 yyc3_canary_weight）"""
        self.canary_weight.labels(alias=alias).set(weight)

    def record_shadow_request(self, shadow: str, code: str):
        """记录 Shadow 采样结果（03 §4 最小采样）"""
        self.shadow_requests.labels(shadow=shadow, code=code).inc()

    def record_canary_failure(self, alias: str):
        """记录 canary 失败信号（自动回退依据）"""
        self.canary_failures.labels(alias=alias).inc()

    def record_rate_limit_rejection(self, client_type: str):
        """记录限流拒绝"""
        self.rate_limit_rejections.labels(client_type=client_type).inc()

    def record_concurrency_limit_rejection(self):
        """记录并发限制拒绝"""
        self.concurrency_limit_rejections.inc()

    def get_active_requests(self) -> float:
        """获取当前活跃请求数"""
        return self.active_requests._value.get()

    def _get_counter_value(self, counter) -> float:
        """安全获取 Counter 值，兼容不同 prometheus_client 版本"""
        try:
            return counter._value.get()
        except AttributeError:
            pass
        try:
            samples = counter.collect()
            if samples and samples[0].samples:
                return float(samples[0].samples[0].value)
        except Exception:
            pass
        return 0.0

    def get_total_requests(self) -> float:
        """获取总请求数"""
        return self._get_counter_value(self.request_counter)

    def get_cache_hit_rate(self) -> float:
        """获取缓存命中率"""
        hits = self._get_counter_value(self.cache_hits)
        misses = self._get_counter_value(self.cache_misses)
        total = hits + misses
        return hits / total if total > 0 else 0.0


metrics_manager = MetricsManager()
