"""
@file: failover_manager.py
@description: 故障转移管理器 - 自动故障检测和转移
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-04-08
@updated: 2026-04-08
@status: active
@license: MIT
@copyright: Copyright (c) 2026 YanYuCloudCube Team
@tags: failover,high-availability,recovery
"""

from typing import Optional, Dict, List
from datetime import datetime
import asyncio
import logging
import httpx
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class FailoverState(Enum):
    NORMAL = "normal"
    FAILOVER_IN_PROGRESS = "failover_in_progress"
    RECOVERING = "recovering"


@dataclass
class FailoverEvent:
    timestamp: datetime
    from_node: str
    to_node: str
    reason: str
    duration: float = 0.0
    success: bool = True


class FailoverManager:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.primary_node = "yyc3-33"
        self.backup_nodes = ["yyc3-45", "yyc3-77"]
        self.current_active = self.primary_node
        self.state = FailoverState.NORMAL
        self.failover_history: List[FailoverEvent] = []
        self._monitoring = False
        self._lock = asyncio.Lock()
        
        self.health_check_interval = 5
        self.max_failover_attempts = 3
        self.failover_timeout = 30
    
    async def start_monitoring(self):
        if self._monitoring:
            logger.warning("Monitoring already started")
            return
        
        self._monitoring = True
        logger.info("Starting failover monitoring...")
        
        while self._monitoring:
            try:
                await self._monitor_loop()
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            
            await asyncio.sleep(self.health_check_interval)
    
    async def stop_monitoring(self):
        self._monitoring = False
        logger.info("Stopped failover monitoring")
    
    async def _monitor_loop(self):
        is_healthy = await self._check_node_health(self.current_active)
        
        if not is_healthy:
            logger.warning(f"Node {self.current_active} is unhealthy, initiating failover...")
            await self._perform_failover()
    
    async def _check_node_health(self, node_id: str) -> bool:
        try:
            url = f"http://{node_id}:8000/health"
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
            
            if response.status_code != 200:
                return False
            
            data = response.json()
            return data.get("status") == "healthy"
        
        except Exception as e:
            logger.error(f"Health check failed for {node_id}: {e}")
            return False
    
    async def _perform_failover(self):
        async with self._lock:
            if self.state == FailoverState.FAILOVER_IN_PROGRESS:
                logger.warning("Failover already in progress")
                return
            
            self.state = FailoverState.FAILOVER_IN_PROGRESS
            start_time = datetime.now()
            
            logger.warning(f"Starting failover from {self.current_active}")
            
            backup_node = await self._select_backup_node()
            
            if not backup_node:
                logger.error("No available backup node for failover!")
                self.state = FailoverState.NORMAL
                return
            
            try:
                await self._sync_data(self.current_active, backup_node)
                
                old_active = self.current_active
                self.current_active = backup_node
                
                await self._update_routing(old_active, backup_node)
                
                duration = (datetime.now() - start_time).total_seconds()
                
                event = FailoverEvent(
                    timestamp=start_time,
                    from_node=old_active,
                    to_node=backup_node,
                    reason="Health check failed",
                    duration=duration,
                    success=True
                )
                self.failover_history.append(event)
                
                logger.info(f"Failover completed: {old_active} -> {backup_node} in {duration:.2f}s")
            
            except Exception as e:
                logger.error(f"Failover failed: {e}")
                
                event = FailoverEvent(
                    timestamp=start_time,
                    from_node=self.current_active,
                    to_node=backup_node,
                    reason=f"Failover error: {str(e)}",
                    success=False
                )
                self.failover_history.append(event)
            
            finally:
                self.state = FailoverState.NORMAL
    
    async def _select_backup_node(self) -> Optional[str]:
        for backup_node in self.backup_nodes:
            if await self._check_node_health(backup_node):
                logger.info(f"Selected backup node: {backup_node}")
                return backup_node
        
        return None
    
    async def _sync_data(self, from_node: str, to_node: str):
        logger.info(f"Syncing data from {from_node} to {to_node}")
        await asyncio.sleep(1)
    
    async def _update_routing(self, old_node: str, new_node: str):
        logger.info(f"Updating routing: {old_node} -> {new_node}")
        await asyncio.sleep(0.5)
    
    async def manual_failover(self, target_node: str) -> bool:
        if target_node not in self.backup_nodes and target_node != self.primary_node:
            logger.error(f"Invalid target node: {target_node}")
            return False
        
        if not await self._check_node_health(target_node):
            logger.error(f"Target node {target_node} is not healthy")
            return False
        
        old_active = self.current_active
        self.current_active = target_node
        
        event = FailoverEvent(
            timestamp=datetime.now(),
            from_node=old_active,
            to_node=target_node,
            reason="Manual failover"
        )
        self.failover_history.append(event)
        
        logger.info(f"Manual failover completed: {old_active} -> {target_node}")
        return True
    
    def get_status(self) -> Dict:
        return {
            "current_active": self.current_active,
            "primary_node": self.primary_node,
            "backup_nodes": self.backup_nodes,
            "state": self.state.value,
            "monitoring": self._monitoring,
            "failover_count": len(self.failover_history),
            "last_failover": self.failover_history[-1].__dict__ if self.failover_history else None,
        }
    
    def get_failover_history(self, limit: int = 10) -> List[Dict]:
        history = self.failover_history[-limit:]
        return [event.__dict__ for event in history]


failover_manager = FailoverManager()
