"""
Sentient Research Agent Server Package

This package provides a modular, well-organized server implementation
that separates concerns and follows software engineering best practices.
"""

from .app import create_app, create_socketio
# from ..core.system_manager import SystemManager # REMOVED
from .services.project_service import ProjectService
from .services.execution_service import ExecutionService
from .main import create_server, SentientServer

__all__ = [
    'create_app',
    'create_socketio',
    # 'SystemManager', # REMOVED
    'ProjectService',
    'ExecutionService',
    'create_server',
    'SentientServer',
]
