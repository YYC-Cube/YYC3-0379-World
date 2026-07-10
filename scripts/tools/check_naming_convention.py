#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
file: check_naming_convention.py
description: YYC³ 文件命名规范检查脚本 - 检查所有文件是否符合命名规范
author: YanYuCloudCube Team
version: v1.0.0
created: 2026-04-04
updated: 2026-04-04
status: active
tags: [script],[naming],[convention]
"""

import re
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path("/Volumes/Development/项目提示词/0379-world")

# 特殊文件名（允许的例外）
SPECIAL_FILES = [
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "LICENSE.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "Makefile",
    "Dockerfile",
    ".gitignore",
    ".env",
    ".env.example",
]

# 文件命名规范
NAMING_RULES = {
    ".py": {
        "pattern": r"^[a-z0-9_]+\.py$",
        "description": "Python 文件应使用 snake_case（下划线命名法）"
    },
    ".sh": {
        "pattern": r"^[a-z0-9_\-\.]+\.sh$",
        "description": "Shell 脚本文件应使用 kebab-case 或 snake_case"
    },
}

# 忽略的文件和目录
IGNORE_PATTERNS = [
    r"^\.",  # 隐藏文件
    r"^node_modules$",
    r"^__pycache__$",
    r"^\.git$",
    r"^\.venv$",
    r"^venv$",
    r"^dist$",
    r"^build$",
    r"^\.pytest_cache$",
]

def should_ignore(path: Path) -> bool:
    """判断是否应该忽略该路径"""
    for pattern in IGNORE_PATTERNS:
        if re.search(pattern, path.name):
            return True
    return False

def is_special_file(file_path: Path) -> bool:
    """判断是否是特殊文件"""
    return file_path.name in SPECIAL_FILES

def check_file_naming(file_path: Path) -> Tuple[bool, str]:
    """检查文件命名是否符合规范"""
    # 如果是特殊文件，则跳过
    if is_special_file(file_path):
        return True, "特殊文件名"
    
    ext = file_path.suffix.lower()
    
    # 如果没有对应的命名规则，则跳过
    if ext not in NAMING_RULES:
        return True, "无命名规范要求"
    
    rule = NAMING_RULES[ext]
    pattern = rule["pattern"]
    
    # 检查文件名是否符合规范
    if re.match(pattern, file_path.name):
        return True, "符合规范"
    else:
        return False, rule["description"]

def main():
    """主函数"""
    print("=" * 50)
    print("YYC³ 文件命名规范检查")
    print("=" * 50)
    print()
    
    # 查找所有文件
    all_files = []
    for ext in NAMING_RULES.keys():
        all_files.extend(PROJECT_ROOT.rglob(f"*{ext}"))
    
    # 过滤掉应该忽略的文件
    all_files = [f for f in all_files if not should_ignore(f)]
    
    compliant_count = 0
    non_compliant_count = 0
    issues = []
    
    for file_path in sorted(all_files):
        rel_path = file_path.relative_to(PROJECT_ROOT)
        
        is_compliant, message = check_file_naming(file_path)
        
        if is_compliant:
            compliant_count += 1
        else:
            non_compliant_count += 1
            issues.append((rel_path, message))
            print(f"❌ {rel_path}")
            print(f"   - {message}")
    
    print()
    print("=" * 50)
    print("✅ 检查完成")
    print("=" * 50)
    print()
    print(f"总文件数: {len(all_files)}")
    print(f"符合规范: {compliant_count}")
    print(f"不符合规范: {non_compliant_count}")
    print(f"合规率: {compliant_count * 100 // len(all_files) if all_files else 0}%")
    print()
    
    if issues:
        print("=" * 50)
        print("📋 不符合规范的文件列表")
        print("=" * 50)
        print()
        for rel_path, message in issues:
            print(f"• {rel_path}")
            print(f"  {message}")
            print()

if __name__ == "__main__":
    main()
