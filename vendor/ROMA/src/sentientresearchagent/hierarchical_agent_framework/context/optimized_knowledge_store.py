"""
OptimizedKnowledgeStore - Performance-optimized version of KnowledgeStore.

This implementation adds:
- Read caching with TTL
- Write buffering for batch operations
- Lock-free reads when possible
- Lazy serialization
"""

import time
import threading
from typing import Dict, List, Optional, Any, Tuple
from collections import OrderedDict
from loguru import logger

from .knowledge_store import KnowledgeStore, TaskRecord


class LRUCache:
    """Simple LRU cache implementation for read optimization."""
    
    def __init__(self, max_size: int = 1000, ttl_ms: int = 5000):
        self.max_size = max_size
        self.ttl_ms = ttl_ms
        self.cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache if not expired."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if (time.time() * 1000 - timestamp) < self.ttl_ms:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                self.hits += 1
                return value
            else:
                # Expired
                del self.cache[key]
        
        self.misses += 1
        return None
    
    def put(self, key: str, value: Any):
        """Add item to cache."""
        # Remove oldest if at capacity
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        
        self.cache[key] = (value, time.time() * 1000)
    
    def invalidate(self, key: str):
        """Remove item from cache."""
        self.cache.pop(key, None)
    
    def clear(self):
        """Clear entire cache."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "size": len(self.cache)
        }


class OptimizedKnowledgeStore(KnowledgeStore):
    """
    Performance-optimized KnowledgeStore with caching and batching.
    
    Features:
    - Read cache with LRU eviction
    - Write buffering for batch updates
    - Reduced lock contention
    - Lazy record creation
    """
    
    def __init__(
        self, 
        cache_size: int = 1000,
        cache_ttl_ms: int = 5000,
        write_buffer_size: int = 100,
        enable_optimization: bool = True
    ):
        """
        Initialize OptimizedKnowledgeStore.
        
        Args:
            cache_size: Maximum number of cached reads
            cache_ttl_ms: Cache TTL in milliseconds
            write_buffer_size: Maximum write buffer size before flush
            enable_optimization: Whether to enable optimizations
        """
        super().__init__()
        
        # Optimization settings - store as private attributes to avoid Pydantic validation
        object.__setattr__(self, '_optimization_enabled', enable_optimization)
        object.__setattr__(self, '_write_buffer_size', write_buffer_size)
        
        # Read cache
        object.__setattr__(self, '_read_cache', LRUCache(max_size=cache_size, ttl_ms=cache_ttl_ms))
        
        # Write buffer (thread-local for safety)
        object.__setattr__(self, '_write_buffer_tls', threading.local())
        
        # Statistics
        object.__setattr__(self, '_stats', {
            "reads": 0,
            "writes": 0,
            "buffer_flushes": 0,
            "cache_invalidations": 0
        })
    
    def _get_write_buffer(self) -> List[Any]:
        """Get thread-local write buffer."""
        if not hasattr(self._write_buffer_tls, 'buffer'):
            self._write_buffer_tls.buffer = []
        return self._write_buffer_tls.buffer
    
    def add_or_update_record_from_node(self, node: Any, immediate: bool = False):
        """
        Optimized version that can buffer updates.
        
        Args:
            node: Node to add/update
            immediate: Force immediate write (bypass buffer)
        """
        if not self._optimization_enabled or immediate:
            # Use original implementation
            super().add_or_update_record_from_node(node)
            self._read_cache.invalidate(node.task_id)
            return
        
        # Buffer the update
        buffer = self._get_write_buffer()
        buffer.append(node)
        
        # Flush if buffer is full
        if len(buffer) >= self._write_buffer_size:
            self.flush_write_buffer()
    
    def flush_write_buffer(self):
        """Flush all buffered writes."""
        buffer = self._get_write_buffer()
        if not buffer:
            return
        
        # Batch process all updates
        with self._lock:
            for node in buffer:
                # Create record without logging each one
                task_type_val = str(node.task_type)
                node_type_val = str(node.node_type) if node.node_type else None
                status_val = str(node.status)

                record = TaskRecord(
                    task_id=node.task_id,
                    goal=node.goal,
                    task_type=task_type_val,
                    node_type=node_type_val,
                    input_params_dict=node.input_payload_dict or {},
                    output_content=node.result,
                    output_type_description=node.output_type_description,
                    output_summary=node.output_summary,
                    status=status_val,
                    timestamp_created=node.timestamp_created,
                    timestamp_updated=node.timestamp_updated,
                    timestamp_completed=node.timestamp_completed,
                    parent_task_id=node.parent_node_id,
                    child_task_ids_generated=node.planned_sub_task_ids or [],
                    layer=node.layer,
                    error_message=node.error,
                    sub_graph_id=node.sub_graph_id,
                    aux_data=node.aux_data or {},
                    result=node.result,
                    planned_sub_task_ids=node.planned_sub_task_ids or []
                )
                self.records[record.task_id] = record
                
                # Invalidate cache for this record
                self._read_cache.invalidate(record.task_id)
        
        # Log once for entire batch
        logger.debug(f"KnowledgeStore: Flushed {len(buffer)} records")
        self._stats["buffer_flushes"] += 1
        self._stats["writes"] += len(buffer)
        
        # Clear buffer
        buffer.clear()
    
    def get_record(self, task_id: str) -> Optional[TaskRecord]:
        """Optimized get with caching."""
        self._stats["reads"] += 1
        
        if not self._optimization_enabled:
            return super().get_record(task_id)
        
        # Try cache first
        cached = self._read_cache.get(task_id)
        if cached is not None:
            return cached
        
        # Fall back to locked read
        record = super().get_record(task_id)
        
        # Cache the result
        if record is not None:
            self._read_cache.put(task_id, record)
        
        return record
    
    def get_child_records(self, parent_task_id: str) -> List[TaskRecord]:
        """Optimized child record retrieval."""
        if not self._optimization_enabled:
            return super().get_child_records(parent_task_id)
        
        # Try cache first
        cache_key = f"children_{parent_task_id}"
        cached = self._read_cache.get(cache_key)
        if cached is not None:
            return cached
        
        # Fall back to locked read
        records = super().get_child_records(parent_task_id)
        
        # Cache the result
        self._read_cache.put(cache_key, records)
        
        return records
    
    def clear(self):
        """Clear all records and caches."""
        super().clear()
        self._read_cache.clear()
        
        # Clear any thread-local buffers
        if hasattr(self._write_buffer_tls, 'buffer'):
            self._write_buffer_tls.buffer.clear()
        
        self._stats["cache_invalidations"] += 1
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        cache_stats = self._read_cache.get_stats()
        
        return {
            "knowledge_store": {
                "reads": self._stats["reads"],
                "writes": self._stats["writes"],
                "buffer_flushes": self._stats["buffer_flushes"],
                "cache_invalidations": self._stats["cache_invalidations"]
            },
            "read_cache": cache_stats,
            "optimization_enabled": self._optimization_enabled
        }
    
    def disable_optimization(self):
        """Disable all optimizations (useful for debugging)."""
        self.flush_write_buffer()
        self._optimization_enabled = False
        self._read_cache.clear()
        logger.info("OptimizedKnowledgeStore: Optimizations disabled")
    
    def enable_optimization(self):
        """Re-enable optimizations."""
        self._optimization_enabled = True
        logger.info("OptimizedKnowledgeStore: Optimizations enabled")