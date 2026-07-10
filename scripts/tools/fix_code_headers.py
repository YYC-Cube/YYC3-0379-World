#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
file: fix-code-headers.py
description: YYC³ 代码文件标头修复脚本 - 自动为所有代码文件添加符合规范的 JSDoc 标头注释
author: YanYuCloudCube Team
version: v1.0.0
created: 2026-04-04
updated: 2026-04-04
status: active
tags: [script],[code],[fix]
"""

import os
import re
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path("/Volumes/Development/项目提示词/0379-world")

# 文件信息映射
FILE_INFO = {
    "core/api/main.py": {
        "description": "FastAPI 应用入口文件",
        "tags": ["api", "main", "entry"]
    },
    "core/api/config.py": {
        "description": "应用配置管理模块",
        "tags": ["config", "settings", "management"]
    },
    "core/api/db.py": {
        "description": "数据库连接和操作模块",
        "tags": ["database", "postgresql", "connection"]
    },
    "core/api/models.py": {
        "description": "数据模型定义模块",
        "tags": ["models", "schema", "data"]
    },
    "core/api/cache.py": {
        "description": "缓存管理模块",
        "tags": ["cache", "redis", "performance"]
    },
    "core/api/api/chat.py": {
        "description": "聊天 API 路由模块",
        "tags": ["api", "chat", "route"]
    },
    "core/api/api/schemas.py": {
        "description": "API 数据模式定义模块",
        "tags": ["api", "schema", "validation"]
    },
    "core/api/services/mcp_client.py": {
        "description": "MCP 客户端服务模块",
        "tags": ["service", "mcp", "client"]
    },
    "core/api/services/mcp_integration.py": {
        "description": "MCP 集成服务模块",
        "tags": ["service", "mcp", "integration"]
    },
    "core/api/services/ollama.py": {
        "description": "Ollama 模型服务模块",
        "tags": ["service", "ollama", "ai"]
    },
    "core/api/services/openai.py": {
        "description": "OpenAI API 服务模块",
        "tags": ["service", "openai", "ai"]
    },
    "core/api/services/zhipu.py": {
        "description": "智谱 AI 服务模块",
        "tags": ["service", "zhipu", "ai"]
    },
    "core/api/errors/exceptions.py": {
        "description": "自定义异常类模块",
        "tags": ["error", "exception", "handling"]
    },
    "core/api/errors/handler.py": {
        "description": "错误处理器模块",
        "tags": ["error", "handler", "middleware"]
    },
    "core/api/middleware/rate_limit.py": {
        "description": "API 限流中间件模块",
        "tags": ["middleware", "rate-limit", "security"]
    },
    "core/api/utils/cache.py": {
        "description": "缓存工具函数模块",
        "tags": ["util", "cache", "helper"]
    },
    "core/api/utils/concurrency.py": {
        "description": "并发处理工具模块",
        "tags": ["util", "concurrency", "async"]
    },
    "core/api/utils/crypto.py": {
        "description": "加密工具函数模块",
        "tags": ["util", "crypto", "security"]
    },
    "core/api/utils/filter.py": {
        "description": "数据过滤工具模块",
        "tags": ["util", "filter", "validation"]
    },
    "core/api/utils/http_client.py": {
        "description": "HTTP 客户端工具模块",
        "tags": ["util", "http", "client"]
    },
    "core/api/utils/logger.py": {
        "description": "日志记录工具模块",
        "tags": ["util", "logger", "monitoring"]
    },
    "core/api/utils/metrics.py": {
        "description": "性能指标工具模块",
        "tags": ["util", "metrics", "monitoring"]
    },
}

def create_jsdoc_header(file_path: Path, file_info: Dict) -> str:
    """创建 JSDoc 标头注释"""
    tags_str = ",".join([f"[{tag}]" for tag in file_info["tags"]])
    
    return f'''/**
 * file: {file_path.name}
 * description: {file_info['description']}
 * author: YanYuCloudCube Team
 * version: v1.0.0
 * created: 2026-03-21
 * updated: 2026-04-04
 * status: active
 * tags: {tags_str}
 */

'''

def fix_code_file(file_path: Path, file_info: Dict) -> tuple:
    """修复代码文件"""
    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否已有 JSDoc 标头
        if content.strip().startswith("/**"):
            return False, "已有 JSDoc 标头"
        
        # 创建新的 JSDoc 标头
        jsdoc_header = create_jsdoc_header(file_path, file_info)
        
        # 合并新标头和内容
        new_content = jsdoc_header + content
        
        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return True, "修复成功"
    
    except Exception as e:
        return False, f"修复失败: {str(e)}"

def main():
    """主函数"""
    print("=" * 50)
    print("YYC³ 代码文件标头修复")
    print("=" * 50)
    print()
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for rel_path, file_info in FILE_INFO.items():
        file_path = PROJECT_ROOT / rel_path
        
        if not file_path.exists():
            print(f"⚠️  文件不存在: {rel_path}")
            error_count += 1
            continue
        
        print(f"修复: {rel_path}")
        
        success, message = fix_code_file(file_path, file_info)
        
        if success:
            print(f"  ✅ {message}")
            success_count += 1
        else:
            print(f"  ⏭️  {message}")
            skip_count += 1
    
    print()
    print("=" * 50)
    print("✅ 修复完成")
    print("=" * 50)
    print()
    print(f"成功修复: {success_count}")
    print(f"跳过: {skip_count}")
    print(f"错误: {error_count}")
    print()

if __name__ == "__main__":
    main()
