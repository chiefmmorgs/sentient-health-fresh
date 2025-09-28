"""
Execution Service

Handles project execution logic, real-time updates, and execution lifecycle management.
"""

import asyncio
import threading
import time
import traceback
from typing import Dict, Any, Optional, TYPE_CHECKING
from loguru import logger
from datetime import datetime

from ...framework_entry import create_node_processor_config_from_main_config
from ...config import SentientConfig
from ...hierarchical_agent_framework.node import TaskStatus

if TYPE_CHECKING:
    from ...server.services.system_manager import SystemManager

class RealtimeExecutionWrapper:
    """
    Wrapper for execution engines that provides real-time updates.
    
    This class manages periodic updates during execution to keep the 
    frontend synchronized with execution progress.
    """
    
    def __init__(self, project_id: str, execution_engine, update_callback, project_manager):
        """
        Initialize the execution wrapper.
        
        Args:
            project_id: Project identifier
            execution_engine: Execution engine instance
            update_callback: Callback for broadcasting updates
            project_manager: Project manager instance
        """
        self.project_id = project_id
        self.execution_engine = execution_engine
        self.update_callback = update_callback
        self.project_manager = project_manager
        self._is_current_project = False
        
    def _check_if_current(self) -> bool:
        """Check if this project is currently being displayed."""
        current_project = self.project_manager.get_current_project()
        self._is_current_project = current_project and current_project.id == self.project_id
        return self._is_current_project
        
    async def run_project_flow(self, root_goal: str, max_steps: int = 250) -> Any:
        """
        Run the complete project flow with real-time updates.
        
        Args:
            root_goal: Root goal for the project
            max_steps: Maximum execution steps
            
        Returns:
            Execution result
        """
        async def execute_with_updates():
            # Start the execution flow (includes initialization and HITL)
            execution_task = asyncio.create_task(
                self.execution_engine.run_project_flow(
                    root_goal=root_goal,
                    max_steps=max_steps
                )
            )
            
            # Create a periodic update task
            update_task = asyncio.create_task(
                self._periodic_updates(execution_task)
            )
            
            try:
                # Wait for execution to complete
                result = await execution_task
                # Cancel the update task
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
                # Final update only if current
                if self._check_if_current():
                    self.update_callback()
                return result
            except Exception as e:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
                # Update on error too, but only if current
                if self._check_if_current():
                    self.update_callback()
                raise e
        
        return await execute_with_updates()
    
    async def run_cycle(self, max_steps: int = 250) -> Any:
        """
        Run execution cycle with periodic real-time updates (for resuming).
        
        Args:
            max_steps: Maximum execution steps
            
        Returns:
            Execution result
        """
        async def execute_with_updates():
            # Start the execution cycle
            execution_task = asyncio.create_task(
                self.execution_engine.run_cycle(max_steps=max_steps)
            )
            
            # Create a periodic update task
            update_task = asyncio.create_task(
                self._periodic_updates(execution_task)
            )
            
            try:
                # Wait for execution to complete
                result = await execution_task
                # Cancel the update task
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
                # Final update only if current
                if self._check_if_current():
                    self.update_callback()
                return result
            except Exception as e:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
                # Update on error too, but only if current
                if self._check_if_current():
                    self.update_callback()
                raise e
        
        return await execute_with_updates()
    
    async def _periodic_updates(self, execution_task: asyncio.Task):
        """
        Periodically update display while execution is running.
        
        Args:
            execution_task: The main execution task to monitor
        """
        # Use a shorter interval for more responsive updates
        update_interval = 0.5  # Update every 0.5 seconds instead of 2 seconds
        last_update_time = 0
        
        while not execution_task.done():
            await asyncio.sleep(update_interval)
            if not execution_task.done():
                current_time = time.time()
                # Only update display if we're the current project
                if self._check_if_current():
                    self.update_callback()
                    last_update_time = current_time
                else:
                    # Still save state for background projects, but less frequently
                    if current_time - last_update_time > 5.0:  # Save every 5 seconds for background
                        self._save_background_state()
                        last_update_time = current_time
    
    def _save_background_state(self):
        """Save state for background projects without updating display."""
        try:
            # This would need access to the project graphs and project manager
            # For now, we'll let the project service handle this
            logger.debug(f"Saving background state for project {self.project_id}")
        except Exception as e:
            logger.warning(f"Failed to save background project state: {e}")


