"""
Consolidated type definitions for the Sentient Research Agent framework.

This module serves as the single source of truth for all enums and type definitions,
preventing enum/string conversion issues throughout the codebase.
"""

from enum import Enum
from typing import Literal, Union

# Core Status and Type Enums (using string values for better serialization)

class TaskStatus(str, Enum):
    """Status of a task node in the execution graph."""
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    PLAN_DONE = "PLAN_DONE"
    AGGREGATING = "AGGREGATING"
    DONE = "DONE"
    FAILED = "FAILED"
    NEEDS_REPLAN = "NEEDS_REPLAN"
    CANCELLED = "CANCELLED"

    def __str__(self) -> str:
        return self.value

class NodeType(str, Enum):
    """Type of processing a node should perform."""
    PLAN = "PLAN"      # Node that breaks down tasks into subtasks
    EXECUTE = "EXECUTE"  # Node that performs actual work

    def __str__(self) -> str:
        return self.value

class TaskType(str, Enum):
    """Category of task being performed."""
    WRITE = "WRITE"
    THINK = "THINK" 
    SEARCH = "SEARCH"
    AGGREGATE = "AGGREGATE"
    CODE_INTERPRET = "CODE_INTERPRET"
    IMAGE_GENERATION = "IMAGE_GENERATION"

    def __str__(self) -> str:
        return self.value

# Literal types for use in Pydantic models and type hints
TaskStatusLiteral = Literal[
    "PENDING", "READY", "RUNNING", "PLAN_DONE", 
    "AGGREGATING", "DONE", "FAILED", "NEEDS_REPLAN", "CANCELLED"
]

NodeTypeLiteral = Literal["PLAN", "EXECUTE"]

TaskTypeLiteral = Literal[
    "WRITE", "THINK", "SEARCH", "AGGREGATE", 
    "CODE_INTERPRET", "IMAGE_GENERATION"
]

# Utility functions for safe enum conversion
def safe_task_status(value: Union[str, TaskStatus]) -> TaskStatus:
    """
    Safely convert a string or TaskStatus to TaskStatus enum.
    
    Args:
        value: String or TaskStatus enum value
        
    Returns:
        TaskStatus enum
        
    Raises:
        ValueError: If the value is not a valid TaskStatus
    """
    if isinstance(value, TaskStatus):
        return value
    elif isinstance(value, str):
        try:
            return TaskStatus(value.upper())
        except ValueError:
            raise ValueError(f"Invalid TaskStatus: {value}")
    else:
        raise ValueError(f"Cannot convert {type(value)} to TaskStatus")

def safe_node_type(value: Union[str, NodeType]) -> NodeType:
    """
    Safely convert a string or NodeType to NodeType enum.
    
    Args:
        value: String or NodeType enum value
        
    Returns:
        NodeType enum
        
    Raises:
        ValueError: If the value is not a valid NodeType
    """
    if isinstance(value, NodeType):
        return value
    elif isinstance(value, str):
        try:
            return NodeType(value.upper())
        except ValueError:
            raise ValueError(f"Invalid NodeType: {value}")
    else:
        raise ValueError(f"Cannot convert {type(value)} to NodeType")

def safe_task_type(value: Union[str, TaskType]) -> TaskType:
    """
    Safely convert a string or TaskType to TaskType enum.
    
    Args:
        value: String or TaskType enum value
        
    Returns:
        TaskType enum
        
    Raises:
        ValueError: If the value is not a valid TaskType
    """
    if isinstance(value, TaskType):
        return value
    elif isinstance(value, str):
        try:
            return TaskType(value.upper())
        except ValueError:
            raise ValueError(f"Invalid TaskType: {value}")
    else:
        raise ValueError(f"Cannot convert {type(value)} to TaskType")

# Sets of terminal and active statuses for convenience
TERMINAL_STATUSES = {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED}
ACTIVE_STATUSES = {
    TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING, 
    TaskStatus.PLAN_DONE, TaskStatus.AGGREGATING, TaskStatus.NEEDS_REPLAN
}

def is_terminal_status(status: Union[str, TaskStatus]) -> bool:
    """Check if a status represents a terminal state."""
    safe_status = safe_task_status(status)
    return safe_status in TERMINAL_STATUSES

def is_active_status(status: Union[str, TaskStatus]) -> bool:
    """Check if a status represents an active state."""
    safe_status = safe_task_status(status)
    return safe_status in ACTIVE_STATUSES 