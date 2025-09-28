from flask_socketio import emit
from loguru import logger


def create_websocket_events(socketio, system_manager, project_service, execution_service):
    """
    Create WebSocket event handlers.
    
    Args:
        socketio: SocketIO instance
        system_manager: SystemManager instance
        project_service: ProjectService instance
        execution_service: ExecutionService instance
    """
    
    # ... existing events ...
    
    @socketio.on('switch_profile')
    def handle_switch_profile(data):
        """Handle profile switching via WebSocket."""
        try:
            profile_name = data.get('profile_name')
            if not profile_name:
                emit('profile_switch_error', {
                    'error': 'Profile name is required'
                })
                return
            
            logger.info(f"🔄 WebSocket request to switch to profile: {profile_name}")
            
            # Perform the switch
            result = system_manager.switch_profile(profile_name)
            
            if result.get("success"):
                # Broadcast the profile change to all connected clients
                socketio.emit('profile_changed', {
                    'profile': profile_name,
                    'profile_details': result.get('profile_details'),
                    'system_info': result.get('system_info')
                })
                
                # Send success response to the requesting client
                emit('profile_switch_success', result)
                
                logger.info(f"✅ Profile switched to {profile_name} via WebSocket")
            else:
                emit('profile_switch_error', result)
                logger.error(f"❌ Failed to switch profile via WebSocket: {result}")
                
        except Exception as e:
            logger.error(f"WebSocket profile switch error: {e}")
            emit('profile_switch_error', {
                'error': str(e)
            })
    
    @socketio.on('get_profiles')
    def handle_get_profiles():
        """Get available profiles via WebSocket."""
        try:
            profiles = system_manager.get_available_profiles()
            current_profile = system_manager.get_current_profile()
            
            # Get details for each profile
            profile_details = []
            for profile_name in profiles:
                details = system_manager.get_profile_details(profile_name)
                details['is_current'] = (profile_name == current_profile)
                profile_details.append(details)
            
            emit('profiles_list', {
                'profiles': profile_details,
                'current_profile': current_profile,
                'total_count': len(profiles)
            })
            
        except Exception as e:
            logger.error(f"WebSocket get profiles error: {e}")
            emit('profiles_error', {
                'error': str(e)
            })

    # ... rest of existing events ... 