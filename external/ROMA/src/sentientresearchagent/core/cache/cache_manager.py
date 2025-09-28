"""
Caching system for the Sentient Research Agent framework.

This module provides a flexible caching layer that can significantly improve
performance by avoiding redundant LLM calls and storing intermediate results.
"""

import os
import json
import time
import hashlib
import pickle
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List, Union
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from loguru import logger

from sentientresearchagent.config import CacheConfig
from sentientresearchagent.exceptions import SentientError

@dataclass
class CacheEntry:
    """Represents a cached item with metadata."""
    key: str
    value: Any
    created_at: datetime
    accessed_at: datetime
    access_count: int = 0
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def touch(self):
        """Update access time and count."""
        self.accessed_at = datetime.now()
        self.access_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create from dictionary after deserialization."""
        return cls(
            key=data["key"],
            value=data["value"],
            created_at=datetime.fromisoformat(data["created_at"]),
            accessed_at=datetime.fromisoformat(data["accessed_at"]),
            access_count=data["access_count"],
            expires_at=datetime.fromisoformat(data["expires_at"]) if data["expires_at"] else None,
            metadata=data["metadata"]
        )

class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[CacheEntry]:
        """Get a cache entry by key."""
        pass
    
    @abstractmethod
    def set(self, key: str, entry: CacheEntry) -> None:
        """Store a cache entry."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""
        pass
    
    @abstractmethod
    def keys(self) -> List[str]:
        """Get all cache keys."""
        pass
    
    @abstractmethod
    def size(self) -> int:
        """Get number of cached items."""
        pass

class MemoryCacheBackend(CacheBackend):
    """In-memory cache backend."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
    
    def get(self, key: str) -> Optional[CacheEntry]:
        entry = self._cache.get(key)
        if entry and not entry.is_expired():
            entry.touch()
            return entry
        elif entry and entry.is_expired():
            # Remove expired entry
            del self._cache[key]
        return None
    
    def set(self, key: str, entry: CacheEntry) -> None:
        # Evict old entries if cache is full
        if len(self._cache) >= self.max_size and key not in self._cache:
            self._evict_lru()
        
        self._cache[key] = entry
    
    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        self._cache.clear()
    
    def keys(self) -> List[str]:
        # Only return keys for non-expired entries
        valid_keys = []
        expired_keys = []
        
        for key, entry in self._cache.items():
            if entry.is_expired():
                expired_keys.append(key)
            else:
                valid_keys.append(key)
        
        # Clean up expired entries
        for key in expired_keys:
            del self._cache[key]
        
        return valid_keys
    
    def size(self) -> int:
        return len(self.keys())  # This will also clean up expired entries
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return
        
        # Find the least recently used entry
        lru_key = min(self._cache.keys(), 
                     key=lambda k: self._cache[k].accessed_at)
        del self._cache[lru_key]

class FileCacheBackend(CacheBackend):
    """File-based cache backend."""
    
    def __init__(self, cache_dir: Union[str, Path] = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Index file to track cache entries
        self.index_file = self.cache_dir / "cache_index.json"
        self._load_index()
    
    def _load_index(self) -> None:
        """Load cache index from file."""
        self._index = {}
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    self._index = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                logger.warning("Cache index file corrupted, starting fresh")
                self._index = {}
    
    def _save_index(self) -> None:
        """Save cache index to file."""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self._index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")
    
    def _get_cache_file(self, key: str) -> Path:
        """Get cache file path for a key."""
        # Use hash to avoid filesystem issues with long/special characters
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    def get(self, key: str) -> Optional[CacheEntry]:
        if key not in self._index:
            return None
        
        cache_file = self._get_cache_file(key)
        if not cache_file.exists():
            # File missing, remove from index
            del self._index[key]
            self._save_index()
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                entry_dict = pickle.load(f)
            
            entry = CacheEntry.from_dict(entry_dict)
            
            if entry.is_expired():
                self.delete(key)
                return None
            
            # Update access info
            entry.touch()
            
            # Save updated entry
            with open(cache_file, 'wb') as f:
                pickle.dump(entry.to_dict(), f)
            
            return entry
            
        except Exception as e:
            logger.error(f"Error reading cache file {cache_file}: {e}")
            self.delete(key)
            return None
    
    def set(self, key: str, entry: CacheEntry) -> None:
        cache_file = self._get_cache_file(key)
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(entry.to_dict(), f)
            
            # Update index
            self._index[key] = {
                "file": cache_file.name,
                "created_at": entry.created_at.isoformat(),
                "expires_at": entry.expires_at.isoformat() if entry.expires_at else None
            }
            self._save_index()
            
        except Exception as e:
            logger.error(f"Error writing cache file {cache_file}: {e}")
            raise SentientError(f"Failed to cache item: {e}")
    
    def delete(self, key: str) -> bool:
        if key not in self._index:
            return False
        
        cache_file = self._get_cache_file(key)
        
        # Remove file
        if cache_file.exists():
            try:
                cache_file.unlink()
            except Exception as e:
                logger.error(f"Error deleting cache file {cache_file}: {e}")
        
        # Remove from index
        del self._index[key]
        self._save_index()
        return True
    
    def clear(self) -> None:
        """Clear all cache files."""
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                cache_file.unlink()
            except Exception as e:
                logger.error(f"Error deleting cache file {cache_file}: {e}")
        
        self._index.clear()
        self._save_index()
    
    def keys(self) -> List[str]:
        # Clean up expired entries first
        expired_keys = []
        for key, index_data in self._index.items():
            if index_data.get("expires_at"):
                expires_at = datetime.fromisoformat(index_data["expires_at"])
                if datetime.now() > expires_at:
                    expired_keys.append(key)
        
        for key in expired_keys:
            self.delete(key)
        
        return list(self._index.keys())
    
    def size(self) -> int:
        return len(self.keys())

class CacheManager:
    """Main cache manager with multiple backend support."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.backend = self._create_backend()
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
    
    def _create_backend(self) -> CacheBackend:
        """Create appropriate cache backend based on config."""
        if not self.config.enabled:
            return MemoryCacheBackend(max_size=0)  # Disabled cache
        
        if self.config.cache_type == "memory":
            return MemoryCacheBackend(max_size=self.config.max_size)
        elif self.config.cache_type == "file":
            cache_dir = self.config.cache_dir or ".cache"
            return FileCacheBackend(cache_dir=cache_dir)
        else:
            logger.warning(f"Unknown cache type: {self.config.cache_type}, falling back to memory")
            return MemoryCacheBackend(max_size=self.config.max_size)
    
    def _generate_key(self, namespace: str, identifier: str, 
                     context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a cache key from namespace, identifier, and context.
        
        Args:
            namespace: Category of cached item (e.g., "agent", "task", "plan")
            identifier: Unique identifier within namespace
            context: Additional context for key generation
            
        Returns:
            Cache key string
        """
        key_parts = [namespace, identifier]
        
        if context:
            # Sort context keys for consistent hashing
            context_str = json.dumps(context, sort_keys=True, default=str)
            context_hash = hashlib.sha256(context_str.encode()).hexdigest()[:16]
            key_parts.append(context_hash)
        
        return ":".join(key_parts)
    
    def get(self, namespace: str, identifier: str, 
            context: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """
        Get a cached value.
        
        Args:
            namespace: Cache namespace
            identifier: Item identifier
            context: Additional context
            
        Returns:
            Cached value or None if not found/expired
        """
        if not self.config.enabled:
            return None
        
        key = self._generate_key(namespace, identifier, context)
        
        try:
            entry = self.backend.get(key)
            if entry:
                self.stats["hits"] += 1
                logger.debug(f"Cache HIT: {key}")
                return entry.value
            else:
                self.stats["misses"] += 1
                logger.debug(f"Cache MISS: {key}")
                return None
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    def set(self, namespace: str, identifier: str, value: Any,
            context: Optional[Dict[str, Any]] = None,
            ttl_seconds: Optional[int] = None,
            metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Cache a value.
        
        Args:
            namespace: Cache namespace
            identifier: Item identifier  
            value: Value to cache
            context: Additional context
            ttl_seconds: Time to live in seconds (overrides config default)
            metadata: Additional metadata to store
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self.config.enabled:
            return False
        
        key = self._generate_key(namespace, identifier, context)
        ttl = ttl_seconds or self.config.ttl_seconds
        
        try:
            now = datetime.now()
            expires_at = now + timedelta(seconds=ttl) if ttl > 0 else None
            
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                accessed_at=now,
                expires_at=expires_at,
                metadata=metadata or {}
            )
            
            self.backend.set(key, entry)
            self.stats["sets"] += 1
            logger.debug(f"Cache SET: {key} (expires: {expires_at})")
            return True
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, namespace: str, identifier: str,
               context: Optional[Dict[str, Any]] = None) -> bool:
        """Delete a cached value."""
        if not self.config.enabled:
            return False
        
        key = self._generate_key(namespace, identifier, context)
        
        try:
            success = self.backend.delete(key)
            if success:
                self.stats["deletes"] += 1
                logger.debug(f"Cache DELETE: {key}")
            return success
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def clear_namespace(self, namespace: str) -> int:
        """Clear all entries in a namespace."""
        if not self.config.enabled:
            return 0
        
        keys_to_delete = [key for key in self.backend.keys() 
                         if key.startswith(f"{namespace}:")]
        
        deleted_count = 0
        for key in keys_to_delete:
            if self.backend.delete(key):
                deleted_count += 1
        
        logger.info(f"Cleared {deleted_count} entries from namespace '{namespace}'")
        return deleted_count
    
    def clear_all(self) -> None:
        """Clear all cached entries."""
        if not self.config.enabled:
            return
        
        try:
            self.backend.clear()
            logger.info("Cache cleared completely")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total_requests,
            "current_size": self.backend.size(),
            "enabled": self.config.enabled,
            "backend_type": self.config.cache_type
        }
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }

# Global cache manager instance
_global_cache_manager: Optional[CacheManager] = None

def get_cache_manager() -> Optional[CacheManager]:
    """Get the global cache manager instance."""
    return _global_cache_manager

def set_cache_manager(manager: CacheManager) -> None:
    """Set the global cache manager instance."""
    global _global_cache_manager
    _global_cache_manager = manager

def init_cache_manager(config: CacheConfig) -> CacheManager:
    """Initialize and set the global cache manager."""
    manager = CacheManager(config)
    set_cache_manager(manager)
    logger.info(f"Cache manager initialized: {config.cache_type} backend, enabled={config.enabled}")
    return manager 