#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
file: check_project_completeness.py
description: YYC³ 项目完整性检查脚本 - 全面检查项目所有组件是否完备
author: YanYuCloudCube Team
version: v1.0.0
created: 2026-04-04
updated: 2026-04-04
status: active
tags: [script],[check],[completeness]
"""

from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path("/Volumes/Development/项目提示词/0379-world")

# 项目组件定义
PROJECT_COMPONENTS = {
    "核心代码": {
        "required": {
            "core/api/main.py": "API 服务入口",
            "core/api/config.py": "配置管理",
            "core/api/db.py": "数据库连接",
            "core/api/models.py": "数据模型",
            "core/api/cache.py": "缓存管理",
        },
        "recommended": {
            "core/api/api/chat.py": "聊天 API",
            "core/api/api/schemas.py": "API 模式",
            "core/api/services/": "服务模块",
            "core/api/utils/": "工具函数",
            "core/api/middleware/": "中间件",
            "core/api/errors/": "错误处理",
        }
    },
    "配置文件": {
        "required": {
            ".env.example": "环境变量示例",
            "requirements.txt": "Python 依赖",
            ".gitignore": "Git 忽略配置",
        },
        "recommended": {
            "core/config/.env.0379-world/": "环境变量配置",
            "core/config/docker/": "Docker 配置",
            "core/config/prometheus/": "Prometheus 配置",
            "core/config/redis/": "Redis 配置",
            "core/config/traefik/": "Traefik 配置",
        }
    },
    "数据库": {
        "required": {
            "core/database/docker/docker-compose.yml": "Docker Compose 配置",
            "core/database/docker/docker-compose.stable.yml": "稳定版配置",
        },
        "recommended": {
            "core/database/docker/Dockerfile": "Docker 构建文件",
            "core/database/docker/prometheus/": "Prometheus 配置",
        }
    },
    "文档": {
        "required": {
            "README.md": "项目说明",
            "CHANGELOG.md": "变更日志",
            "CONTRIBUTING.md": "贡献指南",
            "LICENSE": "开源许可证",
        },
        "recommended": {
            "core/docs/": "核心文档",
            "core/README.md": "核心模块说明",
        }
    },
    "测试": {
        "required": {
            "tests/": "测试目录",
        },
        "recommended": {
            "core/tests/": "核心测试",
            "pytest.ini": "Pytest 配置",
            "requirements-dev.txt": "开发依赖",
        }
    },
    "部署": {
        "required": {
            "Dockerfile": "Docker 构建文件",
            "Makefile": "构建脚本",
        },
        "recommended": {
            "docker-compose.yml": "Docker Compose 主配置",
            ".dockerignore": "Docker 忽略配置",
        }
    },
    "监控": {
        "required": {},
        "recommended": {
            "core/scripts/": "监控脚本",
            "core/config/prometheus/rules/": "告警规则",
        }
    },
    "模型配置": {
        "required": {},
        "recommended": {
            "core/models/MCP/": "MCP 工具配置",
            "core/models/MODEL_CONFIGURATION_PLAN.md": "模型配置方案",
        }
    }
}

def check_component(component_path: str) -> Tuple[bool, str]:
    """检查组件是否存在"""
    full_path = PROJECT_ROOT / component_path
    
    if full_path.exists():
        if full_path.is_dir():
            # 检查目录是否为空
            if any(full_path.iterdir()):
                return True, "✅ 存在且有内容"
            else:
                return True, "⚠️  存在但为空"
        else:
            return True, "✅ 存在"
    else:
        return False, "❌ 不存在"

def check_project_completeness() -> Dict:
    """检查项目完整性"""
    results = {
        "total_required": 0,
        "total_recommended": 0,
        "missing_required": [],
        "missing_recommended": [],
        "existing_required": [],
        "existing_recommended": [],
        "categories": {}
    }
    
    for category, components in PROJECT_COMPONENTS.items():
        category_result = {
            "required": {"total": 0, "existing": 0, "missing": []},
            "recommended": {"total": 0, "existing": 0, "missing": []}
        }
        
        # 检查必需组件
        for component_path, description in components.get("required", {}).items():
            results["total_required"] += 1
            category_result["required"]["total"] += 1
            
            exists, status = check_component(component_path)
            
            if exists:
                results["existing_required"].append(f"{component_path} - {description}")
                category_result["required"]["existing"] += 1
            else:
                results["missing_required"].append(f"{component_path} - {description}")
                category_result["required"]["missing"].append(f"{component_path} - {description}")
        
        # 检查推荐组件
        for component_path, description in components.get("recommended", {}).items():
            results["total_recommended"] += 1
            category_result["recommended"]["total"] += 1
            
            exists, status = check_component(component_path)
            
            if exists:
                results["existing_recommended"].append(f"{component_path} - {description}")
                category_result["recommended"]["existing"] += 1
            else:
                results["missing_recommended"].append(f"{component_path} - {description}")
                category_result["recommended"]["missing"].append(f"{component_path} - {description}")
        
        results["categories"][category] = category_result
    
    return results

def main():
    """主函数"""
    print("=" * 60)
    print("YYC³ 0379-world 项目完整性检查")
    print("=" * 60)
    print()
    
    results = check_project_completeness()
    
    # 显示各分类检查结果
    for category, category_result in results["categories"].items():
        print(f"📦 {category}")
        
        # 必需组件
        if category_result["required"]["total"] > 0:
            required_rate = category_result["required"]["existing"] * 100 // category_result["required"]["total"]
            status = "✅" if required_rate == 100 else "⚠️" if required_rate >= 50 else "❌"
            print(f"   必需组件: {category_result['required']['existing']}/{category_result['required']['total']} ({required_rate}%) {status}")
            
            if category_result["required"]["missing"]:
                for item in category_result["required"]["missing"]:
                    print(f"      ❌ {item}")
        
        # 推荐组件
        if category_result["recommended"]["total"] > 0:
            recommended_rate = category_result["recommended"]["existing"] * 100 // category_result["recommended"]["total"] if category_result["recommended"]["total"] > 0 else 100
            status = "✅" if recommended_rate >= 80 else "⚠️" if recommended_rate >= 50 else "❌"
            print(f"   推荐组件: {category_result['recommended']['existing']}/{category_result['recommended']['total']} ({recommended_rate}%) {status}")
            
            if category_result["recommended"]["missing"]:
                for item in category_result["recommended"]["missing"]:
                    print(f"      ⚠️  {item}")
        
        print()
    
    # 显示总体统计
    print("=" * 60)
    print("📊 总体统计")
    print("=" * 60)
    print()
    
    required_rate = results["existing_required"].__len__() * 100 // results["total_required"] if results["total_required"] > 0 else 100
    recommended_rate = results["existing_recommended"].__len__() * 100 // results["total_recommended"] if results["total_recommended"] > 0 else 100
    
    print(f"必需组件: {len(results['existing_required'])}/{results['total_required']} ({required_rate}%)")
    print(f"推荐组件: {len(results['existing_recommended'])}/{results['total_recommended']} ({recommended_rate}%)")
    print()
    
    # 计算综合评分
    total_score = (required_rate * 0.7 + recommended_rate * 0.3)
    print(f"综合评分: {total_score:.1f}/100")
    
    # 评级
    if total_score >= 90:
        grade = "A (优秀)"
        emoji = "🏆"
    elif total_score >= 80:
        grade = "B (良好)"
        emoji = "👍"
    elif total_score >= 70:
        grade = "C (合格)"
        emoji = "✅"
    elif total_score >= 60:
        grade = "D (需改进)"
        emoji = "⚠️"
    else:
        grade = "F (不合格)"
        emoji = "❌"
    
    print(f"项目评级: {grade} {emoji}")
    print()
    
    # 显示缺失的必需组件
    if results["missing_required"]:
        print("=" * 60)
        print("❌ 缺失的必需组件")
        print("=" * 60)
        print()
        for item in results["missing_required"]:
            print(f"  • {item}")
        print()
    
    # 显示缺失的推荐组件
    if results["missing_recommended"]:
        print("=" * 60)
        print("⚠️  缺失的推荐组件")
        print("=" * 60)
        print()
        for item in results["missing_recommended"]:
            print(f"  • {item}")
        print()
    
    # 建议
    print("=" * 60)
    print("💡 改进建议")
    print("=" * 60)
    print()
    
    if results["missing_required"]:
        print("🔴 高优先级:")
        print("   补充缺失的必需组件，确保项目基本功能完整")
        print()
    
    if results["missing_recommended"]:
        print("🟡 中优先级:")
        print("   添加推荐的组件，提升项目质量和可维护性")
        print()
    
    if not results["missing_required"] and not results["missing_recommended"]:
        print("🎉 恭喜！项目组件已完备，可以正常使用和开发")
        print()
    
    print("=" * 60)

if __name__ == "__main__":
    main()
