# file: db_migrate.py
# description: 数据库迁移 CLI——幂等 create_all，与 app 启动时 init_db 同源
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-10-08
# status: active
# tags: [db],[migrate],[cli]

"""
@file: core/scripts/db_migrate.py
@description: `make db-migrate` 的实现体。把 core/api 注册为 "app" 包（对齐容器内
core/api→/app/app 映射，同 tests/conftest.py 机制），然后执行 init_db() 幂等同步表结构。
部署机上的增量迁移（备份 + migrations 目录）用 scripts/db-migrate.sh，本脚本面向开发本地。
"""

import asyncio
import importlib.util
import os
import sys

_API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api"))

_spec = importlib.util.spec_from_file_location(
    "app",
    os.path.join(_API_DIR, "__init__.py"),
    submodule_search_locations=[_API_DIR],
)
_pkg = importlib.util.module_from_spec(_spec)
sys.modules["app"] = _pkg
_spec.loader.exec_module(_pkg)

from app.db import init_db  # noqa: E402


def main() -> None:
    asyncio.run(init_db())
    print("✅ 表结构同步完成（create_all 幂等）")


if __name__ == "__main__":
    main()
