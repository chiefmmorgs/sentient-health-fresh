"""
Core components of the Sentient Research Agent framework.
"""
from .system_manager import SystemManagerV2 as SystemManager
from .error_handler import (
    ErrorHandler, 
    get_error_handler, 
    set_error_handler, 
    handle_task_errors, 
    handle_agent_errors, 
    ErrorRecovery, 
    safe_execute
)
from .project_manager import ProjectManager, ProjectExecutionContext

__all__ = [
    "SystemManager",
    "ErrorHandler",
    "get_error_handler",
    "set_error_handler",
    "handle_task_errors",
    "handle_agent_errors",
    "ErrorRecovery",
    "safe_execute",
    "ProjectManager",
    "ProjectExecutionContext",
] 