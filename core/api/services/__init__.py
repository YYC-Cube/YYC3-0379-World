"""
@file: app/services/__init__.py
@description: 服务模块初始化
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-03-13
@updated: 2026-04-08
@status: stable
@license: MIT
@copyright: Copyright (c) 2026 YanYuCloudCube Team
@tags: init,python,services,public
"""

from app.services.zhipu import chat_completion as zhipu_chat
from app.services.ollama import chat_completion as ollama_chat
from app.services.deepseek import chat_completion as deepseek_chat

__all__ = ['zhipu', 'ollama', 'deepseek']

