"""
HITL (Human-in-the-Loop) WebSocket Handlers

Handles human-in-the-loop interactions via WebSocket.
"""

from flask_socketio import emit
from loguru import logger


def register_hitl_events(socketio):
    """
    Register HITL-specific WebSocket event handlers.
    
    Args:
        socketio: SocketIO instance
    """
    
    @socketio.on('hitl_response')
    def handle_hitl_response_event(data):
        """Handle HITL response from frontend."""
        logger.info(f"📥 Received HITL response: {data}")
        
        try:
            # Store response in server process for HTTP polling
            from ..api.system import _hitl_responses
            
            request_id = data.get('request_id')
            if request_id:
                # Convert frontend response to backend format
                action = data.get('action')
                if action == 'approve':
                    user_choice = 'approved'
                elif action == 'modify':
                    user_choice = 'request_modification'
                elif action == 'abort':
                    user_choice = 'aborted'
                else:
                    user_choice = 'approved'
                
                response_data = {
                    "user_choice": user_choice,
                    "message": f"User {action}d checkpoint",
                    "modification_instructions": data.get('modification_instructions')
                }
                
                _hitl_responses[request_id] = response_data
                logger.info(f"✅ HITL response stored for polling: {request_id}")
            
            # Also try the original handler for direct socketio communication
            from ...hierarchical_agent_framework.utils.websocket_hitl_utils import handle_hitl_response
            handle_hitl_response(data)
            
        except Exception as e:
            logger.error(f"Failed to handle HITL response: {e}")
            emit('hitl_error', {'message': f'Failed to process HITL response: {str(e)}'})
