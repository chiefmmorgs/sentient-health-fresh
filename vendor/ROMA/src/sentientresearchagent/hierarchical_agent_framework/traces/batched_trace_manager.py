"""
BatchedTraceManager - Optimized trace manager with batching and async I/O.

This implementation adds:
- Batch trace operations to reduce I/O
- Async file writes
- Conditional tracing based on agent type
- Memory-efficient trace storage
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from datetime import datetime
import threading
from collections import deque
from loguru import logger

from ..tracing.manager import TraceManager


class TraceWriteBuffer:
    """Buffer for batching trace write operations."""
    
    def __init__(self, max_size: int = 100, flush_interval_ms: int = 5000):
        self.max_size = max_size
        self.flush_interval_ms = flush_interval_ms
        self.buffer: deque = deque(maxlen=max_size)
        self.last_flush = time.time() * 1000
        self._lock = threading.Lock()
        self._flush_task = None
    
    def add(self, trace_data: Dict[str, Any]):
        """Add trace data to buffer."""
        with self._lock:
            self.buffer.append({
                "timestamp": datetime.now().isoformat(),
                "data": trace_data
            })
    
    def should_flush(self) -> bool:
        """Check if buffer should be flushed."""
        current_time = time.time() * 1000
        time_elapsed = current_time - self.last_flush
        
        return (
            len(self.buffer) >= self.max_size or
            (len(self.buffer) > 0 and time_elapsed >= self.flush_interval_ms)
        )
    
    def get_and_clear(self) -> List[Dict[str, Any]]:
        """Get all buffered data and clear buffer."""
        with self._lock:
            data = list(self.buffer)
            self.buffer.clear()
            self.last_flush = time.time() * 1000
            return data


class BatchedTraceManager(TraceManager):
    """
    Performance-optimized TraceManager with batching and async I/O.
    
    Features:
    - Batch trace writes to reduce I/O operations
    - Async file operations for non-blocking writes
    - Conditional tracing based on configuration
    - Memory-efficient trace storage
    """
    
    def __init__(
        self,
        project_id: str,
        trace_dir: Optional[Path] = None,
        enable_batching: bool = True,
        batch_size: int = 100,
        flush_interval_ms: int = 5000,
        enable_tracing: bool = True,
        trace_lightweight: bool = False
    ):
        """
        Initialize BatchedTraceManager.
        
        Args:
            project_id: Project identifier
            trace_dir: Directory for trace files
            enable_batching: Whether to enable batch writes
            batch_size: Maximum batch size before flush
            flush_interval_ms: Maximum time between flushes
            enable_tracing: Whether tracing is enabled at all
            trace_lightweight: Whether to trace lightweight operations
        """
        super().__init__(project_id, trace_dir)
        
        # Batching settings
        self.enable_batching = enable_batching
        self.enable_tracing = enable_tracing
        self.trace_lightweight = trace_lightweight
        
        # Write buffer
        self._write_buffer = TraceWriteBuffer(
            max_size=batch_size,
            flush_interval_ms=flush_interval_ms
        )
        
        # Background flush task
        self._flush_task = None
        self._shutdown = False
        
        # Statistics
        self._stats = {
            "traces_recorded": 0,
            "batches_written": 0,
            "traces_skipped": 0
        }
        
        # Start background flusher if batching enabled
        if enable_batching and enable_tracing:
            self._start_background_flusher()
    
    def _start_background_flusher(self):
        """Start background task for periodic flushing."""
        async def periodic_flush():
            while not self._shutdown:
                if self._write_buffer.should_flush():
                    await self._flush_buffer()
                await asyncio.sleep(1)  # Check every second
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._flush_task = asyncio.create_task(periodic_flush())
            else:
                # Create new event loop in thread
                import threading
                def run_flusher():
                    asyncio.run(periodic_flush())
                
                flush_thread = threading.Thread(target=run_flusher, daemon=True)
                flush_thread.start()
        except RuntimeError:
            logger.warning("Could not start background trace flusher")
    
    def add_trace(
        self,
        node_id: str,
        event_type: str,
        data: Dict[str, Any],
        execution_strategy: Optional[str] = None
    ) -> str:
        """
        Add a trace event with batching support.
        
        Args:
            node_id: Node identifier
            event_type: Type of event
            data: Event data
            execution_strategy: Current execution strategy
        
        Returns:
            Trace ID
        """
        # Check if tracing is enabled
        if not self.enable_tracing:
            self._stats["traces_skipped"] += 1
            return f"skipped_{node_id}_{event_type}"
        
        # Skip lightweight traces if configured
        if not self.trace_lightweight and execution_strategy == "deferred":
            self._stats["traces_skipped"] += 1
            return f"skipped_{node_id}_{event_type}"
        
        # Create trace entry
        trace_id = f"{node_id}_{event_type}_{int(time.time() * 1000)}"
        trace_entry = {
            "trace_id": trace_id,
            "node_id": node_id,
            "event_type": event_type,
            "data": data,
            "execution_strategy": execution_strategy
        }
        
        self._stats["traces_recorded"] += 1
        
        # Add to buffer or write immediately
        if self.enable_batching:
            self._write_buffer.add(trace_entry)
            
            # Check if we need immediate flush
            if self._write_buffer.should_flush():
                # Run flush asynchronously
                asyncio.create_task(self._flush_buffer())
        else:
            # Write immediately (fallback to parent implementation)
            super().add_trace(node_id, event_type, data)
        
        return trace_id
    
    async def _flush_buffer(self):
        """Flush write buffer to disk."""
        traces = self._write_buffer.get_and_clear()
        
        if not traces:
            return
        
        try:
            # Write batch to file
            batch_file = self.trace_dir / f"batch_{int(time.time() * 1000)}.json"
            
            # Async file write
            await self._async_write_json(batch_file, {
                "project_id": self.project_id,
                "batch_size": len(traces),
                "traces": traces
            })
            
            self._stats["batches_written"] += 1
            logger.debug(f"Flushed {len(traces)} traces to {batch_file}")
            
        except Exception as e:
            logger.error(f"Failed to flush trace buffer: {e}")
    
    async def _async_write_json(self, file_path: Path, data: Dict[str, Any]):
        """Write JSON data asynchronously."""
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: file_path.write_text(json.dumps(data, indent=2))
        )
    
    def flush(self):
        """Force flush of pending traces."""
        if self.enable_batching and self.enable_tracing:
            # Run flush synchronously
            asyncio.run(self._flush_buffer())
    
    def shutdown(self):
        """Shutdown trace manager and flush pending traces."""
        self._shutdown = True
        
        # Final flush
        self.flush()
        
        # Cancel background task
        if self._flush_task:
            self._flush_task.cancel()
        
        logger.info(f"BatchedTraceManager shutdown - {self._stats['traces_recorded']} traces recorded")
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        return {
            "trace_manager": {
                "traces_recorded": self._stats["traces_recorded"],
                "traces_skipped": self._stats["traces_skipped"],
                "batches_written": self._stats["batches_written"],
                "batching_enabled": self.enable_batching,
                "tracing_enabled": self.enable_tracing,
                "buffer_size": len(self._write_buffer.buffer)
            }
        }
    
    def disable_tracing(self):
        """Disable all tracing."""
        self.enable_tracing = False
        self.flush()  # Flush any pending traces
        logger.info("Tracing disabled")
    
    def enable_tracing(self):
        """Re-enable tracing."""
        self.enable_tracing = True
        logger.info("Tracing enabled")