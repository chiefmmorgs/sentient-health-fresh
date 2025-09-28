"""
CachedContextBuilder - Optimized context builder with caching.

This implementation adds:
- Context result caching with TTL
- Lazy context building
- Incremental context updates
- Cache invalidation strategies
"""

import time
import hashlib
import json
from typing import Dict, List, Optional, Any, Tuple, Set
from collections import OrderedDict
from loguru import logger

from .knowledge_store import TaskRecord, KnowledgeStore
from .context_builder import resolve_context_for_agent


class ContextCache:
    """Simple cache for context results."""
    
    def __init__(self, max_size: int = 100, ttl_ms: int = 30000):
        self.max_size = max_size
        self.ttl_ms = ttl_ms
        self.cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self.hits = 0
        self.misses = 0
    
    def _compute_key(self, node_id: str, layer: int, knowledge_checksum: str) -> str:
        """Compute cache key from context parameters."""
        key_data = f"{node_id}:{layer}:{knowledge_checksum}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, node_id: str, layer: int, knowledge_checksum: str) -> Optional[Any]:
        """Get cached context if not expired."""
        key = self._compute_key(node_id, layer, knowledge_checksum)
        
        if key in self.cache:
            context, timestamp = self.cache[key]
            if (time.time() * 1000 - timestamp) < self.ttl_ms:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                self.hits += 1
                return context
            else:
                # Expired
                del self.cache[key]
        
        self.misses += 1
        return None
    
    def put(self, node_id: str, layer: int, knowledge_checksum: str, context: Any):
        """Add context to cache."""
        key = self._compute_key(node_id, layer, knowledge_checksum)
        
        # Remove oldest if at capacity
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        
        self.cache[key] = (context, time.time() * 1000)
    
    def invalidate_node(self, node_id: str):
        """Invalidate all cache entries for a node."""
        keys_to_remove = [k for k in self.cache.keys() if k.startswith(node_id)]
        for key in keys_to_remove:
            del self.cache[key]
    
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


