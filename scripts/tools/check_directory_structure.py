#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
file: check_directory_structure.py
description: YYC³ 项目目录结构检查脚本 - 检查项目目录结构是否符合规范
author: YanYuCloudCube Team
version: v1.0.0
created: 2026-04-04
updated: 2026-04-04
status: active
tags: [script],[directory],[structure]
"""

from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path("/Volumes/Development/项目提示词/0379-world")

# 必需的目录结构
REQUIRED_DIRECTORIES = {
    "core": "核心代码目录",
    "core/api": "API 服务代码目录",
    "core/config": "配置文件目录",
    "core/docs": "文档目录",
    "core/scripts": "脚本文件目录",
    "core/database": "数据库相关文件目录",
    "core/models": "模型配置目录",
}

# 推荐的目录结构
RECOMMENDED_DIRECTORIES = {
    "tests": "测试文件目录",
    "core/tests": "核心代码测试目录",
}

# 必需的根目录文件
REQUIRED_ROOT_FILES = {
    "README.md": "项目说明文档",
    ".gitignore": "Git 忽略配置",
    "requirements.txt": "Python 依赖配置",
    ".env.example": "环境变量示例文件",
}

# 推荐的根目录文件
RECOMMENDED_ROOT_FILES = {
    "CHANGELOG.md": "版本变更日志",
    "CONTRIBUTING.md": "贡献指南",
    "LICENSE": "开源许可证",
    "Makefile": "构建脚本",
    "Dockerfile": "Docker 构建文件",
}

def check_directory_structure() -> Tuple[List[str], List[str], List[str], List[str]]:
    """检查目录结构"""
    missing_required_dirs = []
    missing_recommended_dirs = []
    missing_required_files = []
    missing_recommended_files = []
    
    # 检查必需的目录
    for dir_path, description in REQUIRED_DIRECTORIES.items():
        full_path = PROJECT_ROOT / dir_path
        if not full_path.exists():
            missing_required_dirs.append(f"{dir_path} - {description}")
    
    # 检查推荐的目录
    for dir_path, description in RECOMMENDED_DIRECTORIES.items():
        full_path = PROJECT_ROOT / dir_path
        if not full_path.exists():
            missing_recommended_dirs.append(f"{dir_path} - {description}")
    
    # 检查必需的文件
    for file_path, description in REQUIRED_ROOT_FILES.items():
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            missing_required_files.append(f"{file_path} - {description}")
    
    # 检查推荐的文件
    for file_path, description in RECOMMENDED_ROOT_FILES.items():
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            missing_recommended_files.append(f"{file_path} - {description}")
    
    return (
        missing_required_dirs,
        missing_recommended_dirs,
        missing_required_files,
        missing_recommended_files
    )

def main():
    """主函数"""
    print("=" * 50)
    print("YYC³ 项目目录结构检查")
    print("=" * 50)
    print()
    
    # 检查目录结构
    (
        missing_required_dirs,
        missing_recommended_dirs,
        missing_required_files,
        missing_recommended_files
    ) = check_directory_structure()
    
    # 显示结果
    print("📁 目录结构检查结果")
    print()
    
    # 必需的目录
    if missing_required_dirs:
        print("❌ 缺少必需的目录:")
        for item in missing_required_dirs:
            print(f"   - {item}")
    else:
        print("✅ 所有必需的目录都存在")
    
    print()
    
    # 推荐的目录
    if missing_recommended_dirs:
        print("⚠️  缺少推荐的目录:")
        for item in missing_recommended_dirs:
            print(f"   - {item}")
    else:
        print("✅ 所有推荐的目录都存在")
    
    print()
    
    # 必需的文件
    if missing_required_files:
        print("❌ 缺少必需的文件:")
        for item in missing_required_files:
            print(f"   - {item}")
    else:
        print("✅ 所有必需的文件都存在")
    
    print()
    
    # 推荐的文件
    if missing_recommended_files:
        print("⚠️  缺少推荐的文件:")
        for item in missing_recommended_files:
            print(f"   - {item}")
    else:
        print("✅ 所有推荐的文件都存在")
    
    print()
    print("=" * 50)
    print("✅ 检查完成")
    print("=" * 50)
    print()
    
    # 计算合规率
    total_required = len(REQUIRED_DIRECTORIES) + len(REQUIRED_ROOT_FILES)
    missing_required = len(missing_required_dirs) + len(missing_required_files)
    compliance_rate = (total_required - missing_required) * 100 // total_required if total_required > 0 else 100
    
    print(f"必需项合规率: {compliance_rate}%")
    print()
    
    # 显示建议
    if missing_required_dirs or missing_required_files:
        print("=" * 50)
        print("📋 修复建议")
        print("=" * 50)
        print()
        
        if missing_required_dirs:
            print("创建缺少的目录:")
            for item in missing_required_dirs:
                dir_path = item.split(" - ")[0]
                print(f"  mkdir -p {dir_path}")
            print()
        
        if missing_required_files:
            print("创建缺少的文件:")
            for item in missing_required_files:
                print(f"  touch {item.split(' - ')[0]}")
            print()

if __name__ == "__main__":
    main()
