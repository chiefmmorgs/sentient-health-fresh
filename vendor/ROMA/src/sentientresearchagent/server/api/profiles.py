"""
Profile Management API Routes

REST endpoints for managing agent profiles.
"""

from flask import jsonify, request
from loguru import logger
from typing import Dict, Any

def create_profile_routes(app, system_manager):
    """
    Create profile management API routes.
    
    Args:
        app: Flask application instance
        system_manager: SystemManager instance
    """
    
    @app.route('/api/profiles', methods=['GET'])
    def get_profiles():
        """Get all available agent profiles with current profile marked."""
        try:
            profiles_data = system_manager.get_profiles_with_current()
            return jsonify(profiles_data)
        except Exception as e:
            logger.error(f"Profiles API error: {e}")
            return jsonify({
                "current_profile": None,
                "profiles": [],
                "total_count": 0,
                "error": str(e)
            }), 500
    
    @app.route('/api/profiles/<profile_name>', methods=['GET'])
    def get_profile_details(profile_name: str):
        """Get detailed information about a specific profile."""
        try:
            details = system_manager.get_profile_details(profile_name)
            current_profile = system_manager.get_current_profile()
            details['is_current'] = (profile_name == current_profile)
            
            return jsonify(details)
        except Exception as e:
            logger.error(f"Failed to get profile details for {profile_name}: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/profiles/<profile_name>/switch', methods=['POST'])
    def switch_profile(profile_name: str):
        """Switch to a different agent profile."""
        try:
            logger.info(f"🔄 API request to switch to profile: {profile_name}")
            
            # Perform the switch
            result = system_manager.switch_profile(profile_name)
            
            if result.get("success"):
                logger.info(f"✅ Successfully switched to profile: {profile_name}")
                return jsonify(result)
            else:
                logger.error(f"❌ Failed to switch to profile: {profile_name}")
                return jsonify(result), 400
                
        except Exception as e:
            logger.error(f"Profile switch error for {profile_name}: {e}")
            return jsonify({
                "success": False,
                "error": str(e),
                "profile": profile_name
            }), 500
    
    @app.route('/api/profiles/current', methods=['GET'])
    def get_current_profile():
        """Get information about the currently active profile."""
        try:
            current_profile = system_manager.get_current_profile()
            
            if current_profile:
                details = system_manager.get_profile_details(current_profile)
                details['is_current'] = True
                return jsonify(details)
            else:
                return jsonify({
                    "error": "No profile currently active",
                    "current_profile": None
                }), 404
                
        except Exception as e:
            logger.error(f"Failed to get current profile: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/profiles/validate/<profile_name>', methods=['GET'])
    def validate_profile(profile_name: str):
        """Validate a specific profile without switching to it."""
        try:
            from ....hierarchical_agent_framework.agent_configs.registry_integration import validate_profile
            
            validation = validate_profile(profile_name)
            return jsonify({
                "profile": profile_name,
                "validation": validation,
                "is_valid": validation.get("blueprint_valid", False)
            })
            
        except Exception as e:
            logger.error(f"Profile validation error for {profile_name}: {e}")
            return jsonify({
                "profile": profile_name,
                "error": str(e),
                "is_valid": False
            }), 500 