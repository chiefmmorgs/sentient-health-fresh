"""
Flask Application Factory

Creates and configures the Flask app and SocketIO instance.
"""

from flask import Flask, current_app
from flask_cors import CORS
from flask_socketio import SocketIO
from typing import Optional
import os
from loguru import logger
from ..config import SentientConfig
from .api.profiles import create_profile_routes


def create_app(main_config: Optional[SentientConfig] = None) -> Flask:
    """
    Create and configure Flask application.
    
    Args:
        main_config: Optional SentientConfig instance. 
                     If None, app uses basic defaults (not recommended for full server).
        
    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    
    if main_config and main_config.web_server:
        # Use settings from SentientConfig.web_server
        app.config.update({
            'SECRET_KEY': main_config.web_server.secret_key,
            'DEBUG': main_config.web_server.debug,
            # Add any other Flask specific app.config settings here
            # e.g., 'SESSION_COOKIE_SECURE': not main_config.web_server.debug,
        })
        logger.info(f"Flask app configured from SentientConfig.web_server (Debug: {main_config.web_server.debug})")
    else:
        # Fallback to basic defaults if no config provided (e.g., for standalone app testing)
        # This path should ideally not be hit when running the full SentientServer
        app.config.update({
            'SECRET_KEY': os.getenv('FLASK_SECRET_KEY', 'fallback-default-secret-key'),
            'DEBUG': os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
        })
        logger.warning("Flask app created with basic fallback defaults as SentientConfig was not provided to create_app.")

    # Example: If CORS origins were part of WebServerConfig:
    # cors_origins = main_config.web_server.cors_origins if main_config and main_config.web_server else ["http://localhost:3000", "http://127.0.0.1:3000"]
    # For now, keeping CORS static as it was.
    # Configure CORS for development - allow ngrok domains
    import os
    cors_origins = [
        "http://localhost:3000", 
        "http://127.0.0.1:3000"
    ]
    
    # Add ngrok domain if NGROK_URL environment variable is set
    ngrok_url = os.getenv("NGROK_URL")
    if ngrok_url:
        cors_origins.append(ngrok_url)
    
    # For development, also allow common ngrok patterns
    cors_origins.extend([
        "https://215f9d3b4eda.ngrok-free.app",  # Current ngrok URL
    ])
    
    CORS(app, origins=cors_origins)
    
    return app


def create_socketio(app: Flask) -> SocketIO:
    """
    Create and configure SocketIO instance.
    
    Args:
        app: Flask application instance
        // main_config: Optional[SentientConfig] = None (if needed)
        
    Returns:
        Configured SocketIO instance
    """
    # Example: if async_mode or other SocketIO params needed to be configurable via SentientConfig.web_server
    # async_mode = main_config.web_server.socketio_async_mode if main_config and main_config.web_server else 'threading'
    socketio = SocketIO(
        app,
        cors_allowed_origins="*", # This could also come from main_config.web_server.cors_allowed_origins
        async_mode='threading', # Example: could be configurable
        logger=False,           # Disabled to reduce log noise
        engineio_logger=False   # Disabled to reduce log noise
    )
    
    return socketio


def register_routes(app: Flask, socketio: SocketIO, system_manager, project_service, execution_service):
    """
    Register all API routes and WebSocket event handlers.
    
    Args:
        app: Flask application instance
        socketio: SocketIO instance
        system_manager: SystemManager instance
        project_service: ProjectService instance
        execution_service: ExecutionService instance
    """
    # Register REST API routes
    from .api.system import create_system_routes
    from .api.projects import create_project_routes
    from .api.simple_api import create_simple_api_routes
    
    create_system_routes(app, system_manager)
    create_project_routes(app, project_service, execution_service)
    create_simple_api_routes(app, system_manager)
    
    # Register WebSocket event handlers
    from .websocket.events import register_websocket_events
    from .websocket.hitl import register_hitl_events
    
    register_websocket_events(socketio, project_service, execution_service)
    register_hitl_events(socketio)
    
    # Profile management routes
    create_profile_routes(app, system_manager)
