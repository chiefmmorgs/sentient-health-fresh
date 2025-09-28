"""
WebSocket-based Human-in-the-Loop utilities
"""
import asyncio
import uuid
import os
import requests
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Global reference to the socketio instance
_socketio_instance = None

# Global storage for pending HITL requests
_pending_requests = {}

# Global timeout setting (will be set by the system)
_hitl_timeout_seconds = 1800.0  # Default 30 minutes, but will be overridden

# Global flag to track if WebSocket HITL is ready
_websocket_hitl_ready = False

def set_socketio_instance(socketio):
    """Set the global socketio instance for HITL communication"""
    global _socketio_instance, _websocket_hitl_ready
    _socketio_instance = socketio
    _websocket_hitl_ready = True
    logger.info("✅ WebSocket HITL: socketio instance registered and ready")
    
    # AGGRESSIVE DEBUGGING: Verify state immediately
    logger.info(f"🔍 HITL State After Setup:")
    logger.info(f"   - _websocket_hitl_ready: {_websocket_hitl_ready}")
    logger.info(f"   - _socketio_instance: {_socketio_instance is not None}")
    logger.info(f"   - is_websocket_hitl_ready(): {is_websocket_hitl_ready()}")

def set_hitl_timeout(timeout_seconds: float):
    """Set the HITL timeout from configuration"""
    global _hitl_timeout_seconds
    _hitl_timeout_seconds = timeout_seconds
    logger.info(f"WebSocket HITL: timeout set to {timeout_seconds} seconds")

def is_websocket_hitl_ready() -> bool:
    """Check if WebSocket HITL is ready for use"""
    global _websocket_hitl_ready, _socketio_instance
    return _websocket_hitl_ready and _socketio_instance is not None

def check_connected_clients():
    """Check if there are any connected clients"""
    global _socketio_instance
    if not _socketio_instance:
        return 0
    
    try:
        if hasattr(_socketio_instance.server, 'manager') and hasattr(_socketio_instance.server.manager, 'rooms'):
            rooms = _socketio_instance.server.manager.rooms
            if '/' in rooms:
                return len(rooms['/'])
        return 0
    except Exception as e:
        logger.error(f"Error checking connected clients: {e}")
        return 0

async def wait_for_websocket_hitl_ready(max_wait_seconds: float = 30.0) -> bool:
    """
    Wait for WebSocket HITL to be ready.
    
    Args:
        max_wait_seconds: Maximum time to wait for WebSocket HITL to be ready
        
    Returns:
        True if WebSocket HITL is ready, False if timeout
    """
    wait_interval = 0.5
    waited = 0.0
    
    logger.info(f"⏳ Waiting for WebSocket HITL to be ready (max {max_wait_seconds}s)...")
    
    while not is_websocket_hitl_ready() and waited < max_wait_seconds:
        await asyncio.sleep(wait_interval)
        waited += wait_interval
        
        if waited % 5.0 < wait_interval:  # Log every 5 seconds
            logger.info(f"⏳ Still waiting for WebSocket HITL... ({waited:.1f}s/{max_wait_seconds}s)")
    
    if is_websocket_hitl_ready():
        logger.info(f"✅ WebSocket HITL ready after {waited:.1f}s")
        return True
    else:
        logger.error(f"❌ WebSocket HITL not ready after {max_wait_seconds}s timeout")
        return False

