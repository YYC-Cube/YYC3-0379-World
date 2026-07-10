#!/usr/bin/env python3

"""
@file: test-websocket.py
@description: WebSocket功能测试脚本
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-04-08
@updated: 2026-04-08
@status: stable
@license: MIT
"""

import asyncio
import json
import os
import sys

try:
    import websockets
except ImportError:
    print("❌ 缺少依赖: pip install websockets")
    sys.exit(1)


BASE_URL = "wss://api.0379.world"
API_KEY = os.environ.get("API_KEY", "")


class Colors:
    """终端颜色"""

    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"


def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.NC}")


def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.NC}")


def print_info(msg):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.NC}")


def print_test(msg):
    print(f"\n{Colors.YELLOW}━━━ {msg} ━━━{Colors.NC}")


async def test_chat_websocket():
    """测试WebSocket聊天接口"""
    print_test("WebSocket聊天接口测试")

    uri = f"{BASE_URL}/ws/chat?token={API_KEY}"

    try:
        async with websockets.connect(uri) as ws:
            print_success("WebSocket连接建立成功")

            # 发送聊天请求
            request = {
                "model": "llama3.2",
                "messages": [{"role": "user", "content": "你好，请简单介绍一下你自己"}],
                "stream": True,
            }

            print_info(f"发送请求: {json.dumps(request, ensure_ascii=False)}")
            await ws.send(json.dumps(request))

            # 接收流式响应
            print_info("接收流式响应:")
            full_content = ""

            while True:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    data = json.loads(message)

                    event = data.get("event")
                    event_data = data.get("data", {})

                    if event == "start":
                        print(f"  🚀 开始生成 (模型: {event_data.get('model')})")

                    elif event == "chunk":
                        choices = event_data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_content += content
                                print(f"  📝 {content}", end="", flush=True)

                    elif event == "complete":
                        print("\n  ✅ 生成完成")
                        print_info(f"完整响应: {full_content[:100]}...")

                    elif event == "done":
                        print_success("流式输出完成")
                        break

                    elif event == "error":
                        print_error(f"错误: {event_data.get('error')}")
                        return False

                except asyncio.TimeoutError:
                    print_error("接收消息超时")
                    return False

            return True

    except Exception as e:
        print_error(f"WebSocket连接失败: {e}")
        return False


async def test_monitor_websocket():
    """测试WebSocket监控接口"""
    print_test("WebSocket监控接口测试")

    uri = f"{BASE_URL}/ws/monitor?token={API_KEY}"

    try:
        async with websockets.connect(uri) as ws:
            print_success("WebSocket连接建立成功")

            # 接收3次监控数据
            for i in range(3):
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    data = json.loads(message)

                    if data.get("event") == "metrics":
                        metrics = data.get("data", {})
                        print_info(f"监控数据 #{i + 1}:")
                        print(f"  📊 时间: {metrics.get('timestamp')}")
                        print(f"  🔄 活跃请求: {metrics.get('active_requests')}")
                        print(f"  📈 总请求数: {metrics.get('total_requests')}")
                        print(f"  💾 缓存命中率: {metrics.get('cache_hit_rate'):.2%}")

                        models = metrics.get("models", {})
                        for model_name, model_status in models.items():
                            print(
                                f"  🤖 {model_name}: {model_status.get('status')} (延迟: {model_status.get('latency_ms')}ms)"
                            )

                except asyncio.TimeoutError:
                    print_error("接收监控数据超时")
                    return False

            print_success("监控数据接收正常")
            return True

    except Exception as e:
        print_error(f"WebSocket连接失败: {e}")
        return False


async def test_invalid_auth():
    """测试无效认证"""
    print_test("无效认证测试")

    uri = f"{BASE_URL}/ws/chat?token=invalid_key"

    try:
        async with websockets.connect(uri) as ws:
            print_error("应该拒绝无效认证，但连接成功了")
            return False
    except websockets.exceptions.ConnectionClosedError as e:
        if e.rcvd and e.rcvd.code in [4001, 4003]:
            print_success(f"正确拒绝无效认证 (错误码: {e.rcvd.code})")
            return True
        else:
            print_error(f"意外的错误码: {e}")
            return False
    except Exception as e:
        print_error(f"连接异常: {e}")
        return False


async def main():
    """主测试函数"""
    print("=" * 60)
    print("YYC³ Gateway v2.0.0 WebSocket功能测试")
    print("=" * 60)

    tests = [
        ("WebSocket聊天接口", test_chat_websocket),
        ("WebSocket监控接口", test_monitor_websocket),
        ("无效认证测试", test_invalid_auth),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"测试异常: {e}")
            results.append((test_name, False))

    # 打印测试总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = (
            f"{Colors.GREEN}✓ 通过{Colors.NC}"
            if result
            else f"{Colors.RED}✗ 失败{Colors.NC}"
        )
        print(f"{test_name}: {status}")

    print(f"\n总测试数: {total}")
    print(f"通过: {Colors.GREEN}{passed}{Colors.NC}")
    print(f"失败: {Colors.RED}{total - passed}{Colors.NC}")

    if passed == total:
        print(f"\n{Colors.GREEN}✓ 所有测试通过！{Colors.NC}")
        sys.exit(0)
    else:
        print(f"\n{Colors.RED}✗ 部分测试失败{Colors.NC}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}测试被用户中断{Colors.NC}")
        sys.exit(1)
