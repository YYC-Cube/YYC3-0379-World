# file: rate_limit.py
# description: API 限流中间件模块
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-03-21
# updated: 2026-04-04
# status: active
# tags: [middleware],[rate-limit],[security]

"""
@file: app/middleware/rate_limit.py
@description: 限流中间件，提供基于 IP 和用户的限流功能
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-03-19
@updated: 2026-03-19
@status: stable
@license: MIT
@copyright: Copyright (c) 2026 YanYuCloudCube Team
@tags: middleware,python,rate_limit,public
"""

import logging
import time
from collections import defaultdict
from functools import wraps
from typing import Callable, Dict, Optional

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiter:
    """限流器"""

    def __init__(self, max_requests: int = 100, time_window: int = 60, burst: int = 10):
        self.max_requests = max_requests
        self.time_window = time_window
        self.burst = burst

        self.requests: Dict[str, list] = defaultdict(list)
        self.logger = logging.getLogger(__name__)

    def is_allowed(self, key: str) -> tuple[bool, Dict[str, int]]:
        """检查是否允许请求"""
        now = time.time()
        window_start = now - self.time_window

        requests = self.requests[key]

        requests[:] = [t for t in requests if t > window_start]

        if len(requests) >= self.max_requests:
            return False, {
                "limit": self.max_requests,
                "remaining": 0,
                "reset": int(requests[0] + self.time_window),
            }

        requests.append(now)

        return True, {
            "limit": self.max_requests,
            "remaining": self.max_requests - len(requests),
            "reset": int(now + self.time_window),
        }

    def cleanup(self):
        """清理过期记录"""
        now = time.time()
        window_start = now - self.time_window

        for key in list(self.requests.keys()):
            self.requests[key][:] = [t for t in self.requests[key] if t > window_start]

            if not self.requests[key]:
                del self.requests[key]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件"""

    def __init__(
        self,
        app=None,
        ip_limiter: Optional[RateLimiter] = None,
        user_limiter: Optional[RateLimiter] = None,
    ):
        super().__init__(app)
        self.ip_limiter = ip_limiter or RateLimiter(max_requests=500, time_window=60)
        self.user_limiter = user_limiter or RateLimiter(
            max_requests=1000, time_window=60
        )
        self.logger = logging.getLogger(__name__)

    async def dispatch(self, request: Request, call_next):
        """中间件处理"""
        client_ip = self._get_client_ip(request)
        user_id = request.headers.get("X-User-ID")

        allowed, ip_info = self.ip_limiter.is_allowed(client_ip)

        if not allowed:
            self.logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests from this IP",
                    "retry_after": ip_info["reset"] - int(time.time()),
                },
            )

        if user_id:
            allowed, user_info = self.user_limiter.is_allowed(user_id)

            if not allowed:
                self.logger.warning(f"Rate limit exceeded for user: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests for this user",
                        "retry_after": user_info["reset"] - int(time.time()),
                    },
                )

        response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(ip_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(ip_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(ip_info["reset"])

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端 IP"""
        forwarded = request.headers.get("X-Forwarded-For")

        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")

        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


rate_limit_middleware = RateLimitMiddleware()


def rate_limit(max_requests: int = 100, time_window: int = 60):
    """限流装饰器"""
    limiter = RateLimiter(max_requests=max_requests, time_window=time_window)

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = None

            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                return await func(*args, **kwargs)

            client_ip = rate_limit_middleware._get_client_ip(request)

            allowed, info = limiter.is_allowed(client_ip)

            if not allowed:
                logging.getLogger(__name__).warning(
                    f"Rate limit exceeded for IP: {client_ip} "
                    f"in function: {func.__name__}"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests",
                        "retry_after": info["reset"] - int(time.time()),
                    },
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
