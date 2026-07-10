#!/usr/bin/env python3
"""验证所有模块导入"""
import sys

modules = [
    "app.config", "app.cache", "app.models", "app.db",
    "app.errors.exceptions", "app.errors.handler", "app.errors",
    "app.utils.logger", "app.utils.metrics", "app.utils.cache",
    "app.utils.concurrency", "app.utils.crypto", "app.utils.filter",
    "app.utils.http_client", "app.utils",
    "app.middleware.rate_limit", "app.middleware.auth",
    "app.middleware.versioning", "app.middleware",
    "app.services.zhipu", "app.services.ollama", "app.services.openai",
    "app.services.deepseek", "app.services.embedding",
    "app.services.model_router", "app.services.failover_manager",
    "app.services.mcp_integration", "app.services.mcp_client",
    "app.services.rag_service", "app.services.document_processor",
    "app.services",
    "app.api.schemas", "app.api.chat", "app.api.knowledge_base",
    "app.api.documents", "app.api.rag", "app.api.mcp",
    "app.api.websocket", "app.api",
]

errors = []
for mod in modules:
    try:
        __import__(mod)
        print(f"  OK   {mod}")
    except Exception as e:
        errors.append((mod, str(e)))
        print(f"  FAIL {mod}: {e}")

total = len(modules)
ok = total - len(errors)
print(f"\n{'='*50}")
print(f"Total: {total} | OK: {ok} | FAIL: {len(errors)}")
if errors:
    print("\nFailed modules:")
    for mod, err in errors:
        print(f"  {mod}: {err}")
    sys.exit(1)
else:
    print("\nAll modules imported successfully!")
