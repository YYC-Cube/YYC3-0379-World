# file: model_register_agent.py
# description: 模型服务侧注册 Agent - 就绪探测/注册/置ready/心跳循环/优雅下线（规范 01 附录 A P2 落地）
# author: YanYuCloudCube Team <admin@0379.email>
# version: v1.0.0
# created: 2026-09-28
# status: active
# tags: [registry],[agent],[heartbeat],[onboarding]
# spec: docs/模型接入与注册/01-接入现状规范-v2.3.md 附录 A / 02-Registry目标架构.md §4.4

"""
@file: core/scripts/model_register_agent.py
@description: Registry 注册 Agent（部署在算力节点侧，随 vLLM 服务拉起）。
    生命周期（规范 02 §5.3 注册 Agent 工作流）：
      ① 轮询本地服务 /health 直到 200（权重加载完成）
      ② POST {gateway}/registry/v1/models 注册（元数据源：model-meta.json + CLI 覆盖）
      ③ PATCH state=ready（开始承接流量）
      ④ 每 30s 心跳上报（runtime 指标从服务 /health 尽力而为抽取）
      ⑤ SIGTERM/SIGINT → 尽力而为 PATCH state=offline 后退出（TTL 兜底：停跳 300s 自动摘除）
    零第三方依赖（stdlib urllib）——DGX/NAS/裸机 python3 直跑。
    用法：
      python3 model_register_agent.py --gateway http://yyc3-45:8000 \\
          --meta model-meta.json --admin-key-env ADMIN_API_KEYS
    认证：网关管理面密钥从环境变量（--admin-key-env 指定名，缺省 ADMIN_API_KEYS）读取。
@author: YanYuCloudCube Team <admin@0379.email>
@license: MIT
@copyright Copyright (c) 2026 YanYuCloudCube Team
"""

import argparse
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from typing import Callable, Optional

DEFAULT_INTERVAL = 30  # 心跳周期（秒，规范 02 §4.4 同值）
READY_TIMEOUT = 3600  # 就绪等待上限（秒）——TB 级权重冷加载余量


def build_register_payload(meta: dict, overrides: Optional[dict] = None) -> dict:
    """model-meta.json → /registry/v1/models 请求体（字段白名单 + 必填校验）。

    :raises ValueError: model_id 缺失
    """
    payload = dict(meta)
    if overrides:
        payload.update({k: v for k, v in overrides.items() if v is not None})
    model_id = str(payload.get("model_id") or "").strip()
    if not model_id:
        raise ValueError("model-meta.json 缺失必填字段 model_id")
    payload["model_id"] = model_id
    # backend 同义归一（规范 04 元数据 schema 的 backend ↔ 主表 backend_type）
    if "backend" in payload and "backend_type" not in payload:
        payload["backend_type"] = payload["backend"]
    return payload


def service_health_url(base_url: str) -> str:
    """base_url → 健康探测地址（去尾 /v1，附 /health）。"""
    return base_url.rstrip("/").removesuffix("/v1").rstrip("/") + "/health"


def _http_json(
    method: str, url: str, admin_key: str, body: Optional[dict] = None, timeout: float = 10.0
) -> tuple:
    """极简 HTTP JSON 调用（stdlib）：返回 (status_code, parsed_json_or_none)。"""
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if admin_key:
        req.add_header("X-API-Key", admin_key)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, None
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, None


def extract_runtime_metrics(health_body: Optional[dict]) -> dict:
    """服务 /health 响应 → 心跳 runtime 指标（尽力而为字段抽取，缺失即略）。"""
    if not isinstance(health_body, dict):
        return {}
    metrics = {}
    for src, dst in (
        ("gpu_utilization", "gpu_utilization"),
        ("active_requests", "active_requests"),
        ("uptime_seconds", "uptime_seconds"),
    ):
        if isinstance(health_body.get(src), (int, float)):
            metrics[dst] = health_body[src]
    return metrics