async def websocket_human_review(
    checkpoint_name: str,
    context_message: str,
    data_for_review: Optional[Any] = None,
    node_id: Optional[str] = "N/A",
    current_attempt: int = 1
) -> Dict[str, Any]:
    """
    WebSocket-based human review that broadcasts HITL requests to frontend
    """
    global _socketio_instance, _pending_requests, _hitl_timeout_seconds
    
    logger.info(f"🤔 HITL WebSocket: Broadcasting checkpoint '{checkpoint_name}' for node {node_id}")
    
    # Check if socketio instance is available
    if _socketio_instance is None:
        logger.warning("🚨 HITL WebSocket: No socketio instance available!")
        logger.info("🔄 HITL WebSocket: Using HTTP fallback with polling...")
        
        try:
            import requests
            import os
            
            # Get server URL from environment or use default
            server_host = os.getenv('SENTIENT_SERVER_HOST', 'localhost')
            server_port = os.getenv('SENTIENT_SERVER_PORT', '5000')
            server_url = f"http://{server_host}:{server_port}"
            
            # Create HITL request
            request_id = str(uuid.uuid4())
            hitl_request_data = {
                "checkpoint_name": checkpoint_name,
                "context_message": context_message,
                "data_for_review": data_for_review,
                "node_id": node_id,
                "current_attempt": current_attempt,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
            
            # Send HTTP request to server
            logger.info(f"📡 Sending HITL request via HTTP to {server_url}")
            response = requests.post(
                f"{server_url}/api/system/hitl-request",
                json=hitl_request_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✅ HITL request sent via HTTP fallback successfully")
                
                # Now poll for response
                actual_timeout = max(_hitl_timeout_seconds, 3600)  # At least 1 hour
                start_time = datetime.now()
                poll_interval = 2  # Poll every 2 seconds
                
                logger.info(f"⏳ Polling for user response to HITL request {request_id} (timeout: {actual_timeout}s)...")
                
                while True:
                    # Check if we've exceeded the timeout
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed >= actual_timeout:
                        logger.warning(f"⏰ HITL request {request_id} timed out after {actual_timeout} seconds")
                        return {
                            "user_choice": "timeout",
                            "message": f"HITL request timed out after {actual_timeout} seconds",
                            "modification_instructions": None
                        }
                    
                    # Poll for response
                    try:
                        poll_response = requests.get(
                            f"{server_url}/api/system/hitl-response/{request_id}",
                            timeout=5
                        )
                        
                        if poll_response.status_code == 200:
                            response_data = poll_response.json()
                            if response_data.get('has_response'):
                                logger.info(f"✅ Received HITL response via HTTP polling: {response_data['response']}")
                                return response_data['response']
                        elif poll_response.status_code == 404:
                            # No response yet, continue polling
                            pass
                        else:
                            logger.warning(f"⚠️ Unexpected response from polling: {poll_response.status_code}")
                            
                    except requests.exceptions.RequestException as e:
                        logger.warning(f"⚠️ Error polling for response: {e}")
                    
                    # Wait before next poll
                    await asyncio.sleep(poll_interval)
                    
            else:
                logger.error(f"❌ HTTP fallback failed: {response.status_code} - {response.text}")
                return {
                    "user_choice": "approved",
                    "message": f"Auto-approved checkpoint '{checkpoint_name}' (HTTP fallback failed: {response.status_code})",
                    "modification_instructions": None
                }
                
        except requests.exceptions.ConnectionError:
            logger.error("❌ HTTP fallback failed: Could not connect to server")
            return {
                "user_choice": "approved",
                "message": f"Auto-approved checkpoint '{checkpoint_name}' (Server not reachable)",
                "modification_instructions": None
            }
        except Exception as e:
            logger.error(f"❌ HTTP fallback error: {e}")
            return {
                "user_choice": "approved",
                "message": f"Auto-approved checkpoint '{checkpoint_name}' (HTTP fallback error: {str(e)})",
                "modification_instructions": None
            }
    
    # If we reach here, socketio instance is available
    logger.info("✅ HITL WebSocket: SocketIO instance found, proceeding with direct emission")
    
    # Check if there are connected clients
    connected_clients = check_connected_clients()
    logger.info(f"🔍 Connected clients: {connected_clients}")
    
    if connected_clients == 0:
        logger.warning("⚠️ No connected clients, but proceeding with HITL request")
    
    # Create HITL request
    request_id = str(uuid.uuid4())
    hitl_request = {
        "checkpoint_name": checkpoint_name,
        "context_message": context_message,
        "data_for_review": data_for_review,
        "node_id": node_id,
        "current_attempt": current_attempt,
        "request_id": request_id,
        "timestamp": datetime.now().isoformat()
    }
    
    logger.info(f"📋 HITL Request Created: {request_id}")
    
    # Store the request for response handling
    response_future = asyncio.Future()
    _pending_requests[request_id] = response_future
    
    try:
        logger.info("📡 Emitting HITL request to frontend")
        _socketio_instance.emit('hitl_request', hitl_request)
        logger.info("✅ HITL request emitted successfully")
        
        # Wait for response with configured timeout
        actual_timeout = max(_hitl_timeout_seconds, 3600)  # At least 1 hour
        
        try:
            logger.info(f"⏳ Waiting for user response to HITL request {request_id} (timeout: {actual_timeout}s)...")
            
            # Periodically re-emit the request in case of connection drops
            async def periodic_reemit():
                emit_count = 0
                while not response_future.done():
                    await asyncio.sleep(30)  # Re-emit every 30 seconds
                    if not response_future.done():
                        emit_count += 1
                        current_clients = check_connected_clients()
                        logger.info(f"🔄 Re-emitting HITL request {request_id} (attempt {emit_count}, clients: {current_clients})")
                        try:
                            _socketio_instance.emit('hitl_request', hitl_request)
                            logger.info(f"✅ Re-emission {emit_count} successful")
                        except Exception as e:
                            logger.error(f"❌ Error re-emitting HITL request: {e}")
            
            # Start the periodic re-emit task
            reemit_task = asyncio.create_task(periodic_reemit())
            
            try:
                response = await asyncio.wait_for(response_future, timeout=actual_timeout)
                logger.info(f"✅ Received HITL response: {response}")
                return response
            finally:
                # Cancel the re-emit task
                reemit_task.cancel()
                try:
                    await reemit_task
                except asyncio.CancelledError:
                    pass
                    
        except asyncio.TimeoutError:
            logger.warning(f"⏰ HITL request {request_id} timed out after {actual_timeout} seconds")
            return {
                "user_choice": "timeout",
                "message": f"HITL request timed out after {actual_timeout} seconds",
                "modification_instructions": None
            }
        
    except Exception as e:
        logger.error(f"❌ Error during HITL request: {e}")
        logger.exception("Full error traceback:")
        return {
            "user_choice": "error",
            "message": f"Error during HITL request: {e}",
            "modification_instructions": None
        }
    finally:
        # Clean up
        _pending_requests.pop(request_id, None)
        logger.info(f"🧹 Cleaned up HITL request {request_id}")

def handle_hitl_response(response_data: Dict[str, Any]):
    """Handle HITL response from frontend"""
    global _pending_requests
    
    request_id = response_data.get('request_id')
    if not request_id:
        logger.error("❌ HITL response missing request_id")
        return
    
    future = _pending_requests.get(request_id)
    if not future:
        logger.warning(f"⚠️ No pending request found for ID: {request_id}")
        return
    
    action = response_data.get('action')
    modification_instructions = response_data.get('modification_instructions')
    
    # Convert frontend action to backend format
    if action == 'approve':
        user_choice = 'approved'
        message = f"User approved checkpoint '{response_data.get('checkpoint_name')}'"
    elif action == 'modify':
        user_choice = 'request_modification'
        message = f"User requested modification for '{response_data.get('checkpoint_name')}'"
    elif action == 'abort':
        user_choice = 'aborted'
        message = f"User aborted checkpoint '{response_data.get('checkpoint_name')}'"
    else:
        user_choice = 'approved'
        message = f"Unknown action '{action}', defaulting to approved"
    
    result = {
        "user_choice": user_choice,
        "message": message,
        "modification_instructions": modification_instructions
    }
    
    # Resolve the future with the response
    if not future.done():
        future.set_result(result)
        logger.info(f"✅ HITL response processed for request {request_id}: {user_choice}")

def get_websocket_hitl_status() -> Dict[str, Any]:
    """Get the current status of WebSocket HITL"""
    global _socketio_instance, _websocket_hitl_ready, _pending_requests
    
    return {
        "ready": _websocket_hitl_ready,
        "socketio_available": _socketio_instance is not None,
        "connected_clients": check_connected_clients(),
        "pending_requests": len(_pending_requests),
        "timeout_seconds": _hitl_timeout_seconds
    }