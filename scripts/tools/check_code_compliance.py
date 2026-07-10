#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
file: check-code-compliance.py
description: YYC³ 代码文件合规性检查脚本 - 检查所有代码文件的 JSDoc 标头注释
author: YanYuCloudCube Team
version: v1.0.0
created: 2026-04-04
updated: 2026-04-04
status: active
tags: [script],[code],[compliance]
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path("/Volumes/Development/项目提示词/0379-world")

# 必填字段
REQUIRED_FIELDS = [
    "file", "description", "author", "version",
    "created", "updated", "status", "tags"
]

def has_jsdoc_header(content: str) -> bool:
    """检查内容是否已有 JSDoc 标头"""
    return content.strip().startswith("/**")

def extract_jsdoc_fields(content: str) -> dict:
    """提取 JSDoc 标头中的字段"""
    fields = {}
    
    # 提取 JSDoc 注释块
    match = re.search(r'/\*\*(.*?)\*/', content, re.DOTALL)
    if not match:
        return fields
    
    jsdoc_content = match.group(1)
    
    # 提取各个字段
    for field in REQUIRED_FIELDS:
        pattern = rf'\*\s*{field}:\s*(.+)'
        match = re.search(pattern, jsdoc_content)
        if match:
            fields[field] = match.group(1).strip()
    
    return fields

def check_code_file(file_path: Path) -> Tuple[bool, List[str]]:
    """检查代码文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否有 JSDoc 标头
        if not has_jsdoc_header(content):
            return False, ["缺少 JSDoc 标头注释"]
        
        # 提取字段
        fields = extract_jsdoc_fields(content)
        
        # 检查必填字段
        missing_fields = []
        for field in REQUIRED_FIELDS:
            if field not in fields:
                missing_fields.append(field)
        
        if missing_fields:
            return False, [f"缺少必填字段: {', '.join(missing_fields)}"]
        
        return True, []
    
    except Exception as e:
        return False, [f"检查失败: {str(e)}"]

def main():
    """主函数"""
    print("=" * 50)
    print("YYC³ 代码文件合规性检查")
    print("=" * 50)
    print()
    
    # 查找所有代码文件
    code_files = []
    for ext in ['*.py', '*.js', '*.ts', '*.tsx', '*.jsx']:
        code_files.extend(PROJECT_ROOT.rglob(ext))
    
    # 过滤掉临时文件
    code_files = [f for f in code_files if not f.name.startswith('fix-') and not f.name.startswith('check-')]
    
    compliant_count = 0
    non_compliant_count = 0
    
    for file_path in sorted(code_files):
        rel_path = file_path.relative_to(PROJECT_ROOT)
        
        is_compliant, issues = check_code_file(file_path)
        
        if is_compliant:
            print(f"✅ {rel_path}")
            compliant_count += 1
        else:
            print(f"❌ {rel_path}")
            for issue in issues:
                print(f"   - {issue}")
            non_compliant_count += 1
    
    print()
    print("=" * 50)
    print("✅ 检查完成")
    print("=" * 50)
    print()
    print(f"总文件数: {len(code_files)}")
    print(f"符合规范: {compliant_count}")
    print(f"不符合规范: {non_compliant_count}")
    print(f"合规率: {compliant_count * 100 // len(code_files) if code_files else 0}%")
    print()

if __name__ == "__main__":
    main()
