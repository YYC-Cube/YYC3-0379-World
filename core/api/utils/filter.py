# file: filter.py
# description: 数据过滤工具模块
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-03-21
# updated: 2026-04-04
# status: active
# tags: [util],[filter],[validation]

"""
@file: app/utils/filter.py
@description: 内容过滤器，提供敏感词过滤和内容审核功能
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-03-19
@updated: 2026-03-19
@status: stable
@license: MIT
@copyright: Copyright (c) 2026 YanYuCloudCube Team
@tags: utils,python,filter,public
"""

import re
import logging
from typing import List, Tuple, Optional


class ContentFilter:
    """内容过滤器"""
    
    def __init__(self):
        self.sensitive_words = self._load_sensitive_words()
        self.logger = logging.getLogger(__name__)
        
        self.filter_stats = {
            'filtered': 0,
            'blocked': 0,
            'passed': 0
        }
    
    def _load_sensitive_words(self) -> List[str]:
        """加载敏感词列表"""
        return [
            'password',
            'secret',
            'token',
            'api_key',
            'private_key',
            'credit_card',
            'ssn',
            'social_security',
            'bank_account'
        ]
    
    def filter_content(
        self,
        content: str,
        mask_char: str = '*'
    ) -> Tuple[str, bool]:
        """过滤敏感内容"""
        if not content:
            return content, False
        
        filtered_content = content
        is_blocked = False
        
        for word in self.sensitive_words:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            matches = pattern.findall(filtered_content)
            
            if matches:
                filtered_content = pattern.sub(
                    mask_char * len(word),
                    filtered_content
                )
                self.filter_stats['filtered'] += len(matches)
                
                if len(matches) > 3:
                    is_blocked = True
                    self.filter_stats['blocked'] += 1
        
        if not is_blocked:
            self.filter_stats['passed'] += 1
        
        return filtered_content, is_blocked
    
    def filter_response(
        self,
        response: dict,
        mask_char: str = '*'
    ) -> Tuple[dict, bool]:
        """过滤响应内容"""
        if not response or 'choices' not in response:
            return response, False
        
        is_blocked = False
        
        for choice in response['choices']:
            if 'message' in choice and 'content' in choice['message']:
                filtered_content, blocked = self.filter_content(
                    choice['message']['content'],
                    mask_char
                )
                
                choice['message']['content'] = filtered_content
                
                if blocked:
                    is_blocked = True
        
        return response, is_blocked
    
    def get_stats(self) -> dict:
        """获取过滤统计"""
        return self.filter_stats.copy()
    
    def reset_stats(self):
        """重置过滤统计"""
        self.filter_stats = {
            'filtered': 0,
            'blocked': 0,
            'passed': 0
        }
        self.logger.info("Content filter stats reset")


content_filter = ContentFilter()