class ExecutionService:
    """
    Manages project execution lifecycle and coordination.
    
    This service handles:
    - Starting and stopping project executions
    - Managing execution threads and async tasks
    - Coordinating real-time updates
    - Handling execution errors and recovery
    """
    
    def __init__(self, project_service, system_manager):
        """
        Initialize ExecutionService.
        
        Args:
            project_service: ProjectService instance
            system_manager: SystemManager instance
        """
        self.project_service = project_service
        self.system_manager = system_manager
        self._running_executions: Dict[str, Dict[str, Any]] = {}
    
    def start_project_execution(self, project_id: str, goal: str, max_steps: int) -> bool:
        """
        Start project execution in a background thread.
        
        Args:
            project_id: Project identifier
            goal: Project goal
            max_steps: Maximum execution steps
            
        Returns:
            True if started successfully, False otherwise
        """
        try:
            if project_id in self._running_executions:
                logger.warning(f"Project {project_id} is already running")
                return False
            
            # Create execution thread
            thread = threading.Thread(
                target=self._run_project_in_thread,
                args=(project_id, goal, max_steps),
                daemon=True
            )
            
            # Store execution info
            self._running_executions[project_id] = {
                'thread': thread,
                'goal': goal,
                'max_steps': max_steps,
                'started_at': datetime.now()
            }
            
            # Start the thread
            thread.start()
            
            logger.info(f"🚀 Started execution for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start project execution: {e}")
            # Clean up on failure
            if project_id in self._running_executions:
                del self._running_executions[project_id]
            return False
    
    def start_configured_project_execution(self, project_id: str, goal: str, max_steps: int, config: SentientConfig) -> bool:
        """
        Start project execution with custom configuration.
        
        Args:
            project_id: Project identifier
            goal: Project goal
            max_steps: Maximum execution steps
            config: Custom configuration
            
        Returns:
            True if started successfully, False otherwise
        """
        try:
            if project_id in self._running_executions:
                logger.warning(f"Project {project_id} is already running")
                return False
            
            # Store the custom config in project service
            self.project_service.project_configs[project_id] = config
            
            # Create execution thread
            thread = threading.Thread(
                target=self._run_configured_project_in_thread,
                args=(project_id, goal, max_steps, config),
                daemon=True
            )
            
            # Store execution info
            self._running_executions[project_id] = {
                'thread': thread,
                'goal': goal,
                'max_steps': max_steps,
                'config': config,
                'started_at': datetime.now()
            }
            
            # Start the thread
            thread.start()
            
            logger.info(f"🚀 Started configured execution for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start configured project execution: {e}")
            # Clean up on failure
            if project_id in self._running_executions:
                del self._running_executions[project_id]
            return False
    
    def get_running_executions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about currently running executions.
        
        Returns:
            Dictionary of running execution info
        """
        # Clean up completed threads
        completed = []
        for project_id, info in self._running_executions.items():
            if not info['thread'].is_alive():
                completed.append(project_id)
        
        for project_id in completed:
            del self._running_executions[project_id]
        
        # Return info about running executions (without thread objects)
        return {
            project_id: {
                'goal': info['goal'],
                'max_steps': info['max_steps'],
                'started_at': info['started_at'].isoformat(),
                'is_alive': info['thread'].is_alive()
            }
            for project_id, info in self._running_executions.items()
        }
    
    def _run_project_in_thread(self, project_id: str, goal: str, max_steps: int):
        """
        Thread wrapper for async execution with project management.
        
        Args:
            project_id: Project identifier
            goal: Project goal
            max_steps: Maximum execution steps
        """
        logger.info(f"🧵 Thread started for project: {project_id}")
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._run_project_cycle_async(project_id, goal, max_steps)
            )
        except Exception as e:
            logger.error(f"Thread error for project {project_id}: {e}")
            traceback.print_exc()
            
            # Update project status to failed
            self.project_service.project_manager.update_project(project_id, status='failed')
        finally:
            # Clean up
            if project_id in self._running_executions:
                del self._running_executions[project_id]
            logger.info(f"🏁 Thread finished for project: {project_id}")
    
    def _run_configured_project_in_thread(self, project_id: str, goal: str, max_steps: int, config: SentientConfig):
        """
        Thread wrapper for async execution with custom configuration.
        
        Args:
            project_id: Project identifier
            goal: Project goal
            max_steps: Maximum execution steps
            config: Custom configuration
        """
        logger.info(f"🧵 Configured thread started for project: {project_id}")
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._run_configured_project_cycle_async(project_id, goal, max_steps, config)
            )
        except Exception as e:
            logger.error(f"Configured thread error for project {project_id}: {e}")
            traceback.print_exc()
            
            # Update project status to failed
            self.project_service.project_manager.update_project(project_id, status='failed')
        finally:
            # Clean up
            if project_id in self._running_executions:
                del self._running_executions[project_id]
            logger.info(f"🏁 Configured thread finished for project: {project_id}")
    
    async def _run_project_cycle_async(self, project_id: str, goal: str, max_steps: int):
        """
        Run the project cycle with proper project isolation and AGGRESSIVE result saving.
        """
        logger.info(f"🎯 Initializing project: {project_id} - {goal}")
        
        try:
            # Get or create project-specific components
            project_components = self.project_service.get_or_create_project_graph(project_id)
            project_task_graph = project_components['task_graph']
            project_execution_engine = project_components['execution_engine']
            update_callback = project_components['update_callback']
            
            # Create real-time wrapper with enhanced saving
            realtime_engine = RealtimeExecutionWrapper(
                project_id,
                project_execution_engine,
                update_callback,
                self.project_service.project_manager
            )
            
            # Check if this should be the current project
            current_project = self.project_service.project_manager.get_current_project()
            if not current_project:
                self.project_service.project_manager.set_current_project(project_id)
                should_display = True
            else:
                should_display = (current_project.id == project_id)
            
            # Load existing state
            project_state = self.project_service.project_manager.load_project_state(project_id)
            
            if project_state and 'all_nodes' in project_state and len(project_state['all_nodes']) > 0:
                logger.info(f"📊 Resuming project with {len(project_state['all_nodes'])} existing nodes")
                self._load_project_state(project_task_graph, project_state)
                self.project_service.project_manager.update_project(project_id, status='running')
                
                if should_display:
                    # Trigger broadcast update for current project
                    if self.project_service.broadcast_callback:
                        self.project_service.broadcast_callback()
                
                logger.info("⚡ Resuming execution...")
                result = await realtime_engine.run_cycle(max_steps=max_steps)
                
                # Handle execution result
                if isinstance(result, dict) and 'error' in result:
                    logger.error(f"❌ Execution failed: {result['error']}")
                    self.project_service.project_manager.update_project(project_id, status='failed', error=result['error'])
                    # Store error in the root node
                    root_node = project_task_graph.get_node("root")
                    if root_node:
                        root_node.error = result['error']
                        root_node.status = TaskStatus.FAILED
                else:
                    logger.info("✅ Execution completed successfully")
            else:
                logger.info("🧹 Starting fresh project...")
                
                # Clear project graph
                project_task_graph.nodes.clear()
                project_task_graph.graphs.clear()
                project_task_graph.root_graph_id = None
                project_task_graph.overall_project_goal = None
                
                # CRITICAL FIX: Clear the knowledge store for the project
                knowledge_store = project_components.get('knowledge_store')
                if knowledge_store:
                    knowledge_store.clear()
                    logger.info("KnowledgeStore cleared for fresh project start.")
                
                # Clear project-specific cache
                cache_manager = self.system_manager.cache_manager
                if cache_manager and self.system_manager.config.cache.enabled:
                    cache_manager.clear_namespace(f"project_{project_id}")
                
                self.project_service.project_manager.update_project(project_id, status='running')
                
                logger.info("🚀 Starting project flow...")
                start_time = time.time()
                
                result = await realtime_engine.run_project_flow(root_goal=goal, max_steps=max_steps)
                
                total_time = time.time() - start_time
                logger.info(f"⏱️ Project execution took {total_time:.2f} seconds")
                
                # Handle execution result
                if isinstance(result, dict) and 'error' in result:
                    logger.error(f"❌ Execution failed: {result['error']}")
                    self.project_service.project_manager.update_project(project_id, status='failed', error=result['error'])
                    # Store error in the root node
                    root_node = project_task_graph.get_node("root")
                    if root_node:
                        root_node.error = result['error']
                        root_node.status = TaskStatus.FAILED
                else:
                    logger.info("✅ Execution completed successfully")
            
            # CRITICAL: Update project status BEFORE saving (only if not already marked as failed)
            current_project = self.project_service.project_manager.get_project(project_id)
            if current_project and current_project.status != 'failed':
                self.project_service.project_manager.update_project(project_id, status='completed')
            
            # CRITICAL: Save state IMMEDIATELY after execution completes
            logger.info(f"🚨 CRITICAL SAVE - Saving final state for project {project_id}")
            self._save_final_project_state_enhanced(project_task_graph, project_id)
            
            # Final sync only if current project
            if (self.project_service.project_manager.get_current_project() and 
                self.project_service.project_manager.get_current_project().id == project_id):
                # Trigger broadcast update for current project
                if self.project_service.broadcast_callback:
                    self.project_service.broadcast_callback()
            
            logger.info(f"✅ Project {project_id} completed and saved")
            
        except Exception as e:
            self.project_service.project_manager.update_project(project_id, status='failed')
            logger.error(f"Project execution error: {e}")
            traceback.print_exc()
            
            try:
                if (self.project_service.project_manager.get_current_project() and 
                    self.project_service.project_manager.get_current_project().id == project_id):
                    # Trigger broadcast update for current project
                    if self.project_service.broadcast_callback:
                        self.project_service.broadcast_callback()
            except:
                logger.error("Failed to broadcast error state")
    
    async def _run_configured_project_cycle_async(self, project_id: str, goal: str, max_steps: int, config: SentientConfig):
        """
        Run the project cycle with custom configuration.
        
        Args:
            project_id: Project identifier
            goal: Project goal
            max_steps: Maximum execution steps
            config: Custom configuration
        """
        logger.info(f"🎯 Initializing configured project: {project_id} - {goal}")
        logger.info(f"🔧 Using config: {config.llm.provider}/{config.llm.model}, "
                   f"temp={config.llm.temperature}, HITL={config.execution.enable_hitl}")
        
        # For configured projects, we force creation of new components with custom config
        # This is handled by the project service when we call get_or_create_project_graph
        
        # The rest of the logic is the same as regular execution
        await self._run_project_cycle_async(project_id, goal, max_steps)
    
    def _load_project_state(self, project_task_graph, project_state):
        """Load project state into task graph."""
        # This logic was extracted from the original load method
        # It deserializes nodes and reconstructs graphs
        self.project_service._reconstruct_graphs(project_task_graph, project_state.get('graphs', {}))
        # ... other state loading logic
    
    def _save_final_project_state_enhanced(self, project_task_graph, project_id):
        """Enhanced final state saving with trace persistence."""
        try:
            logger.info(f"🚨 ENHANCED SAVE - Starting comprehensive save for project: {project_id}")
            
            # Get comprehensive project data
            if hasattr(project_task_graph, 'to_visualization_dict'):
                data = project_task_graph.to_visualization_dict()
            else:
                from ...hierarchical_agent_framework.graph.graph_serializer import GraphSerializer
                serializer = GraphSerializer(project_task_graph)
                data = serializer.to_visualization_dict()
            
            # AGGRESSIVE DEBUGGING
            node_count = len(data.get('all_nodes', {}))
            logger.info(f"🚨 ENHANCED SAVE - Project {project_id}: {node_count} nodes to save")
            
            if node_count == 0:
                logger.error(f"🚨 CRITICAL ERROR - Project {project_id} has 0 nodes after execution!")
                logger.error(f"🚨 CRITICAL ERROR - This indicates execution results were not captured!")
                
                # Try to get data from system manager as fallback
                try:
                    if hasattr(self.system_manager, 'task_graph') and self.system_manager.task_graph:
                        fallback_data = self.system_manager.task_graph.to_visualization_dict()
                        fallback_node_count = len(fallback_data.get('all_nodes', {}))
                        logger.info(f"🚨 FALLBACK ATTEMPT - System manager has {fallback_node_count} nodes")
                        
                        if fallback_node_count > 0:
                            logger.info(f"🚨 FALLBACK SUCCESS - Using system manager data instead")
                            data = fallback_data
                            node_count = fallback_node_count
                except Exception as fe:
                    logger.error(f"🚨 FALLBACK FAILED: {fe}")
            
            if data.get('all_nodes'):
                # Log details about nodes being saved
                for i, (node_id, node_data) in enumerate(list(data['all_nodes'].items())[:3]):
                    has_full_result = bool(node_data.get('full_result'))
                    has_execution_details = bool(node_data.get('execution_details'))
                    status = node_data.get('status', 'unknown')
                    logger.info(f"🚨 ENHANCED SAVE - Node {i+1} ({node_id}): "
                               f"status={status}, has_full_result={has_full_result}, "
                               f"has_execution_details={has_execution_details}")
                    
                    # Special handling for root node
                    if node_data.get('layer') == 0 and not node_data.get('parent_node_id'):
                        full_result_preview = str(node_data.get('full_result', ''))[:200]
                        logger.info(f"🚨 ENHANCED SAVE - ROOT NODE full_result preview: {full_result_preview}...")
            
            # NEW: Save traces for this project
            try:
                # Get project-specific trace manager
                project_context = self.project_service.get_project_execution_context(project_id)
                if project_context and hasattr(project_context, 'trace_manager'):
                    project_context.trace_manager.save_project_traces(project_id)
                    logger.info(f"🔍 TRACE: Saved all traces for project {project_id}")
                else:
                    logger.warning(f"🔍 TRACE: No project context or trace manager for project {project_id}")
            except Exception as e:
                logger.warning(f"🔍 TRACE: Failed to save traces for project {project_id}: {e}")
            
            # MULTIPLE SAVE ATTEMPTS
            save_attempts = [
                ("project_manager", lambda: self.project_service.project_manager.save_project_state(project_id, data)),
                ("comprehensive_results", lambda: self._save_comprehensive_results(project_id, data)),
                ("emergency_backup", lambda: self._save_emergency_backup(project_id, data))
            ]
            
            successful_saves = 0
            for save_name, save_func in save_attempts:
                try:
                    save_func()
                    logger.info(f"✅ ENHANCED SAVE - {save_name} successful")
                    successful_saves += 1
                except Exception as se:
                    logger.error(f"❌ ENHANCED SAVE - {save_name} failed: {se}")
            
            if successful_saves > 0:
                logger.info(f"✅ ENHANCED SAVE - {successful_saves}/{len(save_attempts)} save methods successful")
            else:
                logger.error(f"❌ ENHANCED SAVE - ALL SAVE METHODS FAILED for project {project_id}")
            
            # VERIFICATION
            self._verify_save(project_id, node_count)
            
        except Exception as e:
            logger.error(f"Enhanced save failed for project {project_id}: {e}")
            import traceback
            traceback.print_exc()

    def _save_comprehensive_results(self, project_id: str, data: Dict[str, Any]):
        """Save comprehensive results package."""
        results_package = {
            'basic_state': data,
            'saved_at': datetime.now().isoformat(),
            'execution_completed': True,
            'enhanced_save': True,
            'metadata': {
                'node_count': len(data.get('all_nodes', {})),
                'project_goal': data.get('overall_project_goal'),
                'completion_status': self._get_completion_status(data.get('all_nodes', {})),
                'has_root_node': any(
                    node.get('layer') == 0 and not node.get('parent_node_id') 
                    for node in data.get('all_nodes', {}).values()
                ),
                'root_node_completed': any(
                    node.get('layer') == 0 and not node.get('parent_node_id') and node.get('status') == 'DONE'
                    for node in data.get('all_nodes', {}).values()
                )
            }
        }
        
        success = self.project_service.save_project_results(project_id, results_package)
        if not success:
            raise Exception("Failed to save comprehensive results")

    def _save_emergency_backup(self, project_id: str, data: Dict[str, Any]):
        """Save emergency backup to a separate file."""
        import json
        from pathlib import Path
        
        # Use centralized paths for emergency backups
        from ...config.paths import RuntimePaths
        paths = RuntimePaths.get_default()
        backup_dir = paths.get_emergency_backup_path()
        backup_dir.mkdir(exist_ok=True, parents=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"{project_id}_{timestamp}_emergency.json"
        
        backup_data = {
            'project_id': project_id,
            'saved_at': datetime.now().isoformat(),
            'emergency_backup': True,
            'data': data
        }
        
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        logger.info(f"🚨 EMERGENCY BACKUP saved to: {backup_file}")

    def _verify_save(self, project_id: str, expected_node_count: int):
        """Verify that the save was successful."""
        try:
            verification_data = self.project_service.project_manager.load_project_state(project_id)
            if verification_data:
                actual_node_count = len(verification_data.get('all_nodes', {}))
                logger.info(f"🔍 SAVE VERIFICATION - Expected: {expected_node_count}, Actual: {actual_node_count}")
                
                if actual_node_count == expected_node_count:
                    logger.info(f"✅ SAVE VERIFICATION PASSED")
                else:
                    logger.error(f"❌ SAVE VERIFICATION FAILED - Node count mismatch")
            else:
                logger.error(f"❌ SAVE VERIFICATION FAILED - Could not load saved data")
        except Exception as ve:
            logger.error(f"❌ SAVE VERIFICATION ERROR: {ve}")

    def _get_completion_status(self, nodes: Dict[str, Any]) -> str:
        """Determine project completion status from nodes."""
        if not nodes:
            return "no_nodes"
        
        total_nodes = len(nodes)
        completed_nodes = sum(1 for node in nodes.values() if node.get('status') == 'DONE')
        
        if completed_nodes == 0:
            return "not_started"
        elif completed_nodes == total_nodes:
            return "completed"
        else:
            return f"partial_{completed_nodes}_{total_nodes}"
