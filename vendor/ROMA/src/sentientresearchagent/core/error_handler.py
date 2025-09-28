"""
Error handling utilities for the Sentient Research Agent framework.

This module provides utilities for consistent error handling, logging,
and recovery throughout the framework.
"""

import sys
import traceback
from typing import Optional, Dict, Any, Callable, TypeVar, Generic
from functools import wraps
from loguru import logger

from sentientresearchagent.exceptions import (
    SentientError, handle_exception, create_error_context,
    TaskExecutionError, AgentExecutionError
)
from sentientresearchagent.hierarchical_agent_framework.types import TaskStatus

T = TypeVar('T')

class ErrorHandler:
    """Central error handler for the framework."""
    
    def __init__(self, enable_detailed_logging: bool = True):
        self.enable_detailed_logging = enable_detailed_logging
        self.error_stats = {
            "total_errors": 0,
            "errors_by_type": {},
            "errors_by_component": {}
        }
    
    def handle_error(self, 
                    error: Exception,
                    component: str = "unknown",
                    task_id: Optional[str] = None,
                    agent_name: Optional[str] = None,
                    context: Optional[Dict[str, Any]] = None,
                    reraise: bool = True) -> Optional[SentientError]:
        """
        Handle an error with consistent logging and statistics tracking.
        
        Args:
            error: The exception that occurred
            component: Component where error occurred
            task_id: Optional task ID
            agent_name: Optional agent name
            context: Additional context
            reraise: Whether to re-raise the error after handling
            
        Returns:
            SentientError if not re-raising, None if re-raising
            
        Raises:
            SentientError: If reraise=True
        """
        # Convert to SentientError if needed
        sentient_error = handle_exception(
            error, 
            task_id=task_id, 
            agent_name=agent_name,
            context=context or {}
        )
        
        # Update statistics
        self.error_stats["total_errors"] += 1
        error_type = type(sentient_error).__name__
        self.error_stats["errors_by_type"][error_type] = \
            self.error_stats["errors_by_type"].get(error_type, 0) + 1
        self.error_stats["errors_by_component"][component] = \
            self.error_stats["errors_by_component"].get(component, 0) + 1
        
        # Log the error
        self._log_error(sentient_error, component)
        
        if reraise:
            raise sentient_error
        else:
            return sentient_error
    
    def _log_error(self, error: SentientError, component: str):
        """Log an error with appropriate detail level."""
        error_dict = error.to_dict()
        
        # Basic error log
        logger.error(f"[{component}] {error.message}")
        
        if self.enable_detailed_logging:
            # Detailed context logging
            if error.context:
                logger.debug(f"Error context: {error.context}")
            
            # Original exception traceback
            if error.cause:
                logger.debug(f"Original exception: {error.cause}")
                if hasattr(error.cause, '__traceback__'):
                    logger.debug("Traceback:")
                    for line in traceback.format_exception(
                        type(error.cause), error.cause, error.cause.__traceback__
                    ):
                        logger.debug(line.strip())
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        return self.error_stats.copy()
    
    def reset_stats(self):
        """Reset error statistics."""
        self.error_stats = {
            "total_errors": 0,
            "errors_by_type": {},
            "errors_by_component": {}
        }

# Global error handler instance
_global_error_handler = ErrorHandler()

def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    return _global_error_handler

def set_error_handler(handler: ErrorHandler):
    """Set the global error handler instance."""
    global _global_error_handler
    _global_error_handler = handler

# Decorators for error handling

def handle_task_errors(task_id_param: str = "task_id", 
                      agent_name_param: Optional[str] = None,
                      component: str = "task_processor"):
    """
    Decorator to handle errors in task processing functions.
    
    Args:
        task_id_param: Name of parameter containing task ID
        agent_name_param: Name of parameter containing agent name
        component: Component name for logging
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Extract context from function parameters
                context = create_error_context()
                task_id = kwargs.get(task_id_param)
                agent_name = kwargs.get(agent_name_param) if agent_name_param else None
                
                get_error_handler().handle_error(
                    error=e,
                    component=component,
                    task_id=task_id,
                    agent_name=agent_name,
                    context=context,
                    reraise=True
                )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Extract context from function parameters
                context = create_error_context()
                task_id = kwargs.get(task_id_param)
                agent_name = kwargs.get(agent_name_param) if agent_name_param else None
                
                get_error_handler().handle_error(
                    error=e,
                    component=component,
                    task_id=task_id,
                    agent_name=agent_name,
                    context=context,
                    reraise=True
                )
        
        # Return appropriate wrapper based on whether function is async
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def handle_agent_errors(agent_name_param: str = "agent_name",
                       component: str = "agent_executor"):
    """
    Decorator to handle errors in agent execution functions.
    
    Args:
        agent_name_param: Name of parameter containing agent name
        component: Component name for logging
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                agent_name = kwargs.get(agent_name_param)
                context = create_error_context(agent_name=agent_name)
                
                get_error_handler().handle_error(
                    error=e,
                    component=component,
                    agent_name=agent_name,
                    context=context,
                    reraise=True
                )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                agent_name = kwargs.get(agent_name_param)
                context = create_error_context(agent_name=agent_name)
                
                get_error_handler().handle_error(
                    error=e,
                    component=component,
                    agent_name=agent_name,
                    context=context,
                    reraise=True
                )
        
        # Return appropriate wrapper based on whether function is async
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

class ErrorRecovery:
    """Utilities for error recovery and retry logic."""
    
    @staticmethod
    async def retry_with_backoff(
        func: Callable,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        exceptions: tuple = (Exception,)
    ) -> T:
        """
        Retry a function with exponential backoff.
        
        Args:
            func: Function to retry (can be async or sync)
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay between retries
            max_delay: Maximum delay between retries
            backoff_factor: Factor to multiply delay by after each attempt
            exceptions: Tuple of exceptions to catch and retry on
            
        Returns:
            Result of successful function call
            
        Raises:
            Last exception if all retries fail
        """
        import asyncio
        
        last_exception = None
        delay = base_delay
        
        for attempt in range(max_retries + 1):
            try:
                if hasattr(func, '__call__'):
                    if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:
                        # Async function
                        return await func()
                    else:
                        # Sync function
                        return func()
                else:
                    # Callable object
                    result = func()
                    if hasattr(result, '__await__'):
                        return await result
                    else:
                        return result
                        
            except exceptions as e:
                last_exception = e
                
                if attempt < max_retries:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
                else:
                    logger.error(f"All {max_retries + 1} attempts failed. Last error: {e}")
                    break
        
        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("Retry logic failed without capturing an exception")

def safe_execute(func: Callable, 
                default_return: Any = None,
                log_errors: bool = True,
                component: str = "safe_execute") -> Any:
    """
    Safely execute a function, returning a default value on error.
    
    Args:
        func: Function to execute
        default_return: Value to return on error
        log_errors: Whether to log errors
        component: Component name for logging
        
    Returns:
        Function result or default_return on error
    """
    try:
        return func()
    except Exception as e:
        if log_errors:
            get_error_handler().handle_error(
                error=e,
                component=component,
                reraise=False
            )
        return default_return 