class CachedContextBuilder:
    """
    Performance-optimized context builder with caching.
    
    This is a wrapper around the existing context building functions
    that adds caching capabilities without changing the interface.
    
    Features:
    - Context result caching
    - Knowledge store checksum for cache invalidation
    - Lazy context building
    - Minimal context for certain operations
    """
    
    def __init__(
        self,
        knowledge_store: KnowledgeStore,
        cache_size: int = 100,
        cache_ttl_ms: int = 30000,
        enable_caching: bool = True
    ):
        """
        Initialize CachedContextBuilder.
        
        Args:
            knowledge_store: The knowledge store to use
            cache_size: Maximum number of cached contexts
            cache_ttl_ms: Cache TTL in milliseconds
            enable_caching: Whether to enable caching
        """
        self.knowledge_store = knowledge_store
        
        # Caching settings
        self.enable_caching = enable_caching
        self._context_cache = ContextCache(max_size=cache_size, ttl_ms=cache_ttl_ms)
        
        # Track knowledge store changes for cache invalidation
        self._last_knowledge_checksum = self._compute_knowledge_checksum()
        
        # Statistics
        self._stats = {
            "contexts_built": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
    
    def _compute_knowledge_checksum(self) -> str:
        """Compute a checksum of knowledge store state."""
        # Simple checksum based on record count and latest update times
        record_count = len(self.knowledge_store.records)
        
        if record_count == 0:
            return "empty"
        
        # Get latest update times
        latest_updates = sorted([
            r.timestamp_updated.isoformat() 
            for r in list(self.knowledge_store.records.values())[-10:]  # Last 10 records
        ])
        
        checksum_data = f"{record_count}:{':'.join(latest_updates)}"
        return hashlib.md5(checksum_data.encode()).hexdigest()
    
    def build_context_for_node(
        self,
        node: Any,
        max_context_length: int = 8000,
        minimal: bool = False
    ) -> str:
        """
        Build context for a node with caching support.
        
        Args:
            node: The node to build context for
            max_context_length: Maximum context length
            minimal: Whether to build minimal context (bypasses cache)
        
        Returns:
            The built context string
        """
        # For minimal context, bypass cache and build quickly
        if minimal:
            return self._build_minimal_context(node)
        
        # Check if caching is enabled
        if not self.enable_caching:
            return self._build_context_without_cache(node, max_context_length)
        
        # Check cache
        knowledge_checksum = self._compute_knowledge_checksum()
        cached_context = self._context_cache.get(
            node.task_id,
            node.layer,
            knowledge_checksum
        )
        
        if cached_context is not None:
            self._stats["cache_hits"] += 1
            logger.debug(f"Context cache hit for node {node.task_id}")
            return cached_context
        
        # Build context
        self._stats["cache_misses"] += 1
        self._stats["contexts_built"] += 1
        
        context = self._build_context_without_cache(node, max_context_length)
        
        # Cache the result
        self._context_cache.put(
            node.task_id,
            node.layer,
            knowledge_checksum,
            context
        )
        
        return context
    
    def _build_context_without_cache(self, node: Any, max_context_length: int) -> str:
        """Build context using the existing resolve_context_for_agent function."""
        # Use the existing context building function
        agent_input = resolve_context_for_agent(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=str(node.task_type),
            agent_name=node.agent_name if hasattr(node, 'agent_name') and node.agent_name else "DefaultAgent",
            knowledge_store=self.knowledge_store,
            overall_project_goal=node.overall_objective if hasattr(node, 'overall_objective') else None
        )
        
        # Convert AgentTaskInput to string context
        context_parts = []
        
        if agent_input.overall_project_goal:
            context_parts.append(f"Overall Objective: {agent_input.overall_project_goal}")
        
        context_parts.append(f"\nCurrent Task: {agent_input.current_goal}")
        
        if agent_input.relevant_context_items:
            context_parts.append("\nContext:")
            for item in agent_input.relevant_context_items:
                if hasattr(item, 'content_type_description') and item.content_type_description:
                    context_parts.append(f"- {item.content_type_description}: {item.content}")
                else:
                    context_parts.append(f"- {item.content}")
        
        return "\n".join(context_parts)
    
    def _build_minimal_context(self, node: Any) -> str:
        """Build minimal context for lightweight operations."""
        context_parts = []
        
        # Just the essential information
        context_parts.append(f"Current Task: {node.goal}")
        context_parts.append(f"Task Type: {node.task_type}")
        context_parts.append(f"Layer: {node.layer}")
        
        if node.overall_objective:
            context_parts.append(f"Overall Objective: {node.overall_objective}")
        
        return "\n".join(context_parts)
    
    def invalidate_cache_for_node(self, node_id: str):
        """Invalidate cache entries for a specific node."""
        if self.enable_caching:
            self._context_cache.invalidate_node(node_id)
    
    def clear_cache(self):
        """Clear the entire context cache."""
        if self.enable_caching:
            self._context_cache.clear()
            logger.info("Context cache cleared")
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        cache_stats = self._context_cache.get_stats() if self.enable_caching else {}
        
        return {
            "context_builder": {
                "contexts_built": self._stats["contexts_built"],
                "cache_enabled": self.enable_caching
            },
            "context_cache": cache_stats
        }
    
    def disable_caching(self):
        """Disable caching (useful for debugging)."""
        self.enable_caching = False
        self._context_cache.clear()
        logger.info("Context caching disabled")
    
    def enable_caching(self):
        """Re-enable caching."""
        self.enable_caching = True
        logger.info("Context caching enabled")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get context builder metrics for compatibility with SystemManager."""
        optimization_stats = self.get_optimization_stats()
        
        # Format metrics in expected structure
        metrics = {
            "contexts_built": self._stats["contexts_built"],
            "cache_hits": self._stats.get("cache_hits", 0),
            "cache_misses": self._stats.get("cache_misses", 0),
            "cache_enabled": self.enable_caching,
            "average_context_size": 0,  # Could be tracked if needed
            "cache_hit_rate": 0.0
        }
        
        # Calculate cache hit rate
        if "context_cache" in optimization_stats:
            cache_stats = optimization_stats["context_cache"]
            metrics["cache_hit_rate"] = cache_stats.get("hit_rate", 0.0)
        
        return metrics
    
    async def build_context(
        self,
        node: Any,
        context_type: str,
        knowledge_store: Optional[Any] = None,
        task_graph: Optional[Any] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Async wrapper for compatibility with v2 handlers.
        
        This method provides compatibility with the async interface expected
        by the v2 handlers while using our synchronous context building.
        """
        # Use our knowledge store if not provided
        if knowledge_store is None:
            knowledge_store = self.knowledge_store
        
        # Build context synchronously
        context_str = self.build_context_for_node(node, max_context_length=8000)
        
        # Convert to AgentTaskInput format expected by handlers
        from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import AgentTaskInput, ContextItem
        
        # Extract overall objective if available
        overall_objective = node.overall_objective if hasattr(node, 'overall_objective') else None
        
        # Create context items from the string context
        context_items = []
        if context_str and context_str != f"Current Task: {node.goal}\nTask Type: {node.task_type}\nLayer: {node.layer}":
            # If we have more than minimal context, wrap it as a context item
            context_items.append(ContextItem(
                source_task_id="context",
                source_task_goal="Context",
                content=context_str,
                content_type_description="full_context"
            ))
        
        # Create AgentTaskInput with correct field names
        agent_input = AgentTaskInput(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=str(node.task_type),
            overall_project_goal=overall_objective or node.goal,
            relevant_context_items=context_items,
            formatted_full_context=context_str  # Include full context as formatted string
        )
        
        return agent_input