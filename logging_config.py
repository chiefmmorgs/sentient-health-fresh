"""
Logging Configuration to Fix "Level 'PLAN' already exists" Error

This sets up proper logging configuration and prevents duplicate level registration.
"""

import logging
import sys
from typing import Optional

def setup_logging(level: str = "INFO") -> None:
    """
    Set up logging configuration to prevent the "Level 'PLAN' already exists" error
    """
    
    # Clear any existing handlers to prevent conflicts
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create custom formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.addHandler(console_handler)
    
    # Silence noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    
    # Prevent the "PLAN" level error by checking if custom levels exist
    if not hasattr(logging, 'PLAN'):
        try:
            logging.addLevelName(25, 'PLAN')
            logging.PLAN = 25
        except (AttributeError, ValueError):
            # Level might already exist, ignore
            pass
    
    logging.info("✅ Logging configured successfully")

def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance"""
    return logging.getLogger(name)

# Initialize logging when module is imported
setup_logging()
