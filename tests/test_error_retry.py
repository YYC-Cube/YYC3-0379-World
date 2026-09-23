# file: test_error_retry.py
# description: ErrorHandler 重试语义验证——4xx 确定性失败跳过重试（OBS-1）
# author: YanYuCloudCube Team
# created: 2026-09-23
# status: active
# tags: [test],[error-handling],[retry]

"""
@file: test_error_retry.py
@description: 验证 with_retry/error_handler.retry 对确定性 4xx 失败立即抛出（不空转），
  429 限流与 5xx 维持重试语义，未知异常保持原行为。
@author: YanYuCloudCube Team <admin@0379.email>
"""

import time

import httpx
import pytest

from app.errors.exceptions import APIError
from app.errors.handler import error_handler, with_retry


def _counting_failer(times: int, exc_factory):
    """返回 (func, calls)：每次调用抛 exc_factory()，记录实际调用次数"""
    calls = {"n": 0}

    async def func():
        calls["n"] += 1
        if calls["n"] <= times:
            raise exc_factory()
        return "ok"

    return func, calls


@pytest.mark.anyio
async def test_retry_skips_on_yyc3_401():
    """YYC3Error(401) 确定性失败：不重试，立即抛出（OBS-1 核心场景）"""
    func, calls = _counting_failer(3, lambda: APIError(message="智谱 AI 未配置", status_code=401))
    with pytest.raises(APIError) as ei:
        await error_handler.retry(func, max_retries=2, delay=0.01)
    assert ei.value.status_code == 401
    assert calls["n"] == 1  # 零空转


@pytest.mark.anyio
async def test_retry_skips_on_httpx_4xx():
    """httpx.HTTPStatusError(4xx)：上游已判决，不重试"""
    def make():
        req = httpx.Request("POST", "https://upstream.test/v1/chat")
        resp = httpx.Response(403, request=req)
        return httpx.HTTPStatusError("Forbidden", request=req, response=resp)

    func, calls = _counting_failer(3, make)
    with pytest.raises(httpx.HTTPStatusError):
        await error_handler.retry(func, max_retries=2, delay=0.01)
    assert calls["n"] == 1


@pytest.mark.anyio
async def test_retry_kept_on_429():
    """429 限流：保留重试语义（退避后可恢复）"""
    func, calls = _counting_failer(2, lambda: APIError(message="限流", status_code=429))
    result = await error_handler.retry(func, max_retries=3, delay=0.01)
    assert result == "ok"
    assert calls["n"] == 3  # 2 次失败 + 1 次成功


@pytest.mark.anyio
async def test_retry_kept_on_5xx():
    """5xx 服务端错误：维持重试语义（原行为）"""
    func, calls = _counting_failer(
        2, lambda: APIError(message="上游故障", status_code=502)
    )
    result = await error_handler.retry(func, max_retries=2, delay=0.01)
    assert result == "ok"
    assert calls["n"] == 3


@pytest.mark.anyio
async def test_retry_kept_on_unknown_exception():
    """未知异常（无 status_code）：维持原重试行为"""
    func, calls = _counting_failer(1, lambda: RuntimeError("boom"))
    result = await error_handler.retry(func, max_retries=2, delay=0.01)
    assert result == "ok"
    assert calls["n"] == 2


@pytest.mark.anyio
async def test_with_retry_decorator_401_no_delay():
    """with_retry 装饰器链路：401 立即抛出，总耗时远小于 2 次重试延迟之和"""
    async def failing():
        raise APIError(message="未配置", status_code=401)

    wrapped = with_retry(max_retries=2, delay=1.5)(failing)
    start = time.monotonic()
    with pytest.raises(APIError):
        await wrapped()
    elapsed = time.monotonic() - start
    assert elapsed < 0.5  # 若空转重试 2 次 ×1.5s delay 应 ≥3s
