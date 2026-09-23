# file: sitecustomize.py
# description: importlinter 启动引导 - 预注册 app 包（core/api 动态映射，同 tests/conftest.py 机制）
# created: 2026-09-20
# status: active

"""用法：PYTHONPATH=$REPO/scripts/importlinter_boot lint-imports --config .importlinter

importlinter 需要在 Python path 中发现 root_package=app；本项目 app 是 core/api
的运行时映射（tests/conftest.py 同款），此引导在解释器启动时完成注册。
"""

import importlib.util
import os
import sys

# __file__ = <repo>/scripts/importlinter_boot/sitecustomize.py → repo 根需三级 dirname
_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_pkg_dir = os.path.join(_repo_root, "core", "api")

if os.path.isfile(os.path.join(_pkg_dir, "__init__.py")) and "app" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "app", os.path.join(_pkg_dir, "__init__.py"), submodule_search_locations=[_pkg_dir]
    )
    if _spec is not None and _spec.loader is not None:
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["app"] = _mod
        _spec.loader.exec_module(_mod)
