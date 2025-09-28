"""
Project Service

Handles project management logic including project graphs, state management,
and synchronization with the display.
"""

from typing import Dict, Any, Optional, Callable, List, TYPE_CHECKING
import traceback
from loguru import logger
from datetime import datetime
import json
import os
from pathlib import Path

from ...core.project_manager import ProjectManager, ProjectExecutionContext
from ...framework_entry import create_node_processor_config_from_main_config
from ...hierarchical_agent_framework.graph.task_graph import TaskGraph
from ...hierarchical_agent_framework.graph.state_manager import StateManager
from ...hierarchical_agent_framework.graph.execution_engine import ExecutionEngine
from ...hierarchical_agent_framework.node.node_processor import NodeProcessor
from ...hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator
from ...hierarchical_agent_framework.node.task_node import TaskNode
from ...hierarchical_agent_framework.types import TaskStatus, TaskType, NodeType

if TYPE_CHECKING:
    from ...core.system_manager import SystemManager

class ProjectService:
    """
    Manages project lifecycle, state, and synchronization.
    
    This service handles:
    - Project graph creation and management
    - State synchronization between projects and display
    - Project configuration management
    - Real-time updates and callbacks
    """
    
    def __init__(self, system_manager: "SystemManager", broadcast_callback: Optional[Callable] = None):
        """
        Initialize ProjectService.
        
        Args:
            system_manager: SystemManager instance
            broadcast_callback: Optional callback for broadcasting updates
        """
        self.system_manager = system_manager
        self.broadcast_callback = broadcast_callback
        self.project_manager = ProjectManager()
        
        # Store project-specific components
        self.project_graphs: Dict[str, Dict[str, Any]] = {}
        self.project_configs: Dict[str, Any] = {}
        self.project_execution_contexts: Dict[str, "ProjectExecutionContext"] = {}
        
        # Track current display state to prevent conflicts
        self.current_display_project_id: Optional[str] = None
        
        # Create results storage directory using centralized paths
        from ...config.paths import RuntimePaths
        paths = RuntimePaths.get_default()
        self.results_dir = paths.experiment_results_dir
        self.results_dir.mkdir(exist_ok=True, parents=True)
        
        logger.info("✅ ProjectService initialized")
        
    def get_all_projects(self) -> Dict[str, Any]:
        """
        Get all projects with their metadata.
        
        Returns:
            Dictionary containing projects list and current project ID
        """
        projects = self.project_manager.get_all_projects()
        current_project_id = self.project_manager.get_current_project_id()
        
        # Convert projects to dictionaries and add metadata
        project_dicts = []
        for project in projects:
            project_dict = project.to_dict()
            
            # Add completion metadata if available
            try:
                results_file = self.results_dir / f"{project.id}_results.json"
                if results_file.exists():
                    with open(results_file, 'r') as f:
                        saved_results = json.load(f)
                        project_dict['has_saved_results'] = True
                        project_dict['last_saved'] = saved_results.get('saved_at')
                        project_dict['completion_status'] = saved_results.get('metadata', {}).get('completion_status')
                else:
                    project_dict['has_saved_results'] = False
            except Exception as e:
                logger.warning(f"Failed to check saved results for project {project.id}: {e}")
                project_dict['has_saved_results'] = False
            
            project_dicts.append(project_dict)
        
        return {
            "projects": project_dicts,
            "current_project_id": current_project_id
        }
    
    def create_project(self, goal: str, max_steps: int, custom_config: Optional[Any] = None) -> Dict[str, Any]:
        """
        Create a new project.
        
        Args:
            goal: Project goal description
            max_steps: Maximum execution steps
            custom_config: Optional custom configuration
            
        Returns:
            Dictionary containing project info
        """
        project = self.project_manager.create_project(goal, max_steps)
        
        # Store custom config if provided
        if custom_config:
            self.project_configs[project.id] = custom_config
            logger.info(f"✅ Project {project.id} created with custom configuration")
        else:
            logger.info(f"✅ Project {project.id} created with default configuration")
        
        return project.to_dict()
    
    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific project and its state.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Dictionary containing project and state info, or None if not found
        """
        project = self.project_manager.get_project(project_id)
        if not project:
            return None
        
        # Load project state if it exists
        project_state = self.project_manager.load_project_state(project_id)
        
        # Check for saved results
        project_dict = project.to_dict()
        try:
            results_file = self.results_dir / f"{project_id}_results.json"
            if results_file.exists():
                project_dict['has_saved_results'] = True
                with open(results_file, 'r') as f:
                    saved_results = json.load(f)
                    project_dict['last_saved'] = saved_results.get('saved_at')
                    project_dict['completion_status'] = saved_results.get('metadata', {}).get('completion_status')
            else:
                project_dict['has_saved_results'] = False
        except Exception as e:
            logger.warning(f"Failed to check saved results for project {project_id}: {e}")
            project_dict['has_saved_results'] = False
        
        return {
            "project": project_dict,
            "state": project_state
        }
    
    def get_project_display_data(self, project_id: str) -> Dict[str, Any]:
        """
        Get display data for a specific project with enhanced error handling.
        This method ensures project isolation and prevents data conflicts.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Serialized project data ready for frontend display
        """
        try:
            logger.debug(f"🔍 Getting display data for project {project_id}")
            
            # Ensure project is loaded in memory
            if project_id not in self.project_graphs:
                logger.debug(f"Loading project {project_id} into memory for display")
                if not self.load_project_into_graph(project_id):
                    logger.warning(f"Failed to load project {project_id}")
                    # Try to get data from comprehensive results as fallback
                    return self._try_comprehensive_results_fallback(project_id)
            
            # Get project-specific task graph
            project_components = self.project_graphs[project_id]
            project_task_graph = project_components['task_graph']
            
            # Check if task graph is None or empty
            if not project_task_graph:
                logger.warning(f"Task graph is None for project {project_id}")
                return self._try_comprehensive_results_fallback(project_id)
            
            # Log node count for debugging
            node_count = len(project_task_graph.nodes) if project_task_graph.nodes else 0
            logger.debug(f"🔍 Project {project_id} has {node_count} nodes in memory")
            
            # Serialize project data with enhanced error handling
            data = None
            try:
                if hasattr(project_task_graph, 'to_visualization_dict'):
                    data = project_task_graph.to_visualization_dict()
                else:
                    # Fallback serialization
                    from ...hierarchical_agent_framework.graph.graph_serializer import GraphSerializer
                    serializer = GraphSerializer(project_task_graph)
                    data = serializer.to_visualization_dict()
                
            except Exception as serialize_error:
                logger.error(f"🚨 SERIALIZATION ERROR for project {project_id}: {serialize_error}")
                logger.error(f"🚨 Node count in graph: {len(project_task_graph.nodes)}")
                
                # Try manual serialization as fallback
                try:
                    logger.info(f"🔄 Attempting manual serialization for project {project_id}")
                    data = self._manual_serialize_project_graph(project_task_graph)
                    logger.info(f"✅ Manual serialization successful: {len(data.get('all_nodes', {}))} nodes")
                except Exception as manual_error:
                    logger.error(f"🚨 Manual serialization also failed: {manual_error}")
                    # Final fallback to comprehensive results
                    return self._try_comprehensive_results_fallback(project_id)
            
            # Check if serialization returned valid data
            if data is None:
                logger.warning(f"Serialization returned None for project {project_id}")
                return self._try_comprehensive_results_fallback(project_id)
            
            if not isinstance(data, dict):
                logger.warning(f"Serialization returned non-dict ({type(data)}) for project {project_id}")
                return self._try_comprehensive_results_fallback(project_id)
            
            # Verify we have the expected structure
            node_count_serialized = len(data.get('all_nodes', {}))
            logger.debug(f"✅ Retrieved display data for project {project_id}: {node_count_serialized} nodes")
            
            # If serialization succeeded but returned 0 nodes when we know there should be more
            if node_count_serialized == 0 and node_count > 0:
                logger.warning(f"🚨 Serialization returned 0 nodes but task graph has {node_count} nodes!")
                return self._try_comprehensive_results_fallback(project_id)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to get display data for project {project_id}: {e}")
            import traceback
            traceback.print_exc()
            return self._try_comprehensive_results_fallback(project_id)
    
    def _try_comprehensive_results_fallback(self, project_id: str) -> Dict[str, Any]:
        """
        Try to get project data from comprehensive results as a fallback.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Project data from comprehensive results or empty data structure
        """
        try:
            logger.info(f"🔄 Attempting comprehensive results fallback for project {project_id}")
            
            # Try to load comprehensive results
            results = self.load_project_results(project_id)
            if results and results.get('basic_state'):
                basic_state = results['basic_state']
                node_count = len(basic_state.get('all_nodes', {}))
                logger.info(f"✅ Comprehensive results fallback successful: {node_count} nodes")
                return basic_state
            elif results and results.get('graph_data'):
                graph_data = results['graph_data']
                node_count = len(graph_data.get('all_nodes', {}))
                logger.info(f"✅ Graph data fallback successful: {node_count} nodes")
                return graph_data
            else:
                logger.warning(f"No comprehensive results found for project {project_id}")
                return self._get_empty_display_data()
            
        except Exception as e:
            logger.error(f"Comprehensive results fallback failed for project {project_id}: {e}")
            return self._get_empty_display_data()
    
    def _manual_serialize_project_graph(self, project_task_graph) -> Dict[str, Any]:
        """
        Manual fallback serialization for when the standard serialization fails.
        
        Args:
            project_task_graph: TaskGraph to serialize
            
        Returns:
            Manually serialized graph data
        """
        data = {
            'all_nodes': {},
            'graphs': {},
            'overall_project_goal': getattr(project_task_graph, 'overall_project_goal', None),
            'root_graph_id': getattr(project_task_graph, 'root_graph_id', None)
        }
        
        # Manually serialize nodes
        if hasattr(project_task_graph, 'nodes') and project_task_graph.nodes:
            from ...hierarchical_agent_framework.graph.graph_serializer import GraphSerializer
            temp_serializer = GraphSerializer(project_task_graph)
            
            for node_id, node in project_task_graph.nodes.items():
                try:
                    data['all_nodes'][node_id] = temp_serializer._serialize_node(node)
                except Exception as e:
                    logger.warning(f"Failed to manually serialize node {node_id}: {e}")
                    # Create minimal node representation with safe attribute access
                    aux_data = getattr(node, 'aux_data', None)
                    if aux_data is None:
                        aux_data = {}
                    
                    data['all_nodes'][node_id] = {
                        'task_id': node_id,
                        'goal': getattr(node, 'goal', 'Unknown goal'),
                        'status': str(getattr(node, 'status', 'UNKNOWN')),
                        'layer': getattr(node, 'layer', 0),
                        'full_result': getattr(node, 'result', None),
                        'error': str(e),
                        'agent_name': getattr(node, 'agent_name', None),
                        'parent_node_id': getattr(node, 'parent_node_id', None),
                        'task_type': str(getattr(node, 'task_type', None)) if hasattr(node, 'task_type') and node.task_type else None,
                        'node_type': str(getattr(node, 'node_type', None)) if hasattr(node, 'node_type') and node.node_type else None,
                        'output_summary': getattr(node, 'output_summary', None),
                        'aux_data': aux_data
                    }
        
        # Manually serialize graphs
        if hasattr(project_task_graph, 'graphs') and project_task_graph.graphs:
            for graph_id, graph in project_task_graph.graphs.items():
                try:
                    if hasattr(graph, 'nodes') and hasattr(graph, 'edges'):
                        data['graphs'][graph_id] = {
                            'nodes': list(graph.nodes()),
                            'edges': [{"source": u, "target": v} for u, v in graph.edges()]
                        }
                except Exception as e:
                    logger.warning(f"Failed to manually serialize graph {graph_id}: {e}")
        
        return data
    
    def _get_empty_display_data(self) -> Dict[str, Any]:
        """Return empty display data structure."""
        return {
            'all_nodes': {},
            'graphs': {},
            'overall_project_goal': None,
            'root_graph_id': None
        }
    
    def switch_project(self, project_id: str) -> bool:
        """
        Enhanced project switching with proper isolation and state management.
        
        Args:
            project_id: Project identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"🔄 Switching to project: {project_id}")
            
            # Save current project state before switching
            current_project_id = self.project_manager.get_current_project_id()
            if current_project_id and current_project_id != project_id:
                logger.debug(f"Saving state for current project: {current_project_id}")
                self._save_current_display_state()
            
            # Switch project metadata
            success = self.project_manager.switch_project(project_id)
            if not success:
                logger.error(f"Failed to switch project metadata to {project_id}")
                return False
            
            # Load and prepare new project for display
            self._load_and_prepare_project_display(project_id)
            
            # Update tracking
            self.current_display_project_id = project_id
            
            # Broadcast the switch with new project data
            if hasattr(self, 'broadcast_manager') and self.broadcast_manager:
                self.broadcast_manager.broadcast_project_switch(project_id)
            elif self.broadcast_callback:
                # Fallback to regular broadcast
                self.broadcast_callback()
            
            logger.info(f"✅ Successfully switched to project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch to project {project_id}: {e}")
            return False
    
    def _load_and_prepare_project_display(self, project_id: str):
        """
        Load project data and prepare it for display without affecting other projects.
        
        Args:
            project_id: Project identifier to load
        """
        try:
            # Ensure project is loaded in memory
            if project_id not in self.project_graphs:
                self.load_project_into_graph(project_id)
            
            # Load saved results if available (for persistence)
            self._auto_load_project_results(project_id)
            
            logger.debug(f"Project {project_id} prepared for display")
            
        except Exception as e:
            logger.error(f"Failed to prepare project {project_id} for display: {e}")
    
    def _save_current_display_state(self):
        """
        Save the state of whatever project is currently being displayed.
        """
        try:
            if not self.current_display_project_id:
                return
            
            # Get current project data
            project_data = self.get_project_display_data(self.current_display_project_id)
            
            # Save to project state
            self.project_manager.save_project_state(self.current_display_project_id, project_data)
            
            # Also save detailed results for persistence
            self.save_project_state_async(self.current_display_project_id, project_data)
            
            logger.debug(f"Saved display state for project: {self.current_display_project_id}")
            
        except Exception as e:
            logger.error(f"Failed to save current display state: {e}")
    
    def save_project_state_async(self, project_id: str, data: Dict[str, Any]):
        """
        Asynchronously save project state to prevent blocking operations.
        
        Args:
            project_id: Project identifier
            data: Project data to save
        """
        try:
            import threading
            
            def save_task():
                try:
                    # Save basic state
                    self.project_manager.save_project_state(project_id, data)
                    
                    # Save detailed results for persistence
                    results_package = {
                        'basic_state': data,
                        'saved_at': datetime.now().isoformat(),
                        'metadata': {
                            'node_count': len(data.get('all_nodes', {})),
                            'project_goal': data.get('overall_project_goal'),
                            'completion_status': self._get_completion_status(data.get('all_nodes', {}))
                        }
                    }
                    self.save_project_results(project_id, results_package)
                    
                except Exception as e:
                    logger.warning(f"Async save failed for project {project_id}: {e}")
            
            # Run save in background thread
            thread = threading.Thread(target=save_task, daemon=True)
            thread.start()
            
        except Exception as e:
            logger.warning(f"Failed to start async save for project {project_id}: {e}")
    
    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project and its saved results.
        
        Args:
            project_id: Project identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete saved results
            results_file = self.results_dir / f"{project_id}_results.json"
            if results_file.exists():
                results_file.unlink()
                logger.info(f"🗑️ Deleted saved results for project {project_id}")
            
            # Remove custom config
            if project_id in self.project_configs:
                del self.project_configs[project_id]
            
            # Delete project
            success = self.project_manager.delete_project(project_id)
            if success:
                logger.info(f"🗑️ Deleted project {project_id}")
            
            return success
        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            return False
    
    def get_or_create_project_graph(self, project_id: str) -> Dict[str, Any]:
        """
        Get or create a project-specific execution context.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Dictionary containing project-specific components
        """
        if project_id not in self.project_graphs:
            # Check if we have a custom config for this project
            custom_config = self.project_configs.get(project_id, self.system_manager.config)
            
            # Create update callback for real-time sync
            update_callback = self._create_project_update_callback(project_id)
            
            # Get the current profile's blueprint from SystemManager
            current_profile = self.system_manager.get_current_profile()
            current_blueprint = None
            if current_profile:
                try:
                    from ...hierarchical_agent_framework.agent_configs.profile_loader import ProfileLoader
                    profile_loader = ProfileLoader()
                    current_blueprint = profile_loader.load_profile(current_profile)
                    logger.info(f"🎯 Using blueprint '{current_blueprint.name}' for project {project_id}")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to load blueprint for profile '{current_profile}': {e}")

            # Create project execution context
            project_context = ProjectExecutionContext(
                project_id=project_id,
                config=custom_config,
                agent_registry=self.system_manager.agent_registry,
                agent_blueprint=current_blueprint,
                update_callback=update_callback
            )
            
            # Store the full project execution context for trace access
            self.project_execution_contexts[project_id] = project_context
            
            # Store the project execution context components
            self.project_graphs[project_id] = project_context.get_components()
            
            config_type = "custom" if project_id in self.project_configs else "default"
            logger.info(f"✅ Created execution environment for project {project_id} "
                       f"({config_type} config, HITL: {'enabled' if custom_config.execution.enable_hitl else 'disabled'})")
        
        return self.project_graphs[project_id]
    
    def get_project_execution_context(self, project_id: str) -> Optional["ProjectExecutionContext"]:
        """
        Get the project execution context for accessing project-specific components like TraceManager.
        
        Args:
            project_id: Project identifier
            
        Returns:
            ProjectExecutionContext object or None if not found
        """
        return self.project_execution_contexts.get(project_id)
    
    def sync_project_to_display(self, project_id: str) -> bool:
        """
        DEPRECATED: This method is being phased out in favor of project-specific display data.
        Kept for backward compatibility during transition.
        
        Args:
            project_id: Project identifier to sync
            
        Returns:
            True if successful, False otherwise
        """
        logger.warning("sync_project_to_display is deprecated. Use get_project_display_data instead.")
        
        try:
            # For backward compatibility, just trigger a broadcast
            if project_id == self.project_manager.get_current_project_id():
                if self.broadcast_callback:
                    self.broadcast_callback()
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to sync project {project_id} to display: {e}")
            return False
    
    def load_project_into_graph(self, project_id: str) -> bool:
        """
        Load a project's state into its task graph for display with comprehensive debugging.
        
        Args:
            project_id: Project identifier to load
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.debug(f"🚨 LOAD DEBUG - Starting load for project: {project_id}")
            
            # Get or create project-specific execution context
            project_components = self.get_or_create_project_graph(project_id)
            
            if not project_components:
                logger.error(f"🚨 LOAD DEBUG - Failed to get or create project components for {project_id}")
                return False
            
            logger.debug(f"🚨 LOAD DEBUG - Project graph created/retrieved: {project_components is not None}")
            
            # Load saved state into the project's task graph
            project_state = self.project_manager.load_project_state(project_id)
            project = self.project_manager.get_project(project_id)
            
            logger.debug(f"🚨 LOAD DEBUG - Project state loaded: {project_state is not None}")
            logger.debug(f"🚨 LOAD DEBUG - Project metadata loaded: {project is not None}")
            
            if project_state:
                node_count = len(project_state.get('all_nodes', {}))
                logger.debug(f"🚨 LOAD DEBUG - Project state contains {node_count} nodes")
                
                # Get the task graph from the components
                project_task_graph = project_components.get('task_graph')
                if not project_task_graph:
                    logger.error(f"🚨 LOAD DEBUG - Task graph is missing from project components for {project_id}")
                    return False
                
                # Clear and reload the project's task graph
                project_task_graph.nodes.clear()
                project_task_graph.graphs.clear()
                project_task_graph.root_graph_id = None
                project_task_graph.overall_project_goal = None
                
                if 'all_nodes' in project_state and node_count > 0:
                    # Load nodes by deserializing dictionaries back to TaskNode objects
                    successful_nodes = 0
                    failed_nodes = 0
                    
                    from ...hierarchical_agent_framework.node.task_node import TaskNode
                    
                    for node_id, node_data in project_state['all_nodes'].items():
                        try:
                            # Prepare data for deserialization
                            self._deserialize_node_timestamps(node_data)
                            self._deserialize_node_enums(node_data)
                            prepared_data = self._prepare_node_data_for_deserialization(node_data)
                            
                            task_node = TaskNode(**prepared_data)
                            project_task_graph.nodes[node_id] = task_node
                            successful_nodes += 1
                            
                        except Exception as e:
                            logger.warning(f"🚨 LOAD DEBUG - Failed to deserialize node {node_id}: {e}")
                            logger.debug(f"🚨 LOAD DEBUG - Node data that failed: {node_data}")
                            failed_nodes += 1
                    
                    logger.debug(f"🚨 LOAD DEBUG - Node deserialization: {successful_nodes} successful, {failed_nodes} failed")
                
                # Reconstruct graphs
                if 'graphs' in project_state:
                    self._reconstruct_graphs(project_task_graph, project_state['graphs'])
                    logger.debug(f"🚨 LOAD DEBUG - Reconstructed {len(project_state['graphs'])} graphs")
                
                # Set project goal
                if 'overall_project_goal' in project_state:
                    project_task_graph.overall_project_goal = project_state['overall_project_goal']
                elif project:
                    project_task_graph.overall_project_goal = project.goal
                
                # Set root graph ID
                if 'root_graph_id' in project_state:
                    project_task_graph.root_graph_id = project_state['root_graph_id']
            
            elif project:
                # No saved state, just set the goal
                project_task_graph = project_components.get('task_graph')
                if project_task_graph:
                    project_task_graph.overall_project_goal = project.goal
                    logger.debug(f"🚨 LOAD DEBUG - No saved state, only set goal from metadata")
            
            logger.debug(f"✅ LOAD DEBUG - Loaded project {project_id}: {len(project_components.get('task_graph').nodes)} nodes")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load project {project_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_current_project_state(self):
        """Save the current live graph state to the current project."""
        current_project = self.project_manager.get_current_project()
        if current_project:
            try:
                # Use the proper serialization method
                display_graph = self.system_manager.task_graph
                if hasattr(display_graph, 'to_visualization_dict'):
                    data = display_graph.to_visualization_dict()
                else:
                    # Fallback: Import and use GraphSerializer directly
                    from ...hierarchical_agent_framework.graph.graph_serializer import GraphSerializer
                    serializer = GraphSerializer(display_graph)
                    data = serializer.to_visualization_dict()
                
                self.project_manager.save_project_state(current_project.id, data)
                
                # Also update the project-specific graph if it exists
                if current_project.id in self.project_graphs:
                    project_task_graph = self.project_graphs[current_project.id]['task_graph']
                    project_task_graph.nodes.clear()
                    project_task_graph.nodes.update(display_graph.nodes)
                    project_task_graph.graphs.clear()
                    project_task_graph.graphs.update(display_graph.graphs)
                    project_task_graph.overall_project_goal = display_graph.overall_project_goal
                    project_task_graph.root_graph_id = display_graph.root_graph_id
                
                logger.debug(f"💾 Saved state for project {current_project.id}")
            except Exception as e:
                logger.error(f"Failed to save current project state: {e}")
                traceback.print_exc()
    
    def get_project_config(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the configuration used for a specific project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Configuration dictionary or None if not found
        """
        if project_id not in self.project_configs:
            return None
        
        config = self.project_configs[project_id]
        
        # Convert config to dictionary for JSON response
        return {
            "llm": {
                "provider": config.llm.provider,
                "model": config.llm.model,
                "temperature": config.llm.temperature,
                "max_tokens": getattr(config.llm, 'max_tokens', None),
                "timeout": config.llm.timeout,
                "max_retries": config.llm.max_retries
            },
            "execution": config.execution.to_frontend_dict(),
            "cache": {
                "enabled": config.cache.enabled,
                "ttl_seconds": config.cache.ttl_seconds,
                "max_size": config.cache.max_size,
                "cache_type": config.cache.cache_type
            }
        }
    
    def _create_project_update_callback(self, project_id: str) -> Callable:
        """Create a callback function that syncs project updates to display."""
        def update_callback():
            # Only broadcast if this is the current project
            current_project = self.project_manager.get_current_project()
            if current_project and current_project.id == project_id:
                # Trigger broadcast for current project
                if self.broadcast_callback:
                    self.broadcast_callback()
            # If not current project, just save the state without syncing to display
            else:
                try:
                    project_components = self.project_graphs.get(project_id)
                    if project_components:
                        project_task_graph = project_components['task_graph']
                        if hasattr(project_task_graph, 'to_visualization_dict'):
                            data = project_task_graph.to_visualization_dict()
                        else:
                            from ...hierarchical_agent_framework.graph.graph_serializer import GraphSerializer
                            serializer = GraphSerializer(project_task_graph)
                            data = serializer.to_visualization_dict()
                        self.project_manager.save_project_state(project_id, data)
                except Exception as e:
                    logger.warning(f"Failed to save state for background project {project_id}: {e}")
        
        return update_callback
    
    def _clear_display_graph(self):
        """Clear the display graph."""
        display_graph = self.system_manager.task_graph
        display_graph.nodes.clear()
        display_graph.graphs.clear()
        display_graph.root_graph_id = None
        display_graph.overall_project_goal = None
    
    def _deserialize_node_timestamps(self, node_data: Dict[str, Any]):
        """Convert timestamp strings back to datetime objects."""
        datetime_fields = ['timestamp_created', 'timestamp_updated', 'timestamp_completed']
        for field in datetime_fields:
            if isinstance(node_data.get(field), str):
                try:
                    node_data[field] = datetime.fromisoformat(node_data[field])
                except ValueError:
                    node_data[field] = None
    
    def _deserialize_node_enums(self, node_data: Dict[str, Any]):
        """Fix status and type enums if they're strings."""
        if 'status' in node_data and isinstance(node_data['status'], str):
            node_data['status'] = TaskStatus(node_data['status'])
        
        if 'task_type' in node_data and isinstance(node_data['task_type'], str):
            node_data['task_type'] = TaskType(node_data['task_type'])
        
        if 'node_type' in node_data and isinstance(node_data['node_type'], str):
            node_data['node_type'] = NodeType(node_data['node_type'])
    
    def _prepare_node_data_for_deserialization(self, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare node data for proper deserialization, ensuring all execution data is preserved.
        
        Args:
            node_data: Raw node data from saved state
            
        Returns:
            Prepared data ready for TaskNode creation
        """
        try:
            # Create a copy to avoid modifying original
            prepared_data = node_data.copy()
            
            # Ensure aux_data exists
            if 'aux_data' not in prepared_data:
                prepared_data['aux_data'] = {}
            
            # CRITICAL FIX: Move execution data to aux_data if it's in the root
            execution_fields = [
                'full_result', 'execution_details', 'model_info', 'input_context_sources',
                'execution_time', 'token_usage', 'cost_info', 'error_details'
            ]
            
            for field in execution_fields:
                if field in prepared_data and field not in prepared_data['aux_data']:
                    # Move from root to aux_data
                    prepared_data['aux_data'][field] = prepared_data[field]
                    logger.debug(f"🔄 Moved {field} to aux_data for node {prepared_data.get('task_id', 'unknown')}")
            
            # AGGRESSIVE DEBUGGING (moved to more verbose debug level)
            # has_full_result = bool(prepared_data['aux_data'].get('full_result'))
            # has_execution_details = bool(prepared_data['aux_data'].get('execution_details'))
            # logger.debug(f"🔄 PREP DEBUG - Node {prepared_data.get('task_id', 'unknown')}: "
            #             f"has_full_result={has_full_result}, has_execution_details={has_execution_details}")
            
            return prepared_data
            
        except Exception as e:
            logger.warning(f"Failed to prepare node data for deserialization: {e}")
            return node_data
    
    def _reconstruct_graphs(self, project_task_graph: TaskGraph, graphs_data: Dict[str, Any]):
        """Reconstruct NetworkX graphs from serialized data."""
        import networkx as nx
        
        project_task_graph.graphs.clear()
        
        for graph_id, graph_data in graphs_data.items():
            try:
                # Create a new DiGraph
                new_graph = nx.DiGraph()
                
                # Add nodes
                if 'nodes' in graph_data:
                    new_graph.add_nodes_from(graph_data['nodes'])
                
                # Add edges
                if 'edges' in graph_data:
                    for edge in graph_data['edges']:
                        if isinstance(edge, dict) and 'source' in edge and 'target' in edge:
                            new_graph.add_edge(edge['source'], edge['target'])
                        elif isinstance(edge, (list, tuple)) and len(edge) == 2:
                            new_graph.add_edge(edge[0], edge[1])
                
                project_task_graph.graphs[graph_id] = new_graph
            except Exception as e:
                logger.warning(f"Failed to reconstruct graph {graph_id}: {e}")

    def _check_system_readiness_for_execution(self) -> bool:
        """
        Check if the system is ready for project execution.
        
        Returns:
            True if system is ready, False otherwise
        """
        # Check if WebSocket HITL is ready (if HITL is enabled)
        if self.system_manager.config.execution.enable_hitl:
            if not self.system_manager.is_websocket_hitl_ready():
                logger.warning("⚠️ WebSocket HITL not ready - execution may auto-approve HITL requests")
                return False
        
        return True

    def start_project_execution(self, project_id: str) -> Dict[str, Any]:
        """
        Start execution for a specific project using its isolated execution context.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Dictionary containing execution status and info
        """
        try:
            # Validate system readiness
            if not self._check_system_readiness_for_execution():
                return {
                    "success": False,
                    "error": "System not ready for execution",
                    "project_id": project_id
                }
            
            # Get project metadata
            project = self.project_manager.get_project(project_id)
            if not project:
                return {
                    "success": False,
                    "error": f"Project {project_id} not found",
                    "project_id": project_id
                }
            
            # Get or create project-specific execution context
            project_components = self.get_or_create_project_graph(project_id)
            project_execution_engine = project_components['execution_engine']
            project_task_graph = project_components['task_graph']
            
            # Set the project goal if not already set
            if not project_task_graph.overall_project_goal:
                project_task_graph.overall_project_goal = project.goal
                logger.info(f"Set project goal for {project_id}: {project.goal}")
            
            # Update project status
            self.project_manager.update_project(project_id, status='running')
            
            # Start execution using project-specific engine
            logger.info(f"🚀 Starting execution for project {project_id}")
            
            # Execute using the project-specific execution engine
            execution_result = project_execution_engine.execute_graph(
                goal=project.goal,
                max_steps=project.max_steps
            )
            
            # Update project status based on result
            if execution_result.get("success", False):
                self.project_manager.update_project(project_id, status='completed')
                logger.info(f"✅ Project {project_id} execution completed successfully")
            else:
                self.project_manager.update_project(project_id, status='failed')
                logger.error(f"❌ Project {project_id} execution failed")
            
            # Save project state after execution
            self.save_project_state_async(project_id, project_task_graph.to_visualization_dict())
            
            # Auto-save results
            self._auto_save_current_project()
            
            return {
                "success": execution_result.get("success", False),
                "project_id": project_id,
                "execution_result": execution_result,
                "message": f"Execution {'completed' if execution_result.get('success') else 'failed'} for project {project_id}"
            }
            
        except Exception as e:
            logger.error(f"Failed to start execution for project {project_id}: {e}")
            self.project_manager.update_project(project_id, status='failed')
            return {
                "success": False,
                "error": str(e),
                "project_id": project_id
            }

    def save_project_results(self, project_id: str, results_package: Dict[str, Any]) -> bool:
        """
        Save project results to persistent storage.
        
        Args:
            project_id: Project identifier
            results_package: Complete results package to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            results_file = self.results_dir / f"{project_id}_results.json"
            
            # Add save metadata
            results_package['save_metadata'] = {
                'saved_at': datetime.now().isoformat(),
                'version': '1.0',
                'project_id': project_id
            }
            
            # Write to file
            with open(results_file, 'w') as f:
                json.dump(results_package, f, indent=2, default=str)
            
            logger.debug(f"💾 Saved results for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save results for project {project_id}: {e}")
            return False
    
    def load_project_results(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Load saved project results from persistent storage.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Results package if found, None otherwise
        """
        try:
            results_file = self.results_dir / f"{project_id}_results.json"
            
            if not results_file.exists():
                return None
            
            with open(results_file, 'r') as f:
                results_package = json.load(f)
            
            logger.debug(f"📂 Loaded saved results for project {project_id}")
            return results_package
            
        except Exception as e:
            logger.error(f"Failed to load results for project {project_id}: {e}")
            return None
    
    def _auto_save_current_project(self):
        """
        Automatically save the current project's results.
        """
        try:
            current_project_id = self.project_manager.get_current_project_id()
            if not current_project_id:
                return
            
            # Get current graph data
            graph_data = {}
            if hasattr(self.system_manager, 'task_graph') and self.system_manager.task_graph:
                if hasattr(self.system_manager.task_graph, 'to_visualization_dict'):
                    graph_data = self.system_manager.task_graph.to_visualization_dict()
            
            # Only save if there's meaningful data
            if graph_data.get('all_nodes'):
                project_data = self.get_project(current_project_id)
                if project_data:
                    results_package = {
                        "project": project_data['project'],
                        "saved_at": datetime.now().isoformat(),
                        "graph_data": graph_data,
                        "auto_saved": True,
                        "metadata": {
                            "total_nodes": len(graph_data.get('all_nodes', {})),
                            "project_goal": graph_data.get('overall_project_goal'),
                            "completion_status": self._get_completion_status(graph_data.get('all_nodes', {}))
                        }
                    }
                    
                    self.save_project_results(current_project_id, results_package)
                    logger.debug(f"🔄 Auto-saved project {current_project_id}")
        
        except Exception as e:
            logger.warning(f"Failed to auto-save current project: {e}")
    
    def _auto_load_project_results(self, project_id: str):
        """
        Automatically load project results when switching projects.
        """
        try:
            results_package = self.load_project_results(project_id)
            if results_package and results_package.get('graph_data'):
                # Restore graph data to system manager
                if hasattr(self.system_manager, 'task_graph') and self.system_manager.task_graph:
                    # This would need to be implemented based on your graph restoration logic
                    logger.info(f"🔄 Auto-loaded results for project {project_id}")
        
        except Exception as e:
            logger.warning(f"Failed to auto-load project results for {project_id}: {e}")
    
    def _get_completion_status(self, nodes: Dict[str, Any]) -> str:
        """
        Determine project completion status from nodes.
        
        Args:
            nodes: Dictionary of task nodes
            
        Returns:
            Completion status string
        """
        if not nodes:
            return "no_nodes"
        
        total_nodes = len(nodes)
        completed_nodes = sum(1 for node in nodes.values() if node.get('status') == 'DONE')
        failed_nodes = sum(1 for node in nodes.values() if node.get('status') == 'FAILED')
        running_nodes = sum(1 for node in nodes.values() if node.get('status') in ['RUNNING', 'READY'])
        
        if completed_nodes == total_nodes:
            return "completed"
        elif failed_nodes > 0 and running_nodes == 0:
            return "failed"
        elif running_nodes > 0:
            return "running"
        else:
            return "in_progress"
    
    def get_saved_projects_summary(self) -> List[Dict[str, Any]]:
        """
        Get a summary of all projects with saved results.
        
        Returns:
            List of project summaries with saved results info
        """
        summaries = []
        
        try:
            for results_file in self.results_dir.glob("*_results.json"):
                project_id = results_file.stem.replace("_results", "")
                
                try:
                    with open(results_file, 'r') as f:
                        results_package = json.load(f)
                    
                    summary = {
                        "project_id": project_id,
                        "title": results_package.get('project', {}).get('title', 'Unknown'),
                        "saved_at": results_package.get('saved_at'),
                        "completion_status": results_package.get('metadata', {}).get('completion_status'),
                        "total_nodes": results_package.get('metadata', {}).get('total_nodes', 0),
                        "auto_saved": results_package.get('auto_saved', False)
                    }
                    
                    summaries.append(summary)
                
                except Exception as e:
                    logger.warning(f"Failed to read results file {results_file}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to get saved projects summary: {e}")
        
        return sorted(summaries, key=lambda x: x.get('saved_at', ''), reverse=True)

    def debug_project_serialization_flow(self, project_id: str) -> Dict[str, Any]:
        """
        Comprehensive debugging method to trace project serialization issues.
        
        Args:
            project_id: Project identifier to debug
            
        Returns:
            Debug information about the serialization flow
        """
        debug_info = {
            'project_id': project_id,
            'timestamp': datetime.now().isoformat(),
            'debug_steps': []
        }
        
        try:
            # Step 1: Check if project exists
            project = self.project_manager.get_project(project_id)
            debug_info['debug_steps'].append({
                'step': 'project_metadata_check',
                'success': project is not None,
                'data': project.to_dict() if project else None
            })
            
            if not project:
                debug_info['issue'] = 'Project metadata not found'
                return debug_info
            
            # Step 2: Check if project has saved state
            saved_state = self.project_manager.load_project_state(project_id)
            debug_info['debug_steps'].append({
                'step': 'saved_state_check',
                'success': saved_state is not None,
                'node_count': len(saved_state.get('all_nodes', {})) if saved_state else 0,
                'has_root_graph': saved_state.get('root_graph_id') is not None if saved_state else False
            })
            
            # Step 3: Check if project has comprehensive results
            results = self.load_project_results(project_id)
            debug_info['debug_steps'].append({
                'step': 'comprehensive_results_check',
                'success': results is not None,
                'has_basic_state': results.get('basic_state') is not None if results else False,
                'has_graph_data': results.get('graph_data') is not None if results else False,
                'node_count_from_results': len(results.get('graph_data', {}).get('all_nodes', {})) if results and results.get('graph_data') else 0
            })
            
            # Step 4: Check project graph in memory
            if project_id in self.project_graphs:
                project_components = self.project_graphs[project_id]
                project_task_graph = project_components['task_graph']
                debug_info['debug_steps'].append({
                    'step': 'in_memory_graph_check',
                    'success': project_task_graph is not None,
                    'node_count': len(project_task_graph.nodes) if project_task_graph else 0,
                    'has_root_graph': project_task_graph.root_graph_id is not None if project_task_graph else False
                })
                
                # Step 5: Test serialization
                if project_task_graph:
                    try:
                        if hasattr(project_task_graph, 'to_visualization_dict'):
                            serialized_data = project_task_graph.to_visualization_dict()
                        else:
                            from ...hierarchical_agent_framework.graph.graph_serializer import GraphSerializer
                            serializer = GraphSerializer(project_task_graph)
                            serialized_data = serializer.to_visualization_dict()
                        
                        debug_info['debug_steps'].append({
                            'step': 'serialization_test',
                            'success': serialized_data is not None,
                            'node_count': len(serialized_data.get('all_nodes', {})) if serialized_data else 0,
                            'has_root_graph': serialized_data.get('root_graph_id') is not None if serialized_data else False
                        })
                        
                        # Step 6: Check individual nodes for full results
                        if serialized_data and serialized_data.get('all_nodes'):
                            nodes_with_results = 0
                            nodes_with_execution_details = 0
                            for node_id, node_data in serialized_data['all_nodes'].items():
                                if node_data.get('full_result'):
                                    nodes_with_results += 1
                                if node_data.get('execution_details'):
                                    nodes_with_execution_details += 1
                        
                            debug_info['debug_steps'].append({
                                'step': 'node_content_analysis',
                                'total_nodes': len(serialized_data['all_nodes']),
                                'nodes_with_full_result': nodes_with_results,
                                'nodes_with_execution_details': nodes_with_execution_details
                            })
                            
                    except Exception as e:
                        debug_info['debug_steps'].append({
                            'step': 'serialization_test',
                            'success': False,
                            'error': str(e)
                        })
            else:
                debug_info['debug_steps'].append({
                    'step': 'in_memory_graph_check',
                    'success': False,
                    'error': 'Project not loaded in memory'
                })
            
            # Step 7: Check system manager's task graph (current execution state)
            if hasattr(self.system_manager, 'task_graph') and self.system_manager.task_graph:
                current_graph = self.system_manager.task_graph
                debug_info['debug_steps'].append({
                    'step': 'system_manager_graph_check',
                    'node_count': len(current_graph.nodes),
                    'overall_goal': current_graph.overall_project_goal,
                    'has_root_graph': current_graph.root_graph_id is not None
                })
            
            return debug_info
            
        except Exception as e:
            debug_info['error'] = str(e)
            debug_info['exception_traceback'] = __import__('traceback').format_exc()
            return debug_info
