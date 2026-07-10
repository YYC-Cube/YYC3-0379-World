# file: handler.py
# description: 错误处理器模块
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-03-21
# updated: 2026-04-04
# status: active
# tags: [error],[handler],[middleware]

"""
@file: app/errors/handler.py
@description: 错误处理器类，提供统一的错误处理机制
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-03-19
@updated: 2026-03-19
@status: stable
@license: MIT
@copyright: Copyright (c) 2026 YanYuCloudCube Team
@tags: errors,python,handler,public
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Callable, Type
from functools import wraps
from .exceptions import YYC3Error, NetworkError, APIError, TimeoutError, ValidationError


class ErrorHandler:
    """错误处理器类"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        self.error_types = {
            'network': NetworkError,
            'api': APIError,
            'timeout': TimeoutError,
            'validation': ValidationError
        }
        
        self.retry_config = {
            'network': {'max_retries': 3, 'delay': 1.0},
            'api': {'max_retries': 2, 'delay': 2.0},
            'timeout': {'max_retries': 2, 'delay': 1.0},
            'validation': {'max_retries': 0, 'delay': 0.0}
        }
    
    def _classify_error(self, error: Exception) -> str:
        """分类错误类型"""
        error_str = str(error).lower()
        
        if isinstance(error, YYC3Error):
            for error_type, error_class in self.error_types.items():
                if isinstance(error, error_class):
                    return error_type
        
        if 'timeout' in error_str or 'timed out' in error_str:
            return 'timeout'
        elif 'network' in error_str or 'connection' in error_str:
            return 'network'
        elif 'api' in error_str or 'http' in error_str:
            return 'api'
        elif 'validation' in error_str or 'invalid' in error_str:
            return 'validation'
        
        return 'api'
    
    async def _log_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ):
        """记录错误日志"""
        error_type = self._classify_error(error)
        
        log_data = {
            'error_type': error_type,
            'error_message': str(error),
            'error_class': error.__class__.__name__,
            'context': context or {}
        }
        
        if error_type == 'validation':
            self.logger.warning(log_data)
        else:
            self.logger.error(log_data, exc_info=True)
    
    def _format_response(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """格式化错误响应"""
        if isinstance(error, YYC3Error):
            return error.to_dict()
        
        error_type = self._classify_error(error)
        error_class = self.error_types.get(error_type, APIError)
        
        formatted_error = error_class(
            message=str(error),
            details=context
        )
        
        return formatted_error.to_dict()
    
    async def handle(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """处理错误"""
        await self._log_error(error, context)
        return self._format_response(error, context)
    
    async def retry(
        self,
        func: Callable,
        *args,
        max_retries: Optional[int] = None,
        delay: Optional[float] = None,
        **kwargs
    ):
        """重试机制"""
        last_error = None
        retry_count = 0
        
        while True:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                error_type = self._classify_error(e)
                config = self.retry_config.get(error_type, {})
                
                max_retries = max_retries or config.get('max_retries', 0)
                retry_delay = delay or config.get('delay', 1.0)
                
                if retry_count >= max_retries:
                    break
                
                retry_count += 1
                self.logger.info(
                    f"Retrying {func.__name__} (attempt {retry_count}/{max_retries}) "
                    f"after {retry_delay}s due to {error_type} error: {str(e)}"
                )
                await asyncio.sleep(retry_delay)
        
        raise last_error


error_handler = ErrorHandler()


def handle_errors(context: Optional[Dict[str, Any]] = None):
    """错误处理装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                ctx = context or {}
                ctx.update({
                    'function': func.__name__,
                    'args': str(args),
                    'kwargs': str(kwargs)
                })
                response = await error_handler.handle(e, ctx)
                raise HTTPException(
                    status_code=response['status_code'],
                    detail=response
                )
        return wrapper
    return decorator


def with_retry(
    max_retries: Optional[int] = None,
    delay: Optional[float] = None
):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await error_handler.retry(
                func,
                *args,
                max_retries=max_retries,
                delay=delay,
                **kwargs
            )
        return wrapper
    return decorator


from fastapi import HTTPException
