"""
System API Routes

REST endpoints for system information and management.
"""

from flask import jsonify, make_response, request
from loguru import logger
from datetime import datetime
from flask import current_app
import os

# Add a global storage for HITL responses (in the server process)
_hitl_responses = {}

def create_system_routes(app, system_manager):
    """
    Create system-related API routes.
    
    Args:
        app: Flask application instance
        system_manager: SystemManager instance
    """
    
    @app.route('/api/system-info', methods=['GET'])
    def get_system_info():
        """Get system information and statistics."""
        try:
            info = system_manager.get_system_info()
            return jsonify(info)
        except Exception as e:
            logger.error(f"System info error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/task-graph', methods=['GET'])
    def get_task_graph_data():
        """Get current graph data."""
        try:
            display_graph = system_manager.task_graph
            if hasattr(display_graph, 'to_visualization_dict'):
                data = display_graph.to_visualization_dict()
            else:
                # Fallback: Import and use GraphSerializer directly
                from ...hierarchical_agent_framework.graph.graph_serializer import GraphSerializer
                serializer = GraphSerializer(display_graph)
                data = serializer.to_visualization_dict()
                
            response = make_response(jsonify(data))
            response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
            return response
        except Exception as e:
            logger.error(f"Task graph endpoint error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        try:
            return jsonify({
                "status": "healthy",
                "initialized": system_manager._initialized,
                "timestamp": "2024-01-01T00:00:00Z"  # You'd use datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/readiness', methods=['GET'])
    def get_system_readiness():
        """
        Get system readiness status.
        
        Returns:
            JSON response with readiness information
        """
        try:
            system_manager = current_app.system_manager
            
            readiness = {
                "ready": True,
                "components": {
                    "system_initialized": system_manager._initialized,
                    "websocket_hitl_ready": system_manager.is_websocket_hitl_ready(),
                    "cache_ready": system_manager.cache_manager is not None,
                    "execution_engine_ready": system_manager.execution_engine is not None
                },
                "websocket_hitl_status": system_manager.get_websocket_hitl_status(),
                "timestamp": datetime.now().isoformat()
            }
            
            # Overall readiness check
            if system_manager.config.execution.enable_hitl:
                readiness["ready"] = all([
                    readiness["components"]["system_initialized"],
                    readiness["components"]["websocket_hitl_ready"],
                    readiness["components"]["cache_ready"],
                    readiness["components"]["execution_engine_ready"]
                ])
            else:
                readiness["ready"] = all([
                    readiness["components"]["system_initialized"],
                    readiness["components"]["cache_ready"],
                    readiness["components"]["execution_engine_ready"]
                ])
            
            return jsonify(readiness), 200
            
        except Exception as e:
            logger.error(f"Error getting system readiness: {e}")
            return jsonify({
                "error": "Failed to get system readiness",
                "details": str(e),
                "ready": False
            }), 500

    @app.route('/api/system/hitl-debug', methods=['GET'])
    def get_hitl_debug_info():
        """Get detailed HITL debugging information"""
        try:
            # Try to import the websocket HITL utils
            try:
                from ...hierarchical_agent_framework.utils.websocket_hitl_utils import get_websocket_hitl_status
                hitl_status = get_websocket_hitl_status()
            except ImportError as e:
                hitl_status = {"error": f"WebSocket HITL utils not available: {e}"}
            
            debug_info = {
                "hitl_status": hitl_status,
                "system_hitl_ready": system_manager.is_websocket_hitl_ready(),
                "config_hitl_enabled": system_manager.config.execution.enable_hitl,
                "environment_vars": {
                    "SENTIENT_USE_WEBSOCKET_HITL": os.getenv('SENTIENT_USE_WEBSOCKET_HITL'),
                },
                "timestamp": datetime.now().isoformat()
            }
            
            return jsonify(debug_info)
            
        except Exception as e:
            logger.error(f"Error getting HITL debug info: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/system/hitl-test', methods=['POST'])
    def trigger_hitl_test():
        """Trigger a test HITL request for debugging"""
        try:
            # Try to import and use the test function
            try:
                from ...hierarchical_agent_framework.utils.websocket_hitl_utils import trigger_test_hitl_request
                success = trigger_test_hitl_request()
                message = "Test HITL request triggered" if success else "Failed to trigger test HITL request"
            except ImportError:
                # Fallback: manually create a test request
                try:
                    from ...hierarchical_agent_framework.utils.websocket_hitl_utils import _socketio_instance
                    if _socketio_instance:
                        test_request = {
                            "checkpoint_name": "ServerAPITestCheckpoint",
                            "context_message": "This is a test HITL request from the server API",
                            "data_for_review": {
                                "test": True,
                                "timestamp": datetime.now().isoformat(),
                                "source": "server_api_test"
                            },
                            "node_id": "server-api-test-node",
                            "current_attempt": 1,
                            "request_id": f"server-api-test-{int(datetime.now().timestamp())}",
                            "timestamp": datetime.now().isoformat()
                        }
                        _socketio_instance.emit('hitl_request', test_request)
                        success = True
                        message = "Test HITL request triggered via fallback method"
                    else:
                        success = False
                        message = "No socketio instance available"
                except Exception as fallback_error:
                    success = False
                    message = f"Fallback method failed: {fallback_error}"
            
            return jsonify({
                "success": success,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error triggering HITL test: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/system/hitl-request', methods=['POST'])
    def handle_hitl_request():
        """Handle HITL request via HTTP (for cross-process communication)"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400
            
            # Validate required fields
            required_fields = ['checkpoint_name', 'context_message', 'node_id', 'request_id']
            for field in required_fields:
                if field not in data:
                    return jsonify({"error": f"Missing required field: {field}"}), 400
            
            # Try to get the socketio instance and emit the request
            try:
                from ...hierarchical_agent_framework.utils.websocket_hitl_utils import _socketio_instance
                if _socketio_instance:
                    # Create the HITL request
                    hitl_request = {
                        "checkpoint_name": data['checkpoint_name'],
                        "context_message": data['context_message'],
                        "data_for_review": data.get('data_for_review'),
                        "node_id": data['node_id'],
                        "current_attempt": data.get('current_attempt', 1),
                        "request_id": data['request_id'],
                        "timestamp": data.get('timestamp', datetime.now().isoformat())
                    }
                    
                    # Emit the HITL request to frontend
                    _socketio_instance.emit('hitl_request', hitl_request)
                    logger.info(f"✅ HITL request {data['request_id']} emitted via HTTP endpoint")
                    
                    return jsonify({
                        "success": True,
                        "message": "HITL request emitted successfully",
                        "request_id": data['request_id']
                    })
                else:
                    return jsonify({
                        "success": False,
                        "error": "No socketio instance available"
                    }), 503
                
            except Exception as e:
                logger.error(f"Error emitting HITL request: {e}")
                return jsonify({
                    "success": False,
                    "error": f"Failed to emit HITL request: {str(e)}"
                }), 500
            
        except Exception as e:
            logger.error(f"Error in HITL request handler: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/system/hitl-response/<request_id>', methods=['GET'])
    def get_hitl_response(request_id):
        """Get HITL response for a specific request ID"""
        try:
            if request_id in _hitl_responses:
                response_data = _hitl_responses.pop(request_id)  # Remove after retrieving
                return jsonify({
                    "has_response": True,
                    "response": response_data,
                    "request_id": request_id
                })
            else:
                return jsonify({
                    "has_response": False,
                    "request_id": request_id
                }), 404
            
        except Exception as e:
            logger.error(f"Error getting HITL response: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/system/create-sample-traces', methods=['POST'])
    def create_sample_traces():
        """Create sample trace data for testing the tracing modal."""
        try:
            data = request.get_json()
            project_id = data.get('project_id')
            node_ids = data.get('node_ids', ['root'])
            
            if not project_id:
                return jsonify({"error": "project_id required"}), 400
            
            # Get project-specific trace manager
            project_context = project_service.get_project_execution_context(project_id)
            if not project_context:
                return jsonify({"error": f"Project {project_id} not found"}), 404
            
            trace_manager = project_context.trace_manager
            
            created_traces = []
            for node_id in node_ids:
                # Create trace
                trace = trace_manager.create_trace(node_id, f"Sample goal for {node_id}")
                
                # Add atomization stage
                atomization_stage = trace_manager.start_stage(
                    node_id=node_id,
                    stage_name="atomization",
                    agent_name="sample_atomizer",
                    adapter_name="AtomizerAdapter"
                )
                trace_manager.complete_stage(
                    node_id=node_id,
                    stage_name="atomization",
                    output_data="Determined task needs planning"
                )
                
                # Add planning stage
                planning_stage = trace_manager.start_stage(
                    node_id=node_id,
                    stage_name="planning", 
                    agent_name="sample_planner",
                    adapter_name="PlannerAdapter"
                )
                trace_manager.complete_stage(
                    node_id=node_id,
                    stage_name="planning",
                    output_data="Created detailed plan with sub-tasks"
                )
                
                # Add execution stage
                execution_stage = trace_manager.start_stage(
                    node_id=node_id,
                    stage_name="execution",
                    agent_name="sample_executor", 
                    adapter_name="ExecutorAdapter"
                )
                trace_manager.complete_stage(
                    node_id=node_id,
                    stage_name="execution",
                    output_data="Successfully executed task"
                )
                
                created_traces.append({
                    "node_id": node_id,
                    "stages": len(trace.stages),
                    "stage_names": [s.stage_name for s in trace.stages]
                })
            
            # Save traces for the project
            trace_manager.save_project_traces(project_id)
            
            return jsonify({
                "success": True,
                "message": f"Created sample traces for {len(node_ids)} nodes",
                "traces": created_traces
            })
            
        except Exception as e:
            logger.error(f"Error creating sample traces: {e}")
            return jsonify({"error": str(e)}), 500
