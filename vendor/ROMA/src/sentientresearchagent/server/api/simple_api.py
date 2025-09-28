"""
Simple API Routes

REST endpoints for the simplified API interface.
"""

from flask import jsonify, request
from loguru import logger
from datetime import datetime
import uuid

from ..utils.validation import RequestValidator


def create_simple_api_routes(app, system_manager):
    """
    Create Simple API routes.
    
    Args:
        app: Flask application instance
        system_manager: SystemManager instance
    """
    
    @app.route('/api/simple/execute', methods=['POST'])
    def simple_execute():
        """Simple API endpoint for direct goal execution."""
        try:
            # Validate request
            is_valid, error_msg, data = RequestValidator.validate_json_required(['goal'])
            if not is_valid:
                return jsonify({"error": error_msg}), 400
            
            goal = data['goal']
            options = data.get('options', {})
            
            # Default to HITL disabled for Simple API unless explicitly requested
            enable_hitl = data.get('enable_hitl', False)
            if enable_hitl:
                options['enable_hitl'] = True
            
            # Validate goal
            goal_valid, goal_error = RequestValidator.validate_project_goal(goal)
            if not goal_valid:
                return jsonify({"error": goal_error}), 400
            
            # Get simple agent instance (which has HITL disabled by default)
            agent = system_manager.get_simple_agent()
            if not agent:
                return jsonify({"error": "Failed to initialize SimpleSentientAgent"}), 500
            
            logger.info(f"🎯 Simple API execution: {goal[:100]}... (HITL: {enable_hitl})")
            
            # Execute using simple API
            result = agent.execute(goal, **options)
            
            # Add timestamp for tracking
            result['timestamp'] = datetime.now().isoformat()
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Simple execute error: {e}")
            return jsonify({
                "execution_id": f"error_{uuid.uuid4().hex[:8]}",
                "goal": data.get('goal', 'unknown') if 'data' in locals() else 'unknown',
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }), 500
    
    @app.route('/api/simple/research', methods=['POST'])
    def simple_research():
        """Convenience endpoint for quick research tasks."""
        try:
            # Validate request
            is_valid, error_msg, data = RequestValidator.validate_json_required(['topic'])
            if not is_valid:
                return jsonify({"error": error_msg}), 400
            
            topic = data['topic']
            options = data.get('options', {})
            enable_hitl = data.get('enable_hitl', False)  # Default to False
            
            logger.info(f"🔍 Simple research: {topic[:100]}... (HITL: {enable_hitl})")
            
            # Use the convenience function
            from ...framework_entry import quick_research
            result = quick_research(topic, enable_hitl=enable_hitl, **options)
            
            return jsonify({
                "topic": topic,
                "result": result,
                "timestamp": datetime.now().isoformat(),
                "status": "completed",
                "hitl_enabled": enable_hitl
            })
            
        except Exception as e:
            logger.error(f"Simple research error: {e}")
            return jsonify({
                "topic": data.get('topic', 'unknown') if 'data' in locals() else 'unknown',
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }), 500
    
    @app.route('/api/simple/analysis', methods=['POST'])
    def simple_analysis():
        """Convenience endpoint for quick analysis tasks."""
        try:
            # Validate request
            is_valid, error_msg, data = RequestValidator.validate_json_required(['data_description'])
            if not is_valid:
                return jsonify({"error": error_msg}), 400
            
            data_description = data['data_description']
            options = data.get('options', {})
            enable_hitl = data.get('enable_hitl', False)  # Default to False
            
            logger.info(f"📊 Simple analysis: {data_description[:100]}... (HITL: {enable_hitl})")
            
            # Use the convenience function
            from ...framework_entry import quick_analysis
            result = quick_analysis(data_description, enable_hitl=enable_hitl, **options)
            
            return jsonify({
                "data_description": data_description,
                "result": result,
                "timestamp": datetime.now().isoformat(),
                "status": "completed",
                "hitl_enabled": enable_hitl
            })
            
        except Exception as e:
            logger.error(f"Simple analysis error: {e}")
            return jsonify({
                "data_description": data.get('data_description', 'unknown') if 'data' in locals() else 'unknown',
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }), 500
    
    @app.route('/api/simple/status', methods=['GET'])
    def simple_api_status():
        """Get status of the Simple API system."""
        try:
            agent = system_manager.get_simple_agent()
            
            # Check framework availability
            try:
                from ...framework_entry import FRAMEWORK_AVAILABLE
            except ImportError:
                FRAMEWORK_AVAILABLE = False
            
            return jsonify({
                "framework_available": FRAMEWORK_AVAILABLE,
                "simple_agent_ready": agent is not None,
                "config_loaded": system_manager.config is not None,
                "endpoints": [
                    "/api/simple/execute",
                    "/api/simple/research", 
                    "/api/simple/analysis",
                    "/api/simple/stream"
                ],
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Simple API status error: {e}")
            return jsonify({
                "framework_available": False,
                "simple_agent_ready": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }), 500
