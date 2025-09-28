"""
OptimizedBroadcastService - Enhanced WebSocket communication with batching and queuing.

This service improves WebSocket performance through:
- Message batching to reduce network overhead
- Async message queuing
- Differential updates to minimize data transfer
- Client-side throttling support
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Set, TYPE_CHECKING
from datetime import datetime
from collections import defaultdict, deque
from loguru import logger
import hashlib

if TYPE_CHECKING:
    from socketio import AsyncServer


class MessageBatch:
    """Container for batched messages."""
    
    def __init__(self, max_size: int = 100, max_age_ms: int = 50):
        self.messages: List[Dict[str, Any]] = []
        self.created_at = time.time()
        self.max_size = max_size
        self.max_age_ms = max_age_ms
    
    def add(self, message: Dict[str, Any]) -> bool:
        """Add message to batch. Returns True if batch is full."""
        self.messages.append(message)
        return len(self.messages) >= self.max_size
    
    def is_expired(self) -> bool:
        """Check if batch has exceeded max age."""
        age_ms = (time.time() - self.created_at) * 1000
        return age_ms >= self.max_age_ms
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert batch to payload."""
        return {
            "type": "batch",
            "messages": self.messages,
            "count": len(self.messages),
            "timestamp": datetime.now().isoformat()
        }


