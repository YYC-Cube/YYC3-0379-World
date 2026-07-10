#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
file: fix-documentation.py
description: YYC³ 文档合规性修复脚本 - 自动为所有 Markdown 文档添加符合规范的 YAML Front Matter 标头
author: YanYuCloudCube Team
version: v1.0.0
created: 2026-04-04
updated: 2026-04-04
status: active
tags: [script],[documentation],[compliance]
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path("/Volumes/Development/项目提示词/0379-world")

# 必填字段
REQUIRED_FIELDS = [
    "file", "description", "author", "version", 
    "created", "updated", "status", "tags", 
    "category", "language"
]

# 文件信息映射
FILE_INFO = {
    "core/config/.env.0379-world/README.md": {
        "file": "README.md",
        "description": "0379-world 后端服务器配置说明",
        "category": "configuration",
        "tags": ["configuration", "env", "backend"]
    },
    "core/config/.env.0379-world/DEPLOYMENT.md": {
        "file": "DEPLOYMENT.md",
        "description": "部署配置说明文档",
        "category": "deployment",
        "tags": ["deployment", "configuration", "env"]
    },
    "core/config/.env.yyc3/README.md": {
        "file": "README.md",
        "description": "YYC³ 环境变量配置说明",
        "category": "configuration",
        "tags": ["configuration", "env", "yyc3"]
    },
    "core/models/MODEL_CONFIGURATION_PLAN.md": {
        "file": "MODEL_CONFIGURATION_PLAN.md",
        "description": "模型配置方案文档",
        "category": "model",
        "tags": ["model", "ai", "configuration"]
    },
    "core/models/MCP/README.md": {
        "file": "README.md",
        "description": "MCP 工具配置说明文档",
        "category": "mcp",
        "tags": ["mcp", "tools", "configuration"]
    },
    "core/models/MCP/INTEGRATION_GUIDE.md": {
        "file": "INTEGRATION_GUIDE.md",
        "description": "MCP 集成指南文档",
        "category": "guide",
        "tags": ["guide", "mcp", "integration"]
    },
    "core/docs/PROJECT_STATUS_ANALYSIS.md": {
        "file": "PROJECT_STATUS_ANALYSIS.md",
        "description": "项目现状分析文档",
        "category": "analysis",
        "tags": ["analysis", "project", "status"]
    },
    "core/docs/API_FULL_LINK_ARCHITECTURE.md": {
        "file": "API_FULL_LINK_ARCHITECTURE.md",
        "description": "API 全链路架构文档",
        "category": "architecture",
        "tags": ["architecture", "api", "design"]
    },
    "core/docs/OVERALL_ARCHITECTURE.md": {
        "file": "OVERALL_ARCHITECTURE.md",
        "description": "整体架构设计文档",
        "category": "architecture",
        "tags": ["architecture", "design", "system"]
    },
}

def create_yaml_front_matter(file_info: Dict) -> str:
    """创建 YAML Front Matter 标头"""
    tags_str = ",".join([f"[{tag}]" for tag in file_info["tags"]])
    
    return f"""---
file: {file_info['file']}
description: {file_info['description']}
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-03-21
updated: 2026-04-04
status: stable
tags: {tags_str}
category: {file_info['category']}
language: zh-CN
---

> ***YanYuCloudCube***
> *言启象限 | 语枢未来*
> ***Words Initiate Quadrants, Language Serves as Core for Future***
> *万象归元于云枢 | 深栈智启新纪元*
> ***All things converge in cloud pivot; Deep stacks ignite a new era of intelligence***

---

"""

def has_yaml_front_matter(content: str) -> bool:
    """检查内容是否已有 YAML Front Matter"""
    return content.strip().startswith("---\n")

def fix_documentation(file_path: Path, file_info: Dict) -> Tuple[bool, str]:
    """修复文档"""
    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否已有 YAML Front Matter
        if has_yaml_front_matter(content):
            return False, "已有 YAML Front Matter"
        
        # 创建新的 YAML Front Matter
        yaml_header = create_yaml_front_matter(file_info)
        
        # 移除旧的注释标头（如果有）
        lines = content.split('\n')
        start_index = 0
        
        # 跳过开头的注释行
        for i, line in enumerate(lines):
            if line.startswith('#') or line.strip() == '':
                start_index = i + 1
            else:
                break
        
        # 获取实际内容
        actual_content = '\n'.join(lines[start_index:])
        
        # 合并新标头和内容
        new_content = yaml_header + actual_content
        
        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return True, "修复成功"
    
    except Exception as e:
        return False, f"修复失败: {str(e)}"

def main():
    """主函数"""
    print("=" * 50)
    print("YYC³ 文档合规性修复")
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
        
        success, message = fix_documentation(file_path, file_info)
        
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
