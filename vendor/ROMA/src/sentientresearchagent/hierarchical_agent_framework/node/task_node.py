import uuid
import threading
from typing import Optional, Any, List, Dict, Union, Callable, TYPE_CHECKING
from pydantic import BaseModel, Field
from datetime import datetime
from loguru import logger
from enum import Enum

from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import ReplanRequestDetails
# Import from our consolidated types module
from sentientresearchagent.hierarchical_agent_framework.types import (
    TaskStatus, NodeType, TaskType, safe_task_status
)
from sentientresearchagent.exceptions import InvalidTaskStateError, TaskError

if TYPE_CHECKING:
    from ...core.system_manager import SystemManager

class TaskNode(BaseModel):
    """Represents a single task unit in the hierarchy."""
    goal: str
    task_type: TaskType
    node_type: NodeType  # Initial type, might be changed by atomizer

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    layer: int = 0 # Can be used as planning_depth
    parent_node_id: Optional[str] = None
    overall_objective: Optional[str] = None # The ultimate high-level goal of the entire operation

    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None # Will store Pydantic models, text, or multi-modal references
    output_summary: Optional[str] = None # Concise summary of the result for context building
    error: Optional[str] = None
    
    agent_name: Optional[str] = None # NEW: Name/type of the agent handling this task

    # For PLAN nodes, to link to the graph of their sub-tasks
    sub_graph_id: Optional[str] = None
    
    # For tracking and context building
    input_payload_dict: Optional[Dict[str, Any]] = None # What was given to the agent
    output_type_description: Optional[str] = None # e.g., "text_summary", "plan_output", "image_reference"
    timestamp_created: datetime = Field(default_factory=datetime.now)
    timestamp_updated: datetime = Field(default_factory=datetime.now)
    timestamp_completed: Optional[datetime] = None

    # For PLAN nodes to know their direct children
    # This helps in dependency management and aggregation
    planned_sub_task_ids: List[str] = Field(default_factory=list)

    # NEW: For replanning context
    replan_details: Optional[ReplanRequestDetails] = None 
    replan_reason: Optional[str] = None 
    replan_attempts: int = 0
    
    # NEW: To store arbitrary auxiliary data that might be useful for certain handlers or agents
    # For example, storing the original plan and user modification instructions during HITL replan
    aux_data: Dict[str, Any] = Field(default_factory=dict)
    
    # We'll add the lock via __init__ without declaring it as a field

    class Config:
        # Remove use_enum_values to keep enums as enum objects, not strings
        # use_enum_values = True # This was causing enums to be stored as strings!
        arbitrary_types_allowed = True  # Allow non-pydantic types like threading.RLock

    def __init__(self, **data):
        # Ensure aux_data is never None - fix for deserialization issues
        if 'aux_data' not in data or data['aux_data'] is None:
            data['aux_data'] = {}
        
        super().__init__(**data)
        # Initialize the lock after the object is created
        object.__setattr__(self, '_status_lock', threading.RLock())

    def update_status(self, new_status: TaskStatus, result: Any = None, 
                     error_msg: Optional[str] = None, result_summary: Optional[str] = None,
                     validate_transition: bool = True, update_manager: Any = None):
        """
        Update the task status with better error handling and validation.
        
        Args:
            new_status: New status to set (can be string or TaskStatus enum)
            result: Optional result data
            error_msg: Optional error message (will set status to FAILED if provided)
            result_summary: Optional summary of the result
            validate_transition: Whether to validate status transitions
            update_manager: Optional NodeUpdateManager for optimized updates
        """
        # Ensure we have a lock (in case of deserialized objects)
        if not hasattr(self, '_status_lock') or self._status_lock is None:
            object.__setattr__(self, '_status_lock', threading.RLock())
        
        with self._status_lock:
            old_status = self.status
            
            try:
                # Use safe conversion to handle string inputs
                new_status_enum = safe_task_status(new_status) if not isinstance(new_status, TaskStatus) else new_status
                
                # Validate transition if requested
                if validate_transition and not self._is_valid_transition(old_status, new_status_enum):
                    # Log warning but don't fail - just warn about potentially invalid transition
                    logger.warning(f"Task {self.task_id}: Potentially invalid status transition {old_status} → {new_status_enum}")
                    # Don't raise exception - just log the warning and proceed
                
                # Enhanced logging for state transitions
                transition_time = datetime.now()
                logger.info(f"🔄 STATE TRANSITION [{transition_time.strftime('%H:%M:%S.%f')[:-3]}] "
                           f"Node: {self.task_id} | {old_status} → {new_status_enum} | "
                           f"Layer: {self.layer} | Goal: '{self.goal[:50]}...'")
                
                self.status = new_status_enum
                self.timestamp_updated = transition_time
                
                if result is not None:
                    self.result = result
                    
                if result_summary is not None:
                    self.output_summary = result_summary
                    
                if error_msg is not None:
                    self.error = error_msg
                    self.status = TaskStatus.FAILED # Ensure status is FAILED if error is provided
                
                if self.status in [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.NEEDS_REPLAN, TaskStatus.CANCELLED]:
                    self.timestamp_completed = datetime.now()
                    
                    # IMMEDIATE AGGREGATION TRIGGER: If this node just completed and has a parent,
                    # notify the system to check if parent can aggregate immediately
                    if self.status == TaskStatus.DONE and self.parent_node_id:
                        # Store a hint for immediate parent aggregation check
                        # This will be picked up by the execution engine to trigger immediate cycle
                        if not hasattr(self, 'aux_data') or self.aux_data is None:
                            self.aux_data = {}
                        self.aux_data['trigger_parent_aggregation_check'] = {
                            'parent_id': self.parent_node_id,
                            'completion_time': datetime.now().isoformat(),
                            'child_id': self.task_id
                        }
                        logger.info(f"🚀 IMMEDIATE AGGREGATION TRIGGER: Node {self.task_id} completion may allow parent {self.parent_node_id} to aggregate")
                
                # Comprehensive logging for state transitions
                transition_time = datetime.now()
                logger.info(f"🔄 STATE TRANSITION [{transition_time.strftime('%H:%M:%S.%f')[:-3]}] "
                           f"Task {self.task_id} (layer {self.layer}): {old_status.name} → {self.status.name} "
                           f"| Goal: '{self.goal[:40]}...' "
                           f"| Result: {str(result)[:50] if result else 'None'}... "
                           f"| Error: {error_msg[:50] if error_msg else 'None'}")
                
                # Handle update through update_manager if provided
                if update_manager is not None:
                    import asyncio
                    # Create update data
                    update_data = {
                        "old_status": old_status,
                        "new_status": new_status_enum,
                        "timestamp": transition_time,
                        "result": result,
                        "error": error_msg,
                        "result_summary": result_summary
                    }
                    # Run async update in sync context
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Schedule as a task if loop is already running
                            asyncio.create_task(
                                update_manager.update_node_state(self, "status", update_data)
                            )
                        else:
                            # Run directly if no loop is running
                            loop.run_until_complete(
                                update_manager.update_node_state(self, "status", update_data)
                            )
                    except RuntimeError:
                        # If no event loop, create one
                        asyncio.run(
                            update_manager.update_node_state(self, "status", update_data)
                        )
                       
            except Exception as e:
                logger.error(f"Failed to update status for task {self.task_id}: {e}")
                # Don't re-raise here to avoid cascading failures
                # Just log the error and keep the old status
    
    def update_status_fast(self, new_status: TaskStatus, update_manager: Any = None):
        """
        Fast path status update for deferred execution mode.
        
        This method bypasses validation and logging for maximum performance.
        Only use when execution_strategy is "deferred".
        
        Args:
            new_status: New status to set
            update_manager: NodeUpdateManager configured for deferred updates
        """
        if update_manager is None or getattr(update_manager, 'execution_strategy', None) != 'deferred':
            # Fall back to regular update if not in deferred mode
            self.update_status(new_status, update_manager=update_manager)
            return
        
        # Fast path - minimal operations only
        old_status = self.status
        self.status = new_status if isinstance(new_status, TaskStatus) else safe_task_status(new_status)
        self.timestamp_updated = datetime.now()
        
        # Mark completion time for terminal states
        if self.status in [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            self.timestamp_completed = datetime.now()
        
        # Queue the update without any blocking operations
        import asyncio
        update_data = {
            "old_status": old_status,
            "new_status": self.status,
            "timestamp": self.timestamp_updated,
            "fast_path": True
        }
        
        # Fire and forget - no waiting
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    update_manager.update_node_state(self, "status", update_data)
                )
        except RuntimeError:
            # No event loop - this is fine for deferred mode
            pass
    
    def _is_valid_transition(self, from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """
        Check if a status transition is valid.
        
        Args:
            from_status: Current status
            to_status: Desired new status
            
        Returns:
            True if transition is valid, False otherwise
        """
        # Define valid transitions (more flexible than before)
        valid_transitions = {
            TaskStatus.PENDING: [TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED],
            TaskStatus.READY: [TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED],
            TaskStatus.RUNNING: [TaskStatus.DONE, TaskStatus.PLAN_DONE, TaskStatus.FAILED, TaskStatus.NEEDS_REPLAN, TaskStatus.CANCELLED],
            TaskStatus.PLAN_DONE: [TaskStatus.AGGREGATING, TaskStatus.FAILED, TaskStatus.NEEDS_REPLAN],
            TaskStatus.AGGREGATING: [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.NEEDS_REPLAN],
            TaskStatus.NEEDS_REPLAN: [TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED],  # More flexible
            # Terminal states
            TaskStatus.DONE: [TaskStatus.NEEDS_REPLAN],  # Allow retry
            TaskStatus.FAILED: [TaskStatus.NEEDS_REPLAN, TaskStatus.READY],  # Allow retry
            TaskStatus.CANCELLED: []
        }
        
        return to_status in valid_transitions.get(from_status, [])
    
    def fail_with_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """
        Mark task as failed with detailed error information.
        
        Args:
            error: The exception that caused the failure
            context: Additional context information
        """
        error_message = str(error)
        if context:
            error_message += f" (Context: {context})"
            
        self.update_status(
            TaskStatus.FAILED, 
            error_msg=error_message,
            validate_transition=False  # Don't validate when handling errors
        )
        
        # Store additional error context in aux_data
        if context:
            self.aux_data.setdefault("error_context", {}).update(context)
            
        logger.error(f"Task {self.task_id} failed: {error_message}")

    def __repr__(self):
        return (f"TaskNode(id={self.task_id}, goal='{self.goal[:30]}...', "
                f"type={self.task_type}/{self.node_type}, "
                f"status={self.status}, layer={self.layer})")
