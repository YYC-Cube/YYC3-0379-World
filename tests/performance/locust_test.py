import json
import logging
import os
from datetime import datetime

from locust import HttpUser, between, events, task
from locust.runners import MasterRunner


class YYC3APIUser(HttpUser):
    """YYC³ API 用户行为模拟"""

    wait_time = between(1, 3)

    # API 配置
    api_key = os.environ.get("API_KEY", "")
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }

    def on_start(self):
        """用户开始时的操作"""
        logging.info(f"用户开始测试: {self.environment.runner.user_count}")

    @task(10)
    def health_check(self):
        """健康检查（权重: 10）"""
        with self.client.get(
            "/health", headers=self.headers, catch_response=True, name="健康检查"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码错误: {response.status_code}")

    @task(8)
    def ping(self):
        """Ping 测试（权重: 8）"""
        with self.client.get(
            "/v1/ping", headers=self.headers, catch_response=True, name="Ping"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码错误: {response.status_code}")

    @task(6)
    def list_models(self):
        """模型列表（权重: 6）"""
        with self.client.get(
            "/v1/models", headers=self.headers, catch_response=True, name="模型列表"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "data" in data:
                    response.success()
                else:
                    response.failure("响应格式错误")
            else:
                response.failure(f"状态码错误: {response.status_code}")

    @task(4)
    def chat_completion(self):
        """聊天补全（权重: 4）"""
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello, this is a test message from Locust.",
                }
            ],
            "max_tokens": 50,
        }

        with self.client.post(
            "/v1/chat/completions",
            data=json.dumps(payload),
            headers=self.headers,
            catch_response=True,
            name="聊天补全",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "choices" in data:
                    response.success()
                else:
                    response.failure("响应格式错误")
            else:
                response.failure(f"状态码错误: {response.status_code}")

    @task(3)
    def mcp_tools(self):
        """MCP 工具列表（权重: 3）"""
        with self.client.get(
            "/mcp/tools", headers=self.headers, catch_response=True, name="MCP工具列表"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码错误: {response.status_code}")

    @task(2)
    def mcp_execute(self):
        """MCP 工具执行（权重: 2）"""
        payload = {
            "tool": "yyc3_code_review",
            "params": {
                "code": 'print("Hello, World!")',
                "language": "python",
            },
        }

        with self.client.post(
            "/mcp/execute",
            data=json.dumps(payload),
            headers=self.headers,
            catch_response=True,
            name="MCP执行",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码错误: {response.status_code}")

    @task(1)
    def metrics(self):
        """Prometheus 指标（权重: 1）"""
        with self.client.get(
            "/metrics", headers=self.headers, catch_response=True, name="Prometheus指标"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码错误: {response.status_code}")


class YYC3WebSocketUser(HttpUser):
    """YYC³ WebSocket 用户行为模拟"""

    wait_time = between(5, 10)

    @task
    def websocket_test(self):
        """WebSocket 测试"""
        # TODO: 实现 WebSocket 测试
        pass


# 事件监听器
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """测试开始时的操作"""
    logging.info("=" * 60)
    logging.info("YYC³ 性能测试开始")
    logging.info(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时的操作"""
    logging.info("=" * 60)
    logging.info("YYC³ 性能测试结束")
    logging.info(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info("=" * 60)

    # 生成报告
    if isinstance(environment.runner, MasterRunner):
        stats = environment.stats

        logging.info("\n测试统计:")
        logging.info(f"  总请求数: {stats.total.num_requests}")
        logging.info(f"  失败请求: {stats.total.num_failures}")
        logging.info(f"  错误率: {stats.total.fail_ratio * 100:.2f}%")
        logging.info(f"  平均响应时间: {stats.total.avg_response_time:.2f}ms")
        logging.info(
            f"  P95 响应时间: {stats.total.get_response_time_percentile(0.95):.2f}ms"
        )
        logging.info(
            f"  P99 响应时间: {stats.total.get_response_time_percentile(0.99):.2f}ms"
        )
        logging.info(f"  吞吐量: {stats.total.total_rps:.2f} req/s")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """请求事件监听器"""
    if exception:
        logging.error(f"请求失败: {name} - {exception}")
