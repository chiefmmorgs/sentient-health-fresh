"""
WebSocket Event Handlers

Main WebSocket event handlers for the application.
"""

import threading
from flask_socketio import emit
from loguru import logger
from datetime import datetime

from ..utils.validation import RequestValidator
# TraceManager is now accessed via project-specific instances instead of global singleton


def register_websocket_events(socketio, project_service, execution_service):
    """
    Register WebSocket event handlers.
    
    Args:
        socketio: SocketIO instance
        project_service: ProjectService instance
        execution_service: ExecutionService instance
    """
    
    @socketio.on('connect')
    def handle_connect(auth):
        """Handle client connection."""
        logger.info('👋 Client connected')
        try:
            # Send initial state
            handle_request_initial_state()
        except Exception as e:
            logger.error(f"Error in connect handler: {e}")
    
    @socketio.on('disconnect')
    def handle_disconnect(auth=None):
        """Handle client disconnection."""
        try:
            logger.info('👋 Client disconnected')
            # Don't emit anything on disconnect - client is already gone
            # Just log and clean up any resources if needed
        except Exception as e:
            logger.error(f"Error in disconnect handler: {e}")
    
    @socketio.on('request_initial_state')
    def handle_request_initial_state():
        """Send initial state when frontend connects."""
        logger.info('📋 Client requested initial state')
        try:
            # Send project list
            projects_data = project_service.get_all_projects()
            emit('projects_list', projects_data)
            
            # If there's a current project, send its graph
            current_project = project_service.project_manager.get_current_project()
            if current_project:
                project_service.load_project_into_graph(current_project.id)
            else:
                # Send empty graph by triggering broadcast
                if hasattr(project_service, 'broadcast_callback') and project_service.broadcast_callback:
                    project_service.broadcast_callback()
                
        except Exception as e:
            logger.error(f"Error sending initial state: {e}")
            # Only emit error if we're still connected
            try:
                emit('error', {'message': 'Failed to load initial state'})
            except:
                pass  # Client might have disconnected
    
    @socketio.on('start_project')
    def handle_start_project(data):
        """Handle project start request."""
        logger.info(f"🚀 Received start_project: {data}")
        try:
            # Validate required fields
            if not data or 'project_goal' not in data:
                emit('error', {'message': 'project_goal not provided'})
                return
            
            project_goal = data['project_goal']
            max_steps = data.get('max_steps', 250)  # Should get from config
            project_id = data.get('project_id')  # Optional project ID
            
            # Validate goal
            goal_valid, goal_error = RequestValidator.validate_project_goal(project_goal)
            if not goal_valid:
                emit('error', {'message': goal_error})
                return
            
            # Validate max_steps
            steps_valid, steps_error, validated_steps = RequestValidator.validate_max_steps(max_steps)
            if not steps_valid:
                emit('error', {'message': steps_error})
                return
            
            # Create or use existing project
            if project_id:
                project_data = project_service.get_project(project_id)
                if not project_data:
                    emit('error', {'message': 'Project not found'})
                    return
                project_dict = project_data['project']
            else:
                project_dict = project_service.create_project(project_goal, validated_steps)
                project_id = project_dict['id']
            
            logger.info(f"🚀 Starting project: {project_id} - {project_goal}")
            
            # Start in background thread
            success = execution_service.start_project_execution(project_id, project_goal, validated_steps)
            
            if not success:
                emit('error', {'message': 'Failed to start project execution'})
                return
            
            emit('project_started', {
                'message': f"Project started: {project_goal}",
                'project': project_dict
            })
            logger.info("✅ Project started response sent")
            
        except Exception as e:
            logger.error(f"Error in start_project handler: {e}")
            emit('error', {'message': f'Server error: {str(e)}'})
    
    @socketio.on('simple_execute_stream')
    def handle_simple_execute_stream(data):
        """WebSocket handler for streaming simple API execution."""
        logger.info(f"🌊 Received simple_execute_stream: {data}")
        try:
            # Check framework availability
            try:
                from ...framework_entry import FRAMEWORK_AVAILABLE
            except ImportError:
                FRAMEWORK_AVAILABLE = False
                
            if not FRAMEWORK_AVAILABLE:
                emit('simple_execution_error', {'message': 'Framework components not available'})
                return
                
            goal = data.get('goal')
            if not goal:
                emit('simple_execution_error', {'message': 'goal not provided'})
                return
            
            # Validate goal
            goal_valid, goal_error = RequestValidator.validate_project_goal(goal)
            if not goal_valid:
                emit('simple_execution_error', {'message': goal_error})
                return
            
            options = data.get('options', {})
            
            # Start streaming execution in background thread
            thread = threading.Thread(
                target=_run_simple_streaming_execution, 
                args=(socketio, goal, options),
                daemon=True
            )
            thread.start()
            
            emit('simple_execution_started', {
                'message': f"Simple execution started: {goal[:50]}...",
                'goal': goal
            })
            
        except Exception as e:
            logger.error(f"Simple execute stream error: {e}")
            emit('simple_execution_error', {'message': f'Error: {str(e)}'})
    
    @socketio.on('switch_project')
    def handle_switch_project(data):
        """Handle project switching via WebSocket."""
        logger.info(f"🔄 WebSocket request to switch project: {data}")
        try:
            project_id = data.get('project_id')
            if not project_id:
                emit('project_switch_error', {
                    'error': 'project_id is required'
                })
                return
            
            # Validate project exists
            project = project_service.project_manager.get_project(project_id)
            if not project:
                emit('project_switch_error', {
                    'error': f'Project {project_id} not found'
                })
                return
            
            logger.info(f"🔄 Switching to project: {project_id}")
            
            # Perform the switch
            success = project_service.switch_project(project_id)
            
            if success:
                # Get the switched project's data
                project_data = project_service.get_project_display_data(project_id)
                project_data['current_project'] = project.to_dict()
                
                # Send success response to the requesting client
                emit('project_switch_success', {
                    'project_id': project_id,
                    'project_data': project_data,
                    'message': f'Switched to project: {project.title}'
                })
                
                # Broadcast the project change to all connected clients
                socketio.emit('project_switched', {
                    'project_id': project_id,
                    'project_data': project_data,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Also send regular graph update for compatibility
                socketio.emit('task_graph_update', project_data)
                
                logger.info(f"✅ Project switched to {project_id} via WebSocket")
            else:
                emit('project_switch_error', {
                    'error': f'Failed to switch to project {project_id}'
                })
                logger.error(f"❌ Failed to switch project via WebSocket: {project_id}")
                
        except Exception as e:
            logger.error(f"WebSocket project switch error: {e}")
            emit('project_switch_error', {
                'error': str(e)
            })
    
    @socketio.on('restore_project_state')
    def handle_restore_project_state(data):
        """Handle project state restoration request."""
        logger.info(f"🔄 WebSocket request to restore project state: {data}")
        try:
            project_id = data.get('project_id')
            if not project_id:
                emit('project_restore_error', {
                    'error': 'project_id is required'
                })
                return
            
            # Get project data
            project = project_service.project_manager.get_project(project_id)
            if not project:
                emit('project_restore_error', {
                    'error': f'Project {project_id} not found'
                })
                return
            
            # Get project display data
            project_data = project_service.get_project_display_data(project_id)
            project_data['current_project'] = project.to_dict()
            
            # Send restored data
            emit('project_restored', project_data)
            
            logger.info(f"✅ Project state restored for {project_id}")
            
        except Exception as e:
            logger.error(f"WebSocket project restore error: {e}")
            emit('project_restore_error', {
                'error': str(e)
            })
    
    @socketio.on('auto_save_project')
    def handle_auto_save_project(data):
        """
        Handle automatic project saving from frontend.
        This now uses the server's state as the source of truth.
        """
        try:
            project_id = data.get('project_id')
            if not project_id:
                logger.warning("Auto-save request missing project_id")
                return

            logger.debug(f"💾 Auto-saving project data for: {project_id}")

            # THE FIX: Get the authoritative state from the server, don't trust the client's data.
            project_data = project_service.get_project_display_data(project_id)

            if not project_data or not project_data.get('all_nodes'):
                logger.warning(f"💾 Auto-save skipped for {project_id}: No nodes found in server state.")
                return

            # Save the authoritative state
            project_service.save_project_state_async(project_id, project_data)
            
            # Also save as results for persistence
            results_package = {
                "project_id": project_id,
                "saved_at": datetime.now().isoformat(),
                "basic_state": project_data, # Use basic_state to be consistent
                "auto_saved": True,
                "metadata": {
                    "total_nodes": len(project_data.get('all_nodes', {})),
                    "project_goal": project_data.get('overall_project_goal'),
                    "completion_status": "auto_saved"
                }
            }
            project_service.save_project_results(project_id, results_package)
            
            logger.debug(f"✅ Auto-saved project using server-side state: {project_id}")
            
        except Exception as e:
            logger.error(f"Auto-save error: {e}")
    
    @socketio.on('request_project_restore')
    def handle_request_project_restore(data):
        """Handle project state restoration requests with enhanced debugging."""
        try:
            project_id = data.get('project_id')
            if not project_id:
                emit('project_restore_error', {'error': 'project_id required'})
                return

            logger.info(f"🔄 Restoring project state: {project_id}")

            # ENHANCED: Try multiple restoration sources
            restored = False
            
            # 1. Try to load comprehensive saved results first
            results = project_service.load_project_results(project_id)
            if results and (results.get('basic_state') or results.get('graph_data')):
                project_data = results.get('basic_state') or results.get('graph_data')
                project_data['project_id'] = project_id
                project_data['restored'] = True
                project_data['restored_at'] = datetime.now().isoformat()
                project_data['restored_from'] = 'comprehensive_results'
                
                node_count = len(project_data.get('all_nodes', {}))
                logger.info(f"Restoring project from comprehensive results: {node_count} nodes")

                emit('project_restored', project_data)
                logger.info(f"✅ Restored project from comprehensive results: {project_id}")
                restored = True

            # 2. Fallback to basic project state
            if not restored:
                project_state = project_service.project_manager.load_project_state(project_id)
                if project_state:
                    project_state['project_id'] = project_id
                    project_state['restored'] = True
                    project_state['restored_at'] = datetime.now().isoformat()
                    project_state['restored_from'] = 'basic_state'

                    node_count = len(project_state.get('all_nodes', {}))
                    logger.info(f"Restoring project from basic state: {node_count} nodes")

                    emit('project_restored', project_state)
                    logger.info(f"✅ Restored project from basic state: {project_id}")
                    restored = True

            if not restored:
                emit('project_restore_error', {'error': f'No saved state found for project {project_id}'})
                logger.warning(f"❌ No saved state found for project: {project_id}")

        except Exception as e:
            logger.error(f"Project restore error: {e}")
    
    # NEW: Manual save trigger
    @socketio.on('force_save_project')
    def handle_force_save_project(data):
        """Force save current project state - useful for debugging."""
        try:
            project_id = data.get('project_id')
            if not project_id:
                emit('save_error', {'error': 'project_id required'})
                return

            logger.info(f"🚨 FORCE SAVE - Manually saving project: {project_id}")
            
            # Get current project data
            project_data = project_service.get_project_display_data(project_id)
            
            # Save comprehensive results
            results_package = {
                'basic_state': project_data,
                'saved_at': datetime.now().isoformat(),
                'manual_save': True,
                'metadata': {
                    'node_count': len(project_data.get('all_nodes', {})),
                    'project_goal': project_data.get('overall_project_goal'),
                    'completion_status': 'manual_save'
                }
            }
            
            success = project_service.save_project_results(project_id, results_package)
            
            if success:
                emit('save_success', {
                    'project_id': project_id,
                    'message': 'Project saved successfully',
                    'node_count': len(project_data.get('all_nodes', {}))
                })
                logger.info(f"✅ FORCE SAVE - Successfully saved project: {project_id}")
            else:
                emit('save_error', {'error': 'Failed to save project'})
                logger.error(f"❌ FORCE SAVE - Failed to save project: {project_id}")

        except Exception as e:
            logger.error(f"Force save error: {e}")
            emit('save_error', {'error': str(e)})
    
    @socketio.on('start_project_execution')
    def handle_start_project_execution(data):
        """Handle project re-execution requests."""
        try:
            project_id = data.get('project_id')
            goal = data.get('goal')
            max_steps = data.get('max_steps', 250)
            
            if not project_id or not goal:
                emit('execution_error', {'error': 'project_id and goal are required'})
                return
            
            logger.info(f"🚨 RE-EXECUTION - Starting execution for project: {project_id}")
            logger.info(f"🚨 RE-EXECUTION - Goal: {goal}")
            
            # Clear any existing state for this project
            project_service.project_manager.update_project(project_id, status='running', node_count=0)
            
            # Start execution
            success = execution_service.start_project_execution(project_id, goal, max_steps)
            
            if success:
                emit('execution_started', {
                    'project_id': project_id,
                    'message': f'Re-execution started for project {project_id}',
                    'goal': goal,
                    'max_steps': max_steps
                })
                logger.info(f"✅ RE-EXECUTION - Started successfully for project: {project_id}")
            else:
                emit('execution_error', {
                    'error': f'Failed to start execution for project {project_id}'
                })
                logger.error(f"❌ RE-EXECUTION - Failed to start for project: {project_id}")
            
        except Exception as e:
            logger.error(f"Re-execution error: {e}")
            emit('execution_error', {'error': str(e)})
    
    @socketio.on_error_default
    def default_error_handler(e):
        """Default error handler for WebSocket events."""
        logger.error(f"SocketIO error: {e}")
        # Don't emit anything here - might cause more connection issues

    # NEW: Tracing endpoints with persistence support
    @socketio.on('request_node_trace')
    def handle_request_node_trace(data):
        """Handle request for node processing trace."""
        logger.info(f"🔍 WebSocket request for node trace: {data}")
        try:
            node_id = data.get('node_id')
            project_id = data.get('project_id')
            
            if not node_id:
                emit('node_trace_error', {'error': 'node_id is required'})
                return
            
            if not project_id:
                emit('node_trace_error', {'error': 'project_id is required'})
                return
            
            # Get project-specific trace manager
            project_context = project_service.get_project_execution_context(project_id)
            if not project_context:
                emit('node_trace_error', {'error': f'Project {project_id} not found'})
                return
            
            trace_manager = project_context.trace_manager
            
            # ENHANCED: Debug trace manager state
            debug_state = trace_manager.debug_trace_state()
            logger.info(f"🔍 TRACE DEBUG: Current state: {debug_state}")
            
            # ENHANCED: Check if we have any traces at all
            all_traces = trace_manager.get_all_traces()
            logger.info(f"🔍 TRACE DEBUG: Total traces in memory: {len(all_traces)}")
            for trace in all_traces:
                logger.info(f"🔍 TRACE DEBUG: - Node {trace.node_id}: {len(trace.stages)} stages: {[s.stage_name for s in trace.stages]}")
            
            # ENHANCED: Try to load project traces if project_id provided
            if project_id:
                logger.info(f"🔍 TRACE: Attempting to load project traces for {project_id}")
                
                # Check if traces directory exists
                traces_dir = trace_manager.traces_dir / project_id
                logger.info(f"🔍 TRACE: Looking for traces in: {traces_dir}")
                logger.info(f"🔍 TRACE: Directory exists: {traces_dir.exists()}")
                
                if traces_dir.exists():
                    trace_files = list(traces_dir.glob("trace_*.json"))
                    logger.info(f"🔍 TRACE: Found {len(trace_files)} trace files: {[f.name for f in trace_files]}")
                    
                    # Try to load specific trace file
                    expected_trace_file = traces_dir / f"trace_{node_id}.json"
                    logger.info(f"🔍 TRACE: Looking for {expected_trace_file}")
                    logger.info(f"🔍 TRACE: File exists: {expected_trace_file.exists()}")
                    
                    if expected_trace_file.exists():
                        try:
                            with open(expected_trace_file, 'r') as f:
                                trace_content = f.read()
                                logger.info(f"🔍 TRACE: File content length: {len(trace_content)} chars")
                                logger.info(f"🔍 TRACE: File content preview: {trace_content[:200]}...")
                        except Exception as e:
                            logger.error(f"🔍 TRACE: Error reading trace file: {e}")
                
                trace_manager.load_project_traces(project_id)
            
            # Get trace for the node
            trace = trace_manager.get_trace_for_node(node_id)
            if trace:
                logger.info(f"🔍 TRACE: Found trace for {node_id}: {len(trace.stages)} stages")
                for i, stage in enumerate(trace.stages):
                    logger.info(f"🔍 TRACE: Stage {i+1}: {stage.stage_name} ({stage.status})")
                
                trace_data = trace.to_dict()
                
                # Debug: Check if execution stage has additional_data
                for stage in trace_data.get('stages', []):
                    if stage.get('stage_name') == 'execution' and 'additional_data' in stage:
                        logger.info(f"🔍 TRACE DATA DEBUG: Execution stage has additional_data with keys: {list(stage['additional_data'].keys())}")
                        if 'llm_input_messages' in stage.get('additional_data', {}):
                            logger.info(f"🔍 TRACE DATA DEBUG: Found llm_input_messages with {len(stage['additional_data']['llm_input_messages'])} messages")
                
                emit('node_trace_data', {
                    'node_id': node_id,
                    'trace': trace_data
                })
                logger.info(f"✅ Sent trace data for node {node_id}: {len(trace.stages)} stages")
            else:
                # ENHANCED: Create sample trace data for testing
                logger.warning(f"❌ No trace found for node: {node_id}")
                logger.info(f"🔍 TRACE: Creating sample trace data for testing...")
                
                sample_trace = {
                    "node_id": node_id,
                    "node_goal": f"Sample goal for {node_id}",
                    "trace_id": f"sample-{node_id}",
                    "created_at": "2024-01-01T10:00:00Z",
                    "stages": [
                        {
                            "stage_name": "atomization",
                            "stage_id": f"stage-1-{node_id}",
                            "started_at": "2024-01-01T10:00:00Z",
                            "completed_at": "2024-01-01T10:00:05Z",
                            "status": "completed",
                            "agent_name": "sample_agent",
                            "adapter_name": "AtomizerAdapter",
                            "system_prompt": "You are an atomizer agent determining if a task is atomic.",
                            "user_input": f"Please analyze this task: {node_id}",
                            "llm_response": "This task requires further decomposition.",
                            "output_data": "Task is not atomic, should be planned",
                            "duration_ms": 5000
                        },
                        {
                            "stage_name": "planning",
                            "stage_id": f"stage-2-{node_id}",
                            "started_at": "2024-01-01T10:00:05Z",
                            "completed_at": "2024-01-01T10:00:15Z", 
                            "status": "completed",
                            "agent_name": "planner_agent",
                            "adapter_name": "PlannerAdapter",
                            "system_prompt": "You are a planning agent that breaks down tasks.",
                            "user_input": f"Create a plan for: {node_id}",
                            "llm_response": "Here's a step-by-step plan...",
                            "output_data": "Generated plan with 3 sub-tasks",
                            "duration_ms": 10000
                        },
                        {
                            "stage_name": "execution",
                            "stage_id": f"stage-3-{node_id}",
                            "started_at": "2024-01-01T10:00:15Z",
                            "completed_at": "2024-01-01T10:00:30Z",
                            "status": "completed", 
                            "agent_name": "executor_agent",
                            "adapter_name": "ExecutorAdapter",
                            "system_prompt": "You are an execution agent that performs tasks.",
                            "user_input": f"Execute this task: {node_id}",
                            "llm_response": "Task completed successfully with detailed results.",
                            "output_data": "Execution completed with results",
                            "duration_ms": 15000
                        }
                    ],
                    "metadata": {"sample": True}
                }
                
                emit('node_trace_data', {
                    'node_id': node_id,
                    'trace': sample_trace,
                    'debug_info': debug_state,
                    'message': 'Sample trace data (no real traces found)'
                })
                
        except Exception as e:
            logger.error(f"Node trace request error: {e}")
            import traceback
            traceback.print_exc()
            emit('node_trace_error', {'error': str(e)})
    
    @socketio.on('request_stage_details')
    def handle_request_stage_details(data):
        """Handle request for detailed stage information."""
        logger.info(f"🔍 WebSocket request for stage details: {data}")
        try:
            node_id = data.get('node_id')
            stage_id = data.get('stage_id')
            project_id = data.get('project_id')
            
            if not node_id or not stage_id:
                emit('stage_details_error', {
                    'error': 'node_id and stage_id are required'
                })
                return
            
            if not project_id:
                emit('stage_details_error', {'error': 'project_id is required'})
                return
            
            # Get project-specific trace manager
            project_context = project_service.get_project_execution_context(project_id)
            if not project_context:
                emit('stage_details_error', {'error': f'Project {project_id} not found'})
                return
            
            trace_manager = project_context.trace_manager
            
            # Get trace for the node
            trace = trace_manager.get_trace_for_node(node_id)
            if trace:
                stage = trace.get_stage_by_id(stage_id)
                if stage:
                    stage_data = {
                        "stage_name": stage.stage_name,
                        "stage_id": stage.stage_id,
                        "started_at": stage.started_at.isoformat(),
                        "completed_at": stage.completed_at.isoformat() if stage.completed_at else None,
                        "status": stage.status,
                        "agent_name": stage.agent_name,
                        "adapter_name": stage.adapter_name,
                        "model_info": stage.model_info,
                        "system_prompt": stage.system_prompt,
                        "user_input": stage.user_input,
                        "llm_response": stage.llm_response,
                        "input_context": stage.input_context,
                        "processing_parameters": stage.processing_parameters,
                        "output_data": stage.output_data,
                        "error_message": stage.error_message,
                        "error_details": stage.error_details,
                        "duration_ms": stage.get_duration_ms()
                    }
                    
                    emit('stage_details_data', {
                        'node_id': node_id,
                        'stage_id': stage_id,
                        'stage': stage_data
                    })
                    logger.info(f"✅ Sent stage details for node {node_id}, stage {stage_id}")
                else:
                    emit('stage_details_error', {
                        'error': f'Stage {stage_id} not found'
                    })
            else:
                emit('stage_details_error', {
                    'error': f'No trace found for node {node_id}'
                })
                
        except Exception as e:
            logger.error(f"Stage details request error: {e}")
            emit('stage_details_error', {
                'error': str(e)
            })

    @socketio.on('clear_traces')
    def handle_clear_traces(data):
        """Handle request to clear traces for a project."""
        logger.info(f"🔍 WebSocket request to clear traces: {data}")
        try:
            project_id = data.get('project_id')
            
            if not project_id:
                emit('clear_traces_error', {'error': 'project_id is required'})
                return
            
            # Get project-specific trace manager
            project_context = project_service.get_project_execution_context(project_id)
            if not project_context:
                emit('clear_traces_error', {'error': f'Project {project_id} not found'})
                return
            
            trace_manager = project_context.trace_manager
            trace_manager.clear_traces()
            
            emit('traces_cleared', {
                'message': f'Traces cleared for project {project_id}',
                'project_id': project_id
            })
            logger.info(f"✅ Traces cleared for project {project_id}")
        except Exception as e:
            logger.error(f"Clear traces error: {e}")
            emit('clear_traces_error', {
                'error': str(e)
            })


def _run_simple_streaming_execution(socketio, goal: str, options: dict):
    """
    Run simple API execution with streaming updates.
    
    Args:
        socketio: SocketIO instance for emitting updates
        goal: Execution goal
        options: Execution options
    """
    try:
        # This would need access to the system manager to get the simple agent
        # For now, we'll import it directly
        from ...framework_entry import SimpleSentientAgent
        
        agent = SimpleSentientAgent.create(enable_hitl=False)
        if not agent:
            socketio.emit('simple_execution_error', {'message': 'Failed to get SimpleSentientAgent'})
            return
        
        logger.info(f"🌊 Starting streaming execution: {goal}")
        
        # Use the streaming method from SimpleSentientAgent
        for update in agent.stream_execution(goal, **options):
            socketio.emit('simple_execution_update', update)
            import time
            time.sleep(0.1)  # Small delay to prevent overwhelming the client
        
        logger.info(f"✅ Streaming execution completed: {goal}")
        
    except Exception as e:
        logger.error(f"Streaming execution failed: {e}")
        socketio.emit('simple_execution_error', {
            'message': f'Streaming execution failed: {str(e)}',
            'goal': goal
        })