class RegisterAgent:
    """注册 Agent 状态机：wait_ready → register → ready → heartbeat*（信号退出 → offline）。"""

    def __init__(
        self,
        gateway: str,
        payload: dict,
        admin_key: str,
        interval: int = DEFAULT_INTERVAL,
        http: Optional[Callable] = None,
        sleep: Optional[Callable] = None,
    ):
        self.gateway = gateway.rstrip("/")
        self.payload = payload
        self.admin_key = admin_key
        self.interval = interval
        self._http = http or _http_json  # 测试桩替点
        self._sleep = sleep or time.sleep
        self._stopped = False

    def stop(self, *_args) -> None:
        self._stopped = True

    # ── 生命周期步骤（独立方法便于单测） ──────────────────────

    def wait_service_ready(self, timeout: float = READY_TIMEOUT) -> bool:
        """① 轮询服务 /health 至 200。"""
        url = service_health_url(self.payload["base_url"])
        deadline = time.time() + timeout
        while not self._stopped and time.time() < deadline:
            status, _ = self._http("GET", url, "", timeout=5)
            if status == 200:
                return True
            self._sleep(self.interval)
        return False

    def register(self) -> bool:
        """② 注册（幂等：重复 = 覆盖）。"""
        status, body = self._http(
            "POST", f"{self.gateway}/registry/v1/models", self.admin_key, self.payload
        )
        if status not in (200, 201):
            print(f"❌ 注册失败 HTTP {status}: {body}", file=sys.stderr)
            return False
        print(f"✅ 已注册 {self.payload['model_id']} → {self.gateway}")
        return True

    def set_state(self, state: str) -> bool:
        """③/⑤ 状态切换（ready / offline）。"""
        status, _ = self._http(
            "PATCH",
            f"{self.gateway}/registry/v1/models/{self.payload['model_id']}",
            self.admin_key,
            {"state": state},
        )
        return status == 200

    def heartbeat_once(self) -> bool:
        """④ 单次心跳（runtime 指标尽力而为从服务 /health 抽取）。"""
        _, health = self._http("GET", service_health_url(self.payload["base_url"]), "", timeout=5)
        body = {"status": "healthy", **extract_runtime_metrics(health)}
        status, _ = self._http(
            "POST",
            f"{self.gateway}/registry/v1/models/{self.payload['model_id']}/heartbeat",
            self.admin_key,
            body,
        )
        return status == 200

    def run(self) -> int:
        """主循环：就绪 → 注册 → ready → 心跳（信号/异常退出前尽力 offline）。"""
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        if not self.wait_service_ready():
            print("❌ 服务就绪等待超时/中断", file=sys.stderr)
            return 2
        if not self.register():
            return 3
        if not self.set_state("ready"):
            print("⚠️ state=ready 设置失败（继续心跳）", file=sys.stderr)
        while not self._stopped:
            if not self.heartbeat_once():
                print(
                    "⚠️ 心跳失败（网关不可达？下轮重试；停跳 300s Registry 自动摘除）",
                    file=sys.stderr,
                )
            self._sleep(self.interval)
        self.set_state("offline")  # 优雅下线（尽力而为；失败由 TTL 兜底）
        print("👋 已下线退出")
        return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="YYC³ Registry 注册 Agent（模型服务侧）")
    parser.add_argument("--gateway", required=True, help="网关基址，如 http://yyc3-45:8000")
    parser.add_argument("--meta", required=True, help="model-meta.json 路径")
    parser.add_argument(
        "--admin-key-env",
        default="ADMIN_API_KEYS",
        help="管理面密钥环境变量名（缺省 ADMIN_API_KEYS）",
    )
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="心跳周期秒")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="元数据覆盖项（可多次；数字/bool/JSON 自动转换）",
    )
    args = parser.parse_args(argv)

    try:
        meta = json.loads(open(args.meta, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"❌ model-meta.json 读取失败: {exc}", file=sys.stderr)
        return 2
    overrides = {}
    for item in args.set:
        key, _, value = item.partition("=")
        try:
            overrides[key] = json.loads(value)
        except json.JSONDecodeError:
            overrides[key] = value
    try:
        payload = build_register_payload(meta, overrides)
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2
    admin_key = os.getenv(args.admin_key_env, "")
    if not admin_key:
        print(f"❌ 环境变量 {args.admin_key_env} 未配置", file=sys.stderr)
        return 2
    return RegisterAgent(args.gateway, payload, admin_key, interval=args.interval).run()


if __name__ == "__main__":
    sys.exit(main())
