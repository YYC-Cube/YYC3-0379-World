#!/usr/bin/env python3
"""
@file test_gateway_api.py
@description YYC³ Gateway API 核心测试用例 - 为前端集成验证铺路
@author YanYuCloudCube Team <admin@0379.email>
@version 1.0.0
@date 2026-04-08
@tags [test,gateway,api,五维九曲]
"""

import requests
import json
import sys
from datetime import datetime

GATEWAY_BASE = "https://api.0379.world"
TIMEOUT = 30

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def log_test(name: str, passed: bool, detail: str = ""):
    status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if passed else f"{Colors.RED}❌ FAIL{Colors.RESET}"
    print(f"  {status} {name}")
    if detail:
        print(f"         {Colors.BLUE}{detail}{Colors.RESET}")

def test_health():
    """测试 Gateway 健康检查"""
    print(f"\n{Colors.YELLOW}=== 1. Health Check ==={Colors.RESET}")
    try:
        resp = requests.get(f"{GATEWAY_BASE}/health", timeout=TIMEOUT, verify=True)
        passed = resp.status_code == 200 and resp.json().get("status") == "healthy"
        log_test("GET /health", passed, f"status={resp.status_code}")
        return passed
    except Exception as e:
        log_test("GET /health", False, str(e))
        return False

def test_root():
    """测试根路径"""
    print(f"\n{Colors.YELLOW}=== 2. Root Endpoint ==={Colors.RESET}")
    try:
        resp = requests.get(f"{GATEWAY_BASE}/", timeout=TIMEOUT)
        data = resp.json()
        passed = "message" in data and "version" in data
        log_test("GET /", passed, f"version={data.get('version', 'N/A')}")
        return passed
    except Exception as e:
        log_test("GET /", False, str(e))
        return False

def test_models():
    """测试模型列表"""
    print(f"\n{Colors.YELLOW}=== 3. Models List ==={Colors.RESET}")
    try:
        resp = requests.get(f"{GATEWAY_BASE}/v1/models", timeout=TIMEOUT)
        data = resp.json()
        models = data.get("data", [])
        passed = resp.status_code == 200 and len(models) > 0
        
        free_models = [m for m in models if m.get("pricing_type") == "free"]
        ollama_models = [m for m in models if m.get("provider") == "ollama"]
        
        log_test("GET /v1/models", passed, f"total={len(models)}, free={len(free_models)}, ollama={len(ollama_models)}")
        
        if passed:
            print(f"\n  {Colors.BLUE}可用模型:{Colors.RESET}")
            for m in models[:5]:
                pricing = "🆓" if m.get("pricing_type") == "free" else "💰"
                print(f"    {pricing} {m['id']:20s} [{m['provider']:8s}] {m.get('name', 'N/A')}")
            if len(models) > 5:
                print(f"    ... 还有 {len(models)-5} 个模型")
        
        return passed
    except Exception as e:
        log_test("GET /v1/models", False, str(e))
        return False

def test_chat_completion():
    """测试聊天补全 (使用免费模型)"""
    print(f"\n{Colors.YELLOW}=== 4. Chat Completion (Free Model) ==={Colors.RESET}")
    
    test_cases = [
        ("glm-4-flash", "智谱 GLM-4 Flash"),
        ("llama3.2", "Ollama Llama3.2 (本地)"),
    ]
    
    results = []
    for model_id, model_name in test_cases:
        try:
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": "请用一句话介绍 YYC³ 项目"}],
                "max_tokens": 100,
                "temperature": 0.7
            }
            
            start_time = datetime.now()
            resp = requests.post(
                f"{GATEWAY_BASE}/v1/chat/completions",
                json=payload,
                timeout=TIMEOUT
            )
            elapsed = (datetime.now() - start_time).total_seconds()
            
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                passed = len(content) > 0
                log_test(f"POST /v1/chat/completions ({model_name})", passed, 
                        f"time={elapsed:.2f}s, tokens={len(content)}")
                if passed:
                    print(f"         响应: {content[:80]}...")
            else:
                log_test(f"POST /v1/chat/completions ({model_name})", False, 
                        f"status={resp.status_code}")
                passed = False
            
            results.append(passed)
        except Exception as e:
            log_test(f"POST /v1/chat/completions ({model_name})", False, str(e)[:50])
            results.append(False)
    
    return any(results)

def test_mcp_tools():
    """测试 MCP 工具列表"""
    print(f"\n{Colors.YELLOW}=== 5. MCP Tools ==={Colors.RESET}")
    try:
        resp = requests.get(f"{GATEWAY_BASE}/v1/mcp/tools", timeout=TIMEOUT)
        
        if resp.status_code == 200:
            data = resp.json()
            tools = data.get("tools", [])
            passed = len(tools) > 0
            log_test("GET /v1/mcp/tools", passed, f"tools_count={len(tools)}")
            
            if passed:
                print(f"\n  {Colors.BLUE}可用工具:{Colors.RESET}")
                for t in tools[:5]:
                    print(f"    🔧 {t.get('name', 'unknown'):20s} - {t.get('description', 'N/A')[:40]}")
        else:
            log_test("GET /v1/mcp/tools", False, f"status={resp.status_code}")
            passed = False
        
        return passed
    except Exception as e:
        log_test("GET /v1/mcp/tools", False, str(e))
        return False

def main():
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}  YYC³ Gateway API 核心测试{Colors.RESET}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  目标: {GATEWAY_BASE}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
    
    results = {
        "Health Check": test_health(),
        "Root Endpoint": test_root(),
        "Models List": test_models(),
        "Chat Completion": test_chat_completion(),
        "MCP Tools": test_mcp_tools(),
    }
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}  测试结果汇总{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = f"{Colors.GREEN}✅{Colors.RESET}" if result else f"{Colors.RED}❌{Colors.RESET}"
        print(f"  {status} {name}")
    
    score = int((passed / total) * 100)
    grade = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D"
    
    print(f"\n  {Colors.YELLOW}通过率: {passed}/{total} ({score}%) - 等级: {grade}{Colors.RESET}")
    
    if score >= 80:
        print(f"\n  {Colors.GREEN}🎉 API 就绪，可以开始前端集成！{Colors.RESET}")
    else:
        print(f"\n  {Colors.RED}⚠️ API 存在问题，需要修复后再进行前端集成{Colors.RESET}")
    
    return 0 if score >= 80 else 1

if __name__ == "__main__":
    sys.exit(main())
