"""
LazyHandlerContext - Optimized handler context with lazy initialization.

This implementation reduces overhead by:
- Lazy property initialization
- Copy-on-write for mutable data
- Minimal object creation
- Cached property access
"""

from typing import Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from functools import cached_property
from loguru import logger

if TYPE_CHECKING:
    from ...core.system_manager import SystemManager
    from ..graph.task_graph import TaskGraph
    from ..node.task_node import TaskNode
    from ..context.knowledge_store import KnowledgeStore
    from ..context.context_builder import ContextBuilder
    from ..services.broadcast_service import BroadcastService
    from ..traces.trace_manager import TraceManager


@dataclass
class LazyHandlerContext:
    """
    Lazy-loading handler context to reduce initialization overhead.
    
    Properties are only computed when accessed, reducing the cost
    of creating contexts that may not use all properties.
    """
    
    # Core references (lightweight)
    system_manager: 'SystemManager'
    graph: 'TaskGraph'
    node: 'TaskNode'
    
    # Optional heavyweight references
    _knowledge_store: Optional['KnowledgeStore'] = field(default=None, init=False)
    _context_builder: Optional['ContextBuilder'] = field(default=None, init=False)
    _broadcast_service: Optional['BroadcastService'] = field(default=None, init=False)
    _trace_manager: Optional['TraceManager'] = field(default=None, init=False)
    
    # Cached data
    _context_cache: Optional[str] = field(default=None, init=False)
    _metadata_cache: Optional[Dict[str, Any]] = field(default=None, init=False)
    
    # Flags
    skip_expensive_operations: bool = False
    minimal_context: bool = False
    
    @property
    def knowledge_store(self) -> 'KnowledgeStore':
        """Lazy-load knowledge store."""
        if self._knowledge_store is None:
            self._knowledge_store = self.system_manager.get_component('knowledge_store')
        return self._knowledge_store
    
    @property
    def context_builder(self) -> 'ContextBuilder':
        """Lazy-load context builder."""
        if self._context_builder is None:
            self._context_builder = self.system_manager.get_component('context_builder')
        return self._context_builder
    
    @property
    def broadcast_service(self) -> Optional['BroadcastService']:
        """Lazy-load broadcast service."""
        if self._broadcast_service is None and not self.skip_expensive_operations:
            self._broadcast_service = self.system_manager.get_component('broadcast_service')
        return self._broadcast_service
    
    @property
    def trace_manager(self) -> Optional['TraceManager']:
        """Lazy-load trace manager."""
        if self._trace_manager is None and not self.skip_expensive_operations:
            self._trace_manager = self.system_manager.get_component('trace_manager')
        return self._trace_manager
    
    @cached_property
    def node_context(self) -> str:
        """Build and cache node context."""
        if self._context_cache is not None:
            return self._context_cache
        
        if self.minimal_context:
            # Build minimal context inline
            self._context_cache = f"Task: {self.node.goal}\nType: {self.node.task_type}"
        else:
            # Use context builder
            self._context_cache = self.context_builder.build_context_for_node(
                self.node,
                minimal=self.minimal_context
            )
        
        return self._context_cache
    
    @cached_property
    def metadata(self) -> Dict[str, Any]:
        """Build and cache metadata."""
        if self._metadata_cache is not None:
            return self._metadata_cache
        
        self._metadata_cache = {
            "node_id": self.node.task_id,
            "layer": self.node.layer,
            "task_type": str(self.node.task_type),
            "node_type": str(self.node.node_type),
            "parent_id": self.node.parent_node_id,
            "status": str(self.node.status)
        }
        
        return self._metadata_cache
    
    def copy_for_child(self, child_node: 'TaskNode') -> 'LazyHandlerContext':
        """
        Create a lightweight copy for a child node.
        
        This avoids deep copying and reuses immutable references.
        """
        child_context = LazyHandlerContext(
            system_manager=self.system_manager,  # Reuse reference
            graph=self.graph,  # Reuse reference
            node=child_node,  # New node
            skip_expensive_operations=self.skip_expensive_operations,
            minimal_context=self.minimal_context
        )
        
        # Share cached components if already loaded
        if self._knowledge_store is not None:
            child_context._knowledge_store = self._knowledge_store
        if self._context_builder is not None:
            child_context._context_builder = self._context_builder
        
        return child_context
    
    def invalidate_caches(self):
        """Invalidate cached properties."""
        self._context_cache = None
        self._metadata_cache = None
        
        # Clear cached_property caches
        if 'node_context' in self.__dict__:
            del self.__dict__['node_context']
        if 'metadata' in self.__dict__:
            del self.__dict__['metadata']
    
    @classmethod
    def create_minimal(
        cls,
        system_manager: 'SystemManager',
        graph: 'TaskGraph',
        node: 'TaskNode'
    ) -> 'LazyHandlerContext':
        """Create a minimal context for lightweight operations."""
        return cls(
            system_manager=system_manager,
            graph=graph,
            node=node,
            skip_expensive_operations=True,
            minimal_context=True
        )
    
    @classmethod
    def from_handler_context(cls, ctx: Any) -> 'LazyHandlerContext':
        """Convert from regular HandlerContext to LazyHandlerContext."""
        lazy_ctx = cls(
            system_manager=ctx.system_manager,
            graph=ctx.graph,
            node=ctx.node
        )
        
        # Pre-populate if already available in source context
        if hasattr(ctx, 'knowledge_store'):
            lazy_ctx._knowledge_store = ctx.knowledge_store
        if hasattr(ctx, 'context_builder'):
            lazy_ctx._context_builder = ctx.context_builder
        if hasattr(ctx, 'broadcast_service'):
            lazy_ctx._broadcast_service = ctx.broadcast_service
        if hasattr(ctx, 'trace_manager'):
            lazy_ctx._trace_manager = ctx.trace_manager
        
        return lazy_ctx
    
    def __repr__(self) -> str:
        """Lightweight representation."""
        return (
            f"LazyHandlerContext("
            f"node={self.node.task_id}, "
            f"minimal={self.minimal_context}, "
            f"skip_expensive={self.skip_expensive_operations})"
        )