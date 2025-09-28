"""
Thread-Local Project Context Manager

Provides thread-safe project context isolation to prevent race conditions
when multiple projects run simultaneously.
"""

import threading
import os
from typing import Optional
from loguru import logger

class ProjectContextManager:
    """
    Thread-local project context manager that ensures each execution thread
    maintains its own isolated project ID context.
    
    This solves the race condition issue where multiple concurrent projects
    would overwrite each other's CURRENT_PROJECT_ID environment variable.
    """
    
    def __init__(self):
        self._context = threading.local()
    
    def set_project_id(self, project_id: str) -> None:
        """
        Set the project ID for the current thread.
        
        Args:
            project_id: The project ID to set for this thread
        """
        self._context.project_id = project_id
        logger.debug(f"Set project ID for thread {threading.get_ident()}: {project_id}")
    
    def get_project_id(self) -> Optional[str]:
        """
        Get the project ID for the current thread.
        
        Returns:
            The project ID for the current thread, or None if not set
        """
        if hasattr(self._context, 'project_id'):
            return self._context.project_id
        return None
    
    def clear_project_id(self) -> None:
        """
        Clear the project ID for the current thread.
        """
        if hasattr(self._context, 'project_id'):
            old_project_id = self._context.project_id
            delattr(self._context, 'project_id')
            logger.debug(f"Cleared project ID for thread {threading.get_ident()}: {old_project_id}")
    
    def get_project_directories(self) -> dict:
        """
        Get project-specific directory paths based on current project context.
        
        Returns:
            Dictionary containing project directory paths
        """
        project_id = self.get_project_id()
        if not project_id:
            return {}
            
        from .project_structure import ProjectStructure
        return ProjectStructure.get_project_directories(project_id)
    
    def is_project_context_set(self) -> bool:
        """
        Check if a project context is set for the current thread.
        
        Returns:
            True if project context is set, False otherwise
        """
        return hasattr(self._context, 'project_id')
    
    def get_context_info(self) -> dict:
        """
        Get debugging information about the current context.
        
        Returns:
            Dictionary with context debugging information
        """
        thread_id = threading.get_ident()
        thread_project_id = getattr(self._context, 'project_id', None)
        
        return {
            'thread_id': thread_id,
            'thread_project_id': thread_project_id,
            'effective_project_id': self.get_project_id(),
            'context_set': self.is_project_context_set()
        }

# Global instance for application-wide use
_project_context_manager = ProjectContextManager()

def set_project_context(project_id: str) -> None:
    """
    Set the project context for the current thread.
    
    Args:
        project_id: The project ID to set
    """
    _project_context_manager.set_project_id(project_id)

def get_project_context() -> Optional[str]:
    """
    Get the current project context for this thread.
    
    Returns:
        The current project ID or None if not set
    """
    return _project_context_manager.get_project_id()

def clear_project_context() -> None:
    """
    Clear the project context for the current thread.
    """
    _project_context_manager.clear_project_id()

def get_project_directories() -> dict:
    """
    Get project-specific directory paths.
    
    Returns:
        Dictionary containing project directories
    """
    return _project_context_manager.get_project_directories()

def is_project_context_set() -> bool:
    """
    Check if project context is set for current thread.
    
    Returns:
        True if context is set, False otherwise
    """
    return _project_context_manager.is_project_context_set()

def get_context_debug_info() -> dict:
    """
    Get debugging information about current project context.
    
    Returns:
        Dictionary with debugging information
    """
    return _project_context_manager.get_context_info()