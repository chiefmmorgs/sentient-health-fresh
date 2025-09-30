# cache_manager.py
import json
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

class SearchCache:
    """Simple in-memory cache for search results"""
    
    def __init__(self, ttl_hours: int = 24):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_hours * 3600
        
    def _get_key(self, query: str, deep_mode: bool) -> str:
        """Generate cache key from query"""
        return f"{query.lower().strip()}:{deep_mode}"
    
    def get(self, query: str, deep_mode: bool = False) -> Optional[Dict[str, Any]]:
        """Retrieve cached result if available and not expired"""
        key = self._get_key(query, deep_mode)
        
        if key not in self.cache:
            return None
        
        cached = self.cache[key]
        age = time.time() - cached["timestamp"]
        
        if age > self.ttl_seconds:
            # Expired, remove it
            del self.cache[key]
            return None
        
        return cached["result"]
    
    def set(self, query: str, result: Dict[str, Any], deep_mode: bool = False):
        """Store result in cache"""
        key = self._get_key(query, deep_mode)
        self.cache[key] = {
            "result": result,
            "timestamp": time.time()
        }
    
    def clear(self):
        """Clear all cached results"""
        self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        now = time.time()
        active = sum(1 for v in self.cache.values() if (now - v["timestamp"]) <= self.ttl_seconds)
        
        return {
            "total_entries": len(self.cache),
            "active_entries": active,
            "ttl_hours": self.ttl_seconds / 3600
        }

# Global cache instance
search_cache = SearchCache(ttl_hours=24)
