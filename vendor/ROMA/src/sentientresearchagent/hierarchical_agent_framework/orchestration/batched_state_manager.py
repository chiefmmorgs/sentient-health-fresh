"""
BatchedStateManager - Optimized state management with batching and async I/O.

This manager batches multiple state updates to reduce I/O overhead and
improves performance through asynchronous operations.
"""

import asyncio
from typing import Dict, List, Optional, Set, Any, TYPE_CHECKING
from datetime import datetime
from loguru import logger
import json
import gzip
from collections import defaultdict

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
    from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph


class BatchedStateManager:
    """
    Manages state updates with batching for improved performance.
    
    Features:
    - Batches multiple updates to reduce I/O operations
    - Async write-through caching
    - State compression for large results
    - Bulk operations for knowledge store
    """
    
    def __init__(
        self,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"] = None,
        batch_size: int = 50,
        batch_timeout_ms: int = 100,
        enable_compression: bool = True,
        compression_threshold_bytes: int = 1024
    ):
        """
        Initialize the batched state manager.
        
        Args:
            knowledge_store: Knowledge store for persistence
            task_graph: Optional task graph reference
            batch_size: Maximum batch size before forcing flush
            batch_timeout_ms: Maximum time to wait before flushing
            enable_compression: Whether to compress large states
            compression_threshold_bytes: Minimum size for compression
        """
        self.knowledge_store = knowledge_store
        self.task_graph = task_graph
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms
        self.enable_compression = enable_compression
        self.compression_threshold_bytes = compression_threshold_bytes
        
        # Batching state
        self._pending_updates: Dict[str, TaskNode] = {}
        self._update_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._is_running = True
        
        # Statistics
        self._stats = {
            "total_updates": 0,
            "batched_updates": 0,
            "immediate_updates": 0,
            "compressions": 0,
            "bytes_saved": 0
        }
        
        logger.info(f"BatchedStateManager initialized with batch_size={batch_size}, "
                   f"timeout={batch_timeout_ms}ms, compression={enable_compression}")
    
    async def update_node_state(
        self, 
        node: TaskNode, 
        immediate: bool = False
    ) -> None:
        """
        Update node state with optional batching.
        
        Args:
            node: Node to update
            immediate: Force immediate update (bypass batching)
        """
        async with self._update_lock:
            self._stats["total_updates"] += 1
            
            if immediate or not self._is_running:
                # Immediate update
                await self._persist_node(node)
                self._stats["immediate_updates"] += 1
            else:
                # Add to batch
                self._pending_updates[node.task_id] = node
                self._stats["batched_updates"] += 1
                
                # Check if we should flush
                if len(self._pending_updates) >= self.batch_size:
                    await self._flush_batch()
                elif not self._flush_task or self._flush_task.done():
                    # Schedule a flush
                    self._flush_task = asyncio.create_task(
                        self._scheduled_flush()
                    )
    
    async def _scheduled_flush(self) -> None:
        """Flush batch after timeout."""
        await asyncio.sleep(self.batch_timeout_ms / 1000.0)
        async with self._update_lock:
            await self._flush_batch()
    
    async def _flush_batch(self) -> None:
        """Flush all pending updates."""
        if not self._pending_updates:
            return
        
        batch_size = len(self._pending_updates)
        logger.debug(f"Flushing batch of {batch_size} node updates")
        
        # Prepare batch updates
        nodes_to_update = list(self._pending_updates.values())
        self._pending_updates.clear()
        
        # Perform bulk update
        await self._bulk_persist_nodes(nodes_to_update)
        
        logger.debug(f"Batch flush completed for {batch_size} nodes")
    
    async def _persist_node(self, node: TaskNode) -> None:
        """Persist a single node with optional compression."""
        # Compress large results if enabled
        if self.enable_compression and node.result:
            compressed_result = await self._compress_if_needed(node.result)
            if compressed_result != node.result:
                # Store original and use compressed
                node.aux_data = node.aux_data or {}
                node.aux_data["original_result_size"] = len(str(node.result))
                node.aux_data["compressed"] = True
                node.result = compressed_result
        
        # Update knowledge store
        self.knowledge_store.add_or_update_record_from_node(node)
    
    async def _bulk_persist_nodes(self, nodes: List[TaskNode]) -> None:
        """Persist multiple nodes efficiently."""
        # Group nodes by status for efficient processing
        nodes_by_status = defaultdict(list)
        for node in nodes:
            nodes_by_status[node.status].append(node)
        
        # Process each group
        tasks = []
        for status, status_nodes in nodes_by_status.items():
            # Create async task for each group
            task = asyncio.create_task(
                self._persist_node_group(status_nodes)
            )
            tasks.append(task)
        
        # Wait for all groups to complete
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _persist_node_group(self, nodes: List[TaskNode]) -> None:
        """Persist a group of nodes with the same status."""
        # Compress results if needed
        compression_tasks = []
        for node in nodes:
            if self.enable_compression and node.result:
                task = asyncio.create_task(
                    self._compress_node_result(node)
                )
                compression_tasks.append(task)
        
        if compression_tasks:
            await asyncio.gather(*compression_tasks, return_exceptions=True)
        
        # Batch update knowledge store
        for node in nodes:
            self.knowledge_store.add_or_update_record_from_node(node)
    
    async def _compress_node_result(self, node: TaskNode) -> None:
        """Compress node result if it's large enough."""
        result_str = str(node.result)
        if len(result_str) >= self.compression_threshold_bytes:
            compressed = await self._compress_data(result_str)
            if len(compressed) < len(result_str):
                # Compression was beneficial
                node.aux_data = node.aux_data or {}
                node.aux_data["original_result_size"] = len(result_str)
                node.aux_data["compressed_result_size"] = len(compressed)
                node.aux_data["compressed"] = True
                node.aux_data["compression_ratio"] = len(compressed) / len(result_str)
                
                self._stats["compressions"] += 1
                self._stats["bytes_saved"] += len(result_str) - len(compressed)
                
                # Store compressed result as base64
                import base64
                node.result = {
                    "_compressed": True,
                    "data": base64.b64encode(compressed).decode('utf-8'),
                    "original_size": len(result_str)
                }
    
    async def _compress_if_needed(self, data: Any) -> Any:
        """Compress data if it's large enough."""
        data_str = json.dumps(data) if not isinstance(data, str) else data
        
        if len(data_str) < self.compression_threshold_bytes:
            return data
        
        compressed = await self._compress_data(data_str)
        if len(compressed) < len(data_str):
            import base64
            return {
                "_compressed": True,
                "data": base64.b64encode(compressed).decode('utf-8'),
                "original_size": len(data_str)
            }
        
        return data
    
    async def _compress_data(self, data: str) -> bytes:
        """Compress string data using gzip."""
        return await asyncio.to_thread(
            gzip.compress,
            data.encode('utf-8'),
            compresslevel=6  # Balanced compression
        )
    
    async def flush_all(self) -> None:
        """Force flush all pending updates."""
        async with self._update_lock:
            await self._flush_batch()
    
    async def close(self) -> None:
        """Close the manager and flush remaining updates."""
        self._is_running = False
        await self.flush_all()
        
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"BatchedStateManager closed. Stats: {self._stats}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get manager statistics."""
        return self._stats.copy()
    
    async def get_nodes_by_status(
        self, 
        status: TaskStatus,
        include_pending: bool = True
    ) -> List[TaskNode]:
        """
        Get nodes by status, including pending updates.
        
        Args:
            status: Status to filter by
            include_pending: Include nodes in pending batch
            
        Returns:
            List of nodes with the specified status
        """
        nodes = []
        
        # Get from task graph if available
        if self.task_graph:
            all_nodes = self.task_graph.get_all_nodes()
            nodes.extend([n for n in all_nodes if n.status == status])
        
        # Include pending updates
        if include_pending:
            async with self._update_lock:
                pending_nodes = [
                    n for n in self._pending_updates.values() 
                    if n.status == status
                ]
                # Merge, avoiding duplicates
                existing_ids = {n.task_id for n in nodes}
                nodes.extend([n for n in pending_nodes if n.task_id not in existing_ids])
        
        return nodes