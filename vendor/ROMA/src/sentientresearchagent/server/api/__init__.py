"""
API Routes Package

REST API endpoints for the server.
"""

from .system import create_system_routes
from .projects import create_project_routes
from .simple_api import create_simple_api_routes

__all__ = [
    'create_system_routes',
    'create_project_routes', 
    'create_simple_api_routes',
]
