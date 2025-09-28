"""
Custom exceptions for the Sentient Research Agent framework.

This module defines a hierarchy of exceptions that provide better error handling
and debugging capabilities throughout the framework.
"""

from typing import Optional, Any, Dict, List
from sentientresearchagent.hierarchical_agent_framework.types import TaskStatus, TaskType, NodeType

class SentientError(Exception):
    """
    Base exception for all Sentient Research Agent errors.
    
    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code
        context: Additional context information
    """
    
    def __init__(self, 
                 message: str, 
                 error_code: Optional[str] = None,
                 context: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "cause": str(self.cause) if self.cause else None
        }

# Configuration Related Errors

class ConfigurationError(SentientError):
    """Raised when there's an issue with configuration."""
    pass

class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid."""
    pass

class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""
    
    def __init__(self, missing_key: str, section: Optional[str] = None):
        message = f"Missing required configuration: {missing_key}"
        if section:
            message = f"Missing required configuration in section '{section}': {missing_key}"
        
        super().__init__(
            message=message,
            context={"missing_key": missing_key, "section": section}
        )

# Agent Related Errors

class AgentError(SentientError):
    """Base class for agent-related errors."""
    pass

class AgentNotFoundError(AgentError):
    """Raised when requested agent is not found in registry."""
    
    def __init__(self, agent_name: str, available_agents: Optional[List[str]] = None):
        message = f"Agent '{agent_name}' not found in registry"
        if available_agents:
            message += f". Available agents: {', '.join(available_agents)}"
        
        super().__init__(
            message=message,
            context={"requested_agent": agent_name, "available_agents": available_agents}
        )

class AgentExecutionError(AgentError):
    """Raised when agent execution fails."""
    
    def __init__(self, 
                 agent_name: str, 
                 task_id: str,
                 original_error: Exception,
                 attempt_number: int = 1):
        message = f"Agent '{agent_name}' failed to execute task '{task_id}' (attempt {attempt_number}): {original_error}"
        
        super().__init__(
            message=message,
            context={
                "agent_name": agent_name,
                "task_id": task_id,
                "attempt_number": attempt_number
            },
            cause=original_error
        )

class AgentTimeoutError(AgentError):
    """Raised when agent execution times out."""
    
    def __init__(self, agent_name: str, task_id: str, timeout_seconds: float):
        message = f"Agent '{agent_name}' timed out after {timeout_seconds}s while executing task '{task_id}'"
        
        super().__init__(
            message=message,
            context={
                "agent_name": agent_name, 
                "task_id": task_id,
                "timeout_seconds": timeout_seconds
            }
        )

class AgentRateLimitError(AgentError):
    """Raised when agent hits rate limits."""
    
    def __init__(self, agent_name: str, retry_after_seconds: Optional[float] = None):
        message = f"Agent '{agent_name}' hit rate limit"
        if retry_after_seconds:
            message += f". Retry after {retry_after_seconds}s"
            
        super().__init__(
            message=message,
            context={"agent_name": agent_name, "retry_after_seconds": retry_after_seconds}
        )

# Task Related Errors

class TaskError(SentientError):
    """Base class for task-related errors."""
    
    def __init__(self, 
                 task_id: str,
                 message: str,
                 error_code: Optional[str] = None,
                 context: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        context = context or {}
        context["task_id"] = task_id
        super().__init__(message, error_code, context, cause)

class TaskExecutionError(TaskError):
    """Raised when task execution fails."""
    
    def __init__(self, 
                 task_id: str, 
                 task_goal: str,
                 current_status: TaskStatus,
                 original_error: Exception):
        message = f"Task '{task_id}' (goal: '{task_goal[:50]}...') failed during execution from status {current_status}"
        
        super().__init__(
            task_id=task_id,
            message=message,
            context={
                "task_goal": task_goal,
                "current_status": str(current_status),
                "original_error_type": type(original_error).__name__
            },
            cause=original_error
        )

class TaskTimeoutError(TaskError):
    """Raised when task execution times out."""
    
    def __init__(self, task_id: str, timeout_seconds: float):
        message = f"Task '{task_id}' timed out after {timeout_seconds}s"
        
        super().__init__(
            task_id=task_id,
            message=message,
            context={"timeout_seconds": timeout_seconds}
        )

class InvalidTaskStateError(TaskError):
    """Raised when task is in an invalid state for the requested operation."""
    
    def __init__(self, 
                 task_id: str, 
                 current_status: TaskStatus, 
                 required_status: TaskStatus,
                 operation: str):
        message = f"Task '{task_id}' cannot {operation}: current status is {current_status}, required status is {required_status}"
        
        super().__init__(
            task_id=task_id,
            message=message,
            context={
                "current_status": str(current_status),
                "required_status": str(required_status),
                "operation": operation
            }
        )

class TaskDependencyError(TaskError):
    """Raised when there are issues with task dependencies."""
    
    def __init__(self, 
                 task_id: str, 
                 dependency_issue: str,
                 dependency_tasks: Optional[List[str]] = None):
        message = f"Task '{task_id}' has dependency issue: {dependency_issue}"
        
        super().__init__(
            task_id=task_id,
            message=message,
            context={
                "dependency_issue": dependency_issue,
                "dependency_tasks": dependency_tasks or []
            }
        )

# Graph Related Errors

class GraphError(SentientError):
    """Base class for graph-related errors."""
    pass

class GraphCycleError(GraphError):
    """Raised when circular dependency detected in task graph."""
    
    def __init__(self, cycle_path: List[str]):
        cycle_str = " -> ".join(cycle_path)
        message = f"Circular dependency detected in task graph: {cycle_str}"
        
        super().__init__(
            message=message,
            context={"cycle_path": cycle_path}
        )

class GraphIntegrityError(GraphError):
    """Raised when graph structure is corrupted or invalid."""
    
    def __init__(self, graph_id: str, issue: str):
        message = f"Graph '{graph_id}' integrity issue: {issue}"
        
        super().__init__(
            message=message,
            context={"graph_id": graph_id, "issue": issue}
        )

class NodeNotFoundError(GraphError):
    """Raised when a requested node is not found in the graph."""
    
    def __init__(self, node_id: str, graph_id: Optional[str] = None):
        message = f"Node '{node_id}' not found"
        if graph_id:
            message += f" in graph '{graph_id}'"
            
        super().__init__(
            message=message,
            context={"node_id": node_id, "graph_id": graph_id}
        )

# Planning Related Errors

class PlanningError(SentientError):
    """Base class for planning-related errors."""
    pass

class InvalidPlanError(PlanningError):
    """Raised when a generated plan is invalid."""
    
    def __init__(self, 
                 plan_data: Any, 
                 validation_errors: List[str],
                 planner_agent: Optional[str] = None):
        message = f"Invalid plan generated"
        if planner_agent:
            message += f" by agent '{planner_agent}'"
        message += f": {'; '.join(validation_errors)}"
        
        super().__init__(
            message=message,
            context={
                "validation_errors": validation_errors,
                "planner_agent": planner_agent,
                "plan_data": str(plan_data)[:200] + "..." if len(str(plan_data)) > 200 else str(plan_data)
            }
        )

class PlanExecutionError(PlanningError):
    """Raised when plan execution fails."""
    
    def __init__(self, 
                 plan_id: str,
                 failed_subtask_id: str,
                 original_error: Exception):
        message = f"Plan '{plan_id}' execution failed at subtask '{failed_subtask_id}': {original_error}"
        
        super().__init__(
            message=message,
            context={
                "plan_id": plan_id,
                "failed_subtask_id": failed_subtask_id
            },
            cause=original_error
        )

# Human in the Loop (HITL) Errors

class HITLError(SentientError):
    """Base class for Human-in-the-Loop errors."""
    pass

class HITLTimeoutError(HITLError):
    """Raised when human review times out."""
    
    def __init__(self, checkpoint_name: str, timeout_seconds: float):
        message = f"Human review timed out after {timeout_seconds}s at checkpoint '{checkpoint_name}'"
        
        super().__init__(
            message=message,
            context={
                "checkpoint_name": checkpoint_name,
                "timeout_seconds": timeout_seconds
            }
        )

class HITLAbortError(HITLError):
    """Raised when human aborts the execution."""
    
    def __init__(self, checkpoint_name: str, abort_reason: Optional[str] = None):
        message = f"Human aborted execution at checkpoint '{checkpoint_name}'"
        if abort_reason:
            message += f": {abort_reason}"
            
        super().__init__(
            message=message,
            context={
                "checkpoint_name": checkpoint_name,
                "abort_reason": abort_reason
            }
        )

# Resource Related Errors

class ResourceError(SentientError):
    """Base class for resource-related errors."""
    pass

class InsufficientResourcesError(ResourceError):
    """Raised when there are insufficient resources (memory, API quota, etc.)."""
    
    def __init__(self, resource_type: str, required: str, available: str):
        message = f"Insufficient {resource_type}: required {required}, available {available}"
        
        super().__init__(
            message=message,
            context={
                "resource_type": resource_type,
                "required": required,
                "available": available
            }
        )

# Utility Functions

def handle_exception(
    exception: Exception, 
    task_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> SentientError:
    """
    Convert a generic exception to an appropriate SentientError.
    
    Args:
        exception: The original exception
        task_id: Optional task ID for context
        agent_name: Optional agent name for context
        context: Additional context information
        
    Returns:
        Appropriate SentientError subclass
    """
    context = context or {}
    
    # Always add task_id and agent_name to context if provided
    if task_id:
        context["task_id"] = task_id
    if agent_name:
        context["agent_name"] = agent_name
    
    # If it's already a SentientError, add context and return
    if isinstance(exception, SentientError):
        exception.context.update(context)
        return exception
    
    # Handle common exception types
    if isinstance(exception, TimeoutError):
        if task_id:
            return TaskTimeoutError(task_id, context.get("timeout_seconds", 30.0))
        elif agent_name:
            return AgentTimeoutError(agent_name, task_id or "unknown", context.get("timeout_seconds", 30.0))
    
    if isinstance(exception, (ConnectionError, OSError)):
        return ResourceError(
            message=f"Connection/resource error: {exception}",
            context=context,  # Now includes task_id and agent_name
            cause=exception
        )
    
    if isinstance(exception, ValueError):
        return ConfigurationError(
            message=f"Configuration validation error: {exception}",
            context=context,  # Now includes task_id and agent_name
            cause=exception
        )
    
    # For any other exception, wrap it in a generic SentientError
    if task_id:
        return TaskExecutionError(
            task_id=task_id,
            task_goal=context.get("task_goal", "unknown"),
            current_status=context.get("current_status", TaskStatus.FAILED),
            original_error=exception
        )
    elif agent_name:
        return AgentExecutionError(
            agent_name=agent_name,
            task_id=task_id or "unknown",
            original_error=exception,
            attempt_number=context.get("attempt_number", 1)
        )
    else:
        return SentientError(
            message=f"Unexpected error: {exception}",
            context=context,
            cause=exception
        )

def create_error_context(
    task_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    node_type: Optional[NodeType] = None,
    task_type: Optional[TaskType] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Create a standard error context dictionary.
    
    Args:
        task_id: Task identifier
        agent_name: Agent name
        node_type: Type of node
        task_type: Type of task
        **kwargs: Additional context items
        
    Returns:
        Dictionary with error context
    """
    context = {}
    
    if task_id:
        context["task_id"] = task_id
    if agent_name:
        context["agent_name"] = agent_name
    if node_type:
        context["node_type"] = str(node_type)
    if task_type:
        context["task_type"] = str(task_type)
    
    context.update(kwargs)
    return context 