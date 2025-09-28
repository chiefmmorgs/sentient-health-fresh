"""
Utility functions for working with configurations.
"""

from pathlib import Path
from typing import Optional, Union, Dict, Any
from loguru import logger

from .config import SentientConfig, load_config

def find_config_file() -> Optional[Path]:
    """
    Find configuration file using comprehensive search paths.
    
    Search order:
    1. ./sentient.yaml (primary)
    2. ./config.yaml (common alternative)
    3. ./sentient.yml
    4. ~/.sentient/config.yaml
    5. ~/.sentient/config.yml
    6. /etc/sentient/config.yaml
    
    Returns:
        Path to configuration file if found, None otherwise
    """
    search_paths = [
        Path("./sentient.yaml"),      # Primary config file
        Path("./config.yaml"),        # Common alternative
        Path("./sentient.yml"),
        Path.home() / ".sentient" / "config.yaml",
        Path.home() / ".sentient" / "config.yml",
        Path("/etc/sentient/config.yaml"),
    ]
    
    for path in search_paths:
        if path.exists() and path.is_file():
            logger.info(f"Found configuration file: {path}")
            return path
    
    logger.warning("No configuration file found, will use environment variables and defaults")
    return None

def auto_load_config() -> SentientConfig:
    """
    Automatically load configuration using standard search and precedence.
    
    Returns:
        SentientConfig instance
    """
    config_file = find_config_file()
    return load_config(config_file=config_file, use_env=True)

def validate_config(config: SentientConfig) -> Dict[str, Any]:
    """
    Comprehensive validation of configuration.
    
    Args:
        config: Configuration to validate
        
    Returns:
        Dictionary with validation results
    """
    issues = []
    warnings = []
    
    # Check API keys
    missing_keys = config.validate_api_keys()
    if missing_keys:
        issues.append(f"Missing API keys: {', '.join(missing_keys)}")
    
    # Check execution settings
    if config.execution.max_concurrent_nodes > 10 and config.execution.max_concurrent_nodes <= 20:
        warnings.append(f"High concurrency ({config.execution.max_concurrent_nodes}) may cause rate limiting. Max recommended for some LLMs is 10-20.")
    
    # Check cache settings
    if config.cache.enabled and config.cache.cache_type == "redis" and not config.cache.redis_url:
        issues.append("Redis cache enabled but no redis_url provided")
    
    # Check logging settings
    if config.logging.enable_file and config.logging.file_path:
        log_dir = Path(config.logging.file_path).parent
        if not log_dir.exists():
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                warnings.append(f"Cannot create log directory {log_dir}: {e}")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings
    }

def get_config_info(config: SentientConfig) -> Dict[str, Any]:
    """
    Get information about the current configuration.
    
    Args:
        config: Configuration to analyze
        
    Returns:
        Dictionary with configuration information
    """
    return {
        "config_version": config.config_version,
        "environment": config.environment,
        "llm_provider": config.llm.provider,
        "llm_model": config.llm.model,
        "cache_enabled": config.cache.enabled,
        "max_concurrent_nodes": config.execution.max_concurrent_nodes,
        "hitl_enabled": config.execution.enable_hitl,
        "custom_agents": list(config.agents.keys()),
        "log_level": config.logging.level,
    } 