class OptimizedBroadcastService:
    """
    Optimized WebSocket broadcast service with batching and differential updates.
    """
    
    def __init__(
        self,
        socketio: Optional["AsyncServer"] = None,
        batch_size: int = 50,
        batch_timeout_ms: int = 100,
        enable_compression: bool = True,
        enable_diff_updates: bool = True,
        max_queue_size: int = 1000
    ):
        """
        Initialize the optimized broadcast service.
        
        Args:
            socketio: SocketIO server instance
            batch_size: Maximum messages per batch
            batch_timeout_ms: Maximum time to wait before sending batch
            enable_compression: Enable message compression
            enable_diff_updates: Enable differential updates
            max_queue_size: Maximum queue size per client
        """
        self.socketio = socketio
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms
        self.enable_compression = enable_compression
        self.enable_diff_updates = enable_diff_updates
        self.max_queue_size = max_queue_size
        
        # Message queues per room
        self._message_queues: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_queue_size))
        self._active_batches: Dict[str, MessageBatch] = {}
        self._batch_tasks: Dict[str, asyncio.Task] = {}
        
        # State tracking for differential updates
        self._last_states: Dict[str, Dict[str, Any]] = {}
        self._state_hashes: Dict[str, str] = {}
        
        # Statistics
        self._stats = {
            "messages_sent": 0,
            "batches_sent": 0,
            "bytes_sent": 0,
            "diff_updates": 0,
            "full_updates": 0,
            "compression_ratio": 0.0
        }
        
        # Locks
        self._queue_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        logger.info(f"OptimizedBroadcastService initialized with batch_size={batch_size}, "
                   f"timeout={batch_timeout_ms}ms, compression={enable_compression}")
    
    async def emit(
        self,
        event: str,
        data: Any,
        room: Optional[str] = None,
        priority: int = 0,
        force_immediate: bool = False
    ) -> None:
        """
        Emit a message with optional batching.
        
        Args:
            event: Event name
            data: Event data
            room: Optional room to broadcast to
            priority: Message priority (higher = more important)
            force_immediate: Force immediate sending (bypass batching)
        """
        if not self.socketio:
            return
        
        message = {
            "event": event,
            "data": data,
            "timestamp": time.time(),
            "priority": priority
        }
        
        if force_immediate:
            # Send immediately
            await self._send_immediate(event, data, room)
            self._stats["messages_sent"] += 1
        else:
            # Add to queue for batching
            queue_key = room or "_global"
            async with self._queue_locks[queue_key]:
                await self._queue_message(queue_key, message)
    
    async def _queue_message(self, queue_key: str, message: Dict[str, Any]) -> None:
        """Queue a message for batching."""
        # Add to current batch or create new one
        if queue_key not in self._active_batches:
            self._active_batches[queue_key] = MessageBatch(
                max_size=self.batch_size,
                max_age_ms=self.batch_timeout_ms
            )
            # Schedule batch flush
            self._batch_tasks[queue_key] = asyncio.create_task(
                self._scheduled_flush(queue_key)
            )
        
        batch = self._active_batches[queue_key]
        is_full = batch.add(message)
        
        if is_full:
            # Flush immediately if batch is full
            await self._flush_batch(queue_key)
    
    async def _scheduled_flush(self, queue_key: str) -> None:
        """Flush batch after timeout."""
        await asyncio.sleep(self.batch_timeout_ms / 1000.0)
        async with self._queue_locks[queue_key]:
            await self._flush_batch(queue_key)
    
    async def _flush_batch(self, queue_key: str) -> None:
        """Flush a batch of messages."""
        if queue_key not in self._active_batches:
            return
        
        batch = self._active_batches.pop(queue_key)
        if not batch.messages:
            return
        
        # Cancel scheduled task if exists
        if queue_key in self._batch_tasks:
            task = self._batch_tasks.pop(queue_key)
            if not task.done():
                task.cancel()
        
        # Process differential updates if enabled
        if self.enable_diff_updates:
            await self._process_diff_updates(queue_key, batch)
        
        # Send batch
        payload = batch.to_payload()
        
        # Compress if enabled
        if self.enable_compression:
            payload = await self._compress_payload(payload)
        
        # Send to appropriate destination
        room = queue_key if queue_key != "_global" else None
        await self._send_immediate("batch_update", payload, room)
        
        self._stats["batches_sent"] += 1
        self._stats["messages_sent"] += len(batch.messages)
        
        logger.debug(f"Flushed batch for {queue_key}: {len(batch.messages)} messages")
    
    async def _process_diff_updates(self, queue_key: str, batch: MessageBatch) -> None:
        """Process messages for differential updates."""
        # Group messages by type for efficient diffing
        messages_by_type = defaultdict(list)
        for msg in batch.messages:
            msg_type = msg.get("event", "unknown")
            messages_by_type[msg_type].append(msg)
        
        # Apply differential updates for state-based messages
        for msg_type, messages in messages_by_type.items():
            if msg_type in ["node_update", "graph_update", "state_update"]:
                # Process as differential updates
                for i, msg in enumerate(messages):
                    diff_msg = await self._create_diff_update(queue_key, msg_type, msg)
                    if diff_msg:
                        messages[i] = diff_msg
                        self._stats["diff_updates"] += 1
                    else:
                        self._stats["full_updates"] += 1
    
    async def _create_diff_update(
        self, 
        queue_key: str, 
        msg_type: str, 
        message: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a differential update if possible."""
        state_key = f"{queue_key}:{msg_type}"
        current_data = message.get("data", {})
        
        # Calculate hash of current state
        current_hash = self._calculate_hash(current_data)
        
        # Check if state has changed
        if state_key in self._state_hashes:
            if self._state_hashes[state_key] == current_hash:
                # No change - skip update
                return None
            
            # Calculate diff
            last_state = self._last_states.get(state_key, {})
            diff = self._calculate_diff(last_state, current_data)
            
            if diff and len(json.dumps(diff)) < len(json.dumps(current_data)) * 0.7:
                # Diff is beneficial (at least 30% smaller)
                message["data"] = diff
                message["is_diff"] = True
                message["base_hash"] = self._state_hashes[state_key]
        
        # Update state tracking
        self._last_states[state_key] = current_data
        self._state_hashes[state_key] = current_hash
        
        return message
    
    def _calculate_hash(self, data: Any) -> str:
        """Calculate hash of data for comparison."""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def _calculate_diff(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate difference between two states."""
        diff = {"_type": "diff"}
        
        # Find added/modified fields
        for key, value in new_data.items():
            if key not in old_data:
                diff[f"+{key}"] = value
            elif old_data[key] != value:
                diff[f"~{key}"] = value
        
        # Find removed fields
        for key in old_data:
            if key not in new_data:
                diff[f"-{key}"] = None
        
        return diff if len(diff) > 1 else None
    
    async def _compress_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Compress payload if beneficial."""
        import gzip
        import base64
        
        original = json.dumps(payload)
        compressed = await asyncio.to_thread(
            gzip.compress,
            original.encode('utf-8'),
            compresslevel=6
        )
        
        if len(compressed) < len(original) * 0.8:  # At least 20% compression
            self._stats["compression_ratio"] = len(compressed) / len(original)
            return {
                "_compressed": True,
                "data": base64.b64encode(compressed).decode('utf-8'),
                "original_size": len(original)
            }
        
        return payload
    
    async def _send_immediate(self, event: str, data: Any, room: Optional[str] = None) -> None:
        """Send a message immediately without batching."""
        if not self.socketio:
            return
        
        try:
            if room:
                await self.socketio.emit(event, data, room=room)
            else:
                await self.socketio.emit(event, data)
                
            # Track bytes sent (approximate)
            self._stats["bytes_sent"] += len(json.dumps(data))
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
    
    async def broadcast_to_project(
        self, 
        project_id: str, 
        event: str, 
        data: Any,
        priority: int = 0
    ) -> None:
        """Broadcast to all clients in a project room."""
        await self.emit(event, data, room=f"project_{project_id}", priority=priority)
    
    async def flush_all(self) -> None:
        """Force flush all pending batches."""
        queue_keys = list(self._active_batches.keys())
        for queue_key in queue_keys:
            async with self._queue_locks[queue_key]:
                await self._flush_batch(queue_key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get broadcast statistics."""
        return self._stats.copy()
    
    async def close(self) -> None:
        """Close the service and flush remaining messages."""
        # Flush all pending batches
        await self.flush_all()
        
        # Cancel all scheduled tasks
        for task in self._batch_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        logger.info(f"OptimizedBroadcastService closed. Stats: {self._stats}")