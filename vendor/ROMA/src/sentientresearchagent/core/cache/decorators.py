"""
Cache decorators for easy integration with the caching system.
"""

import json
import inspect
import functools
from typing import Any, Optional, Dict, Callable, Union
from loguru import logger

from sentientresearchagent.core.cache.cache_manager import get_cache_manager

def cache_result(
    namespace: str,
    key_func: Optional[Callable] = None,
    ttl_seconds: Optional[int] = None,
    include_args: bool = True,
    exclude_args: Optional[list] = None,
    cache_condition: Optional[Callable] = None
):
    """
    Decorator to cache function results.
    
    Args:
        namespace: Cache namespace for this function
        key_func: Function to generate cache key (takes same args as decorated function)
        ttl_seconds: Time to live for cached results
        include_args: Whether to include function arguments in cache key
        exclude_args: List of argument names to exclude from cache key
        cache_condition: Function that returns True if result should be cached
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()
            if not cache_manager or not cache_manager.config.enabled:
                # No caching, just call the function
                return await func(*args, **kwargs)
            
            # Generate cache key
            if key_func:
                try:
                    cache_key = key_func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Cache key function failed for {func.__name__}: {e}")
                    cache_key = _default_key_from_args(func, args, kwargs, include_args, exclude_args)
            else:
                cache_key = _default_key_from_args(func, args, kwargs, include_args, exclude_args)
            
            # Try to get from cache
            cached_result = cache_manager.get(namespace, cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}({cache_key})")
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache the result if condition is met
            should_cache = True
            if cache_condition:
                try:
                    should_cache = cache_condition(result, *args, **kwargs)
                except Exception as e:
                    logger.warning(f"Cache condition function failed for {func.__name__}: {e}")
                    should_cache = True
            
            if should_cache and result is not None:
                cache_manager.set(
                    namespace=namespace,
                    identifier=cache_key,
                    value=result,
                    ttl_seconds=ttl_seconds
                )
                logger.debug(f"Cached result for {func.__name__}({cache_key})")
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()
            if not cache_manager or not cache_manager.config.enabled:
                return func(*args, **kwargs)
            
            # Generate cache key (same logic as async version)
            if key_func:
                try:
                    cache_key = key_func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Cache key function failed for {func.__name__}: {e}")
                    cache_key = _default_key_from_args(func, args, kwargs, include_args, exclude_args)
            else:
                cache_key = _default_key_from_args(func, args, kwargs, include_args, exclude_args)
            
            # Try to get from cache
            cached_result = cache_manager.get(namespace, cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}({cache_key})")
                return cached_result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache the result if condition is met
            should_cache = True
            if cache_condition:
                try:
                    should_cache = cache_condition(result, *args, **kwargs)
                except Exception as e:
                    logger.warning(f"Cache condition function failed for {func.__name__}: {e}")
                    should_cache = True
            
            if should_cache and result is not None:
                cache_manager.set(
                    namespace=namespace,
                    identifier=cache_key,
                    value=result,
                    ttl_seconds=ttl_seconds
                )
                logger.debug(f"Cached result for {func.__name__}({cache_key})")
            
            return result
        
        # Return appropriate wrapper based on whether function is async
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def cache_agent_response(
    ttl_seconds: Optional[int] = None,
    key_func: Optional[Callable] = None
):
    """
    Specialized decorator for caching agent responses.
    
    Args:
        ttl_seconds: Time to live for cached responses
        key_func: Custom function to generate cache key
    """
    def default_agent_key_func(*args, **kwargs):
        # Extract agent name and input from typical agent function signatures
        agent_name = "unknown"
        input_hash = "unknown"
        
        # Try to extract agent name
        if args and hasattr(args[0], 'agent_name'):
            agent_name = args[0].agent_name
        elif args and hasattr(args[0], 'name'):
            agent_name = args[0].name
        
        # Try to extract and hash input
        if len(args) >= 2:
            try:
                input_str = json.dumps(args[1], sort_keys=True, default=str)
                import hashlib
                input_hash = hashlib.sha256(input_str.encode()).hexdigest()[:16]
            except Exception:
                input_hash = str(hash(str(args[1])))[:16]
        
        return f"{agent_name}:{input_hash}"
    
    # Only cache successful responses (non-None, non-empty)
    def cache_condition(result, *args, **kwargs):
        return result is not None and result != ""
    
    return cache_result(
        namespace="agent_responses",
        key_func=key_func or default_agent_key_func,
        ttl_seconds=ttl_seconds,
        cache_condition=cache_condition
    )

def _default_key_from_args(func: Callable, args: tuple, kwargs: dict,
                          include_args: bool, exclude_args: Optional[list]) -> str:
    """Generate a default cache key from function arguments."""
    key_parts = [func.__name__]
    
    if include_args:
        exclude_set = set(exclude_args or [])
        
        # Get function signature to map args to parameter names
        try:
            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())
            
            # Process positional arguments
            for i, arg in enumerate(args):
                if i < len(param_names):
                    param_name = param_names[i]
                    if param_name not in exclude_set:
                        try:
                            arg_str = json.dumps(arg, sort_keys=True, default=str)
                        except Exception:
                            arg_str = str(arg)
                        key_parts.append(f"{param_name}={arg_str}")
            
            # Process keyword arguments
            for param_name, value in kwargs.items():
                if param_name not in exclude_set:
                    try:
                        value_str = json.dumps(value, sort_keys=True, default=str)
                    except Exception:
                        value_str = str(value)
                    key_parts.append(f"{param_name}={value_str}")
                    
        except Exception as e:
            logger.warning(f"Error generating cache key for {func.__name__}: {e}")
            # Fallback to simple string representation
            key_parts.append(str(hash(str(args) + str(kwargs))))
    
    return ":".join(key_parts)

# Utility functions for manual cache operations

def cache_get(namespace: str, identifier: str, 
              context: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    """Get a value from cache."""
    cache_manager = get_cache_manager()
    if cache_manager:
        return cache_manager.get(namespace, identifier, context)
    return None

def cache_set(namespace: str, identifier: str, value: Any,
              context: Optional[Dict[str, Any]] = None,
              ttl_seconds: Optional[int] = None) -> bool:
    """Set a value in cache."""
    cache_manager = get_cache_manager()
    if cache_manager:
        return cache_manager.set(namespace, identifier, value, context, ttl_seconds)
    return False

def cache_delete(namespace: str, identifier: str,
                 context: Optional[Dict[str, Any]] = None) -> bool:
    """Delete a value from cache."""
    cache_manager = get_cache_manager()
    if cache_manager:
        return cache_manager.delete(namespace, identifier, context)
    return False

def invalidate_cache_namespace(namespace: str) -> int:
    """Clear all entries in a cache namespace."""
    cache_manager = get_cache_manager()
    if cache_manager:
        return cache_manager.clear_namespace(namespace)
    return 0 