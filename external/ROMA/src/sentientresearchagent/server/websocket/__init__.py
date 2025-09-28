"""
WebSocket Event Handlers Package

WebSocket event handlers for real-time communication.
"""

from .events import register_websocket_events
from .hitl import register_hitl_events

__all__ = [
    'register_websocket_events',
    'register_hitl_events',
]
