"""
Main entry point for the sentientresearchagent package.

Usage:
    python -m sentientresearchagent
"""

# Set up basic clean logging immediately
from loguru import logger
import sys

# Import our clean formatter
from .core.logging_config import format_record

# Remove default handler and add clean one with our formatter
# Start with WARNING level to reduce startup noise
logger.remove()
logger.add(
    sys.stdout,
    format=format_record,
    colorize=True,
    level="WARNING"
)

from .server.main import main

if __name__ == '__main__':
    main() 