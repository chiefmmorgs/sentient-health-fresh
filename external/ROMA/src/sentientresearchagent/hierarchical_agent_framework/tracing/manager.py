"""
Trace manager for handling node processing traces.
"""

from typing import Dict, Optional, List
from loguru import logger
import json
import os
from pathlib import Path
from .models import NodeProcessingTrace, ProcessingStage


class TraceManager:
    """Manages processing traces for nodes."""
    
    def __init__(self, project_id: str, traces_dir: Optional[str] = None):
        self.project_id = project_id
        self._traces: Dict[str, NodeProcessingTrace] = {}
        self._node_to_trace: Dict[str, str] = {}  # node_id -> trace_id
        
        # Set up project-specific traces directory
        if traces_dir:
            self.traces_dir = Path(traces_dir)
        else:
            # Use centralized paths
            from ...config.paths import RuntimePaths
            paths = RuntimePaths.get_default()
            self.traces_dir = paths.experiment_results_dir / "traces" / project_id
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        
        # Optional callback for real-time updates
        self._broadcast_callback = None
    
    def set_broadcast_callback(self, callback_fn):
        """Set callback function for broadcasting real-time trace updates."""
        self._broadcast_callback = callback_fn
    
    def create_trace(self, node_id: str, node_goal: str) -> NodeProcessingTrace:
        """Create a new trace for a node."""
        # Check if trace already exists
        existing_trace = self.get_trace_for_node(node_id)
        if existing_trace:
            logger.info(f"🔍 TRACE: Trace already exists for node {node_id}, returning existing")
            return existing_trace
            
        trace = NodeProcessingTrace(node_id=node_id, node_goal=node_goal)
        self._traces[trace.trace_id] = trace
        self._node_to_trace[node_id] = trace.trace_id
        
        logger.info(f"🔍 TRACE: Created processing trace {trace.trace_id} for node {node_id}")
        return trace
    
    def get_trace(self, trace_id: str) -> Optional[NodeProcessingTrace]:
        """Get trace by trace ID."""
        return self._traces.get(trace_id)
    
    def get_trace_for_node(self, node_id: str) -> Optional[NodeProcessingTrace]:
        """Get trace for a specific node."""
        # First check in-memory traces
        trace_id = self._node_to_trace.get(node_id)
        if trace_id:
            trace = self._traces.get(trace_id)
            if trace:
                logger.info(f"🔍 TRACE: Retrieved in-memory trace for node {node_id}: {len(trace.stages)} stages")
                return trace
            else:
                logger.warning(f"🔍 TRACE: Trace ID {trace_id} found but trace data missing for node {node_id}")
        
        # If not in memory, try to load from disk
        logger.info(f"🔍 TRACE: No in-memory trace for node {node_id}, checking disk...")
        trace = self._load_trace_from_disk(node_id)
        if trace:
            # Add to memory for future access
            self._traces[trace.trace_id] = trace
            self._node_to_trace[node_id] = trace.trace_id
            logger.info(f"🔍 TRACE: Loaded trace from disk for node {node_id}: {len(trace.stages)} stages")
            return trace
        
        logger.warning(f"🔍 TRACE: No trace found for node {node_id} (in-memory or disk)")
        logger.info(f"🔍 TRACE: Current in-memory traces: {list(self._node_to_trace.keys())}")
        return None
    
    def start_stage(self, node_id: str, stage_name: str, **kwargs) -> Optional[ProcessingStage]:
        """Start a new processing stage for a node."""
        trace = self.get_trace_for_node(node_id)
        if not trace:
            logger.info(f"🔍 TRACE: No trace found for node {node_id}, creating one")
            trace = self.create_trace(node_id, f"Node {node_id}")
        
        stage = trace.add_stage(stage_name, **kwargs)
        logger.info(f"🔍 TRACE: Started stage '{stage_name}' for node {node_id} (stage_id: {stage.stage_id})")
        
        # Auto-save trace after adding stage
        self._save_trace_to_disk(trace)
        
        return stage
    
    def complete_stage(self, node_id: str, stage_name: str, output_data: any = None, error: str = None):
        """Complete a processing stage."""
        trace = self.get_trace_for_node(node_id)
        if not trace:
            logger.warning(f"🔍 TRACE: No trace found for node {node_id} when completing stage")
            return
        
        stage = trace.get_stage(stage_name)
        if stage:
            stage.complete_stage(output_data=output_data, error=error)
            logger.info(f"🔍 TRACE: Completed stage '{stage_name}' for node {node_id}")
            
            # Auto-save trace after completing stage
            self._save_trace_to_disk(trace)
        else:
            logger.warning(f"🔍 TRACE: No stage '{stage_name}' found for node {node_id}")
    
    def update_stage(self, node_id: str, stage_name: str, **updates):
        """Update stage data."""
        trace = self.get_trace_for_node(node_id)
        if not trace:
            return
        
        stage = trace.get_stage(stage_name)
        if stage:
            # Log what we're updating
            if "additional_data" in updates:
                logger.info(f"🔍 TRACE: Updating stage with additional_data containing: {list(updates['additional_data'].keys()) if isinstance(updates['additional_data'], dict) else 'Not a dict'}")
            
            # Use the ProcessingStage's update_fields method which handles extra fields
            stage.update_fields(**updates)
            logger.info(f"🔍 TRACE: Updated stage '{stage_name}' for node {node_id} with fields: {list(updates.keys())}")
            
            # Auto-save trace after updates
            self._save_trace_to_disk(trace)
        else:
            logger.warning(f"🔍 TRACE: No stage '{stage_name}' found for node {node_id}")
    
    def get_all_traces(self) -> List[NodeProcessingTrace]:
        """Get all traces."""
        return list(self._traces.values())
    
    def clear_traces(self):
        """Clear all traces."""
        trace_count = len(self._traces)
        self._traces.clear()
        self._node_to_trace.clear()
        logger.info(f"🔍 TRACE: Cleared {trace_count} processing traces from memory")
    
    def debug_trace_state(self) -> Dict[str, any]:
        """Get current trace state for debugging."""
        return {
            "total_traces": len(self._traces),
            "node_mappings": dict(self._node_to_trace),
            "traces_dir": str(self.traces_dir),
            "disk_traces": self._list_disk_traces(),
            "trace_details": {
                trace_id: {
                    "node_id": trace.node_id,
                    "stages": len(trace.stages),
                    "stage_names": [s.stage_name for s in trace.stages]
                }
                for trace_id, trace in self._traces.items()
            }
        }
    
    def _save_trace_to_disk(self, trace: NodeProcessingTrace):
        """Save trace to disk for persistence."""
        try:
            trace_file = self.traces_dir / f"trace_{trace.node_id}.json"
            trace_data = trace.to_dict()
            
            with open(trace_file, 'w') as f:
                json.dump(trace_data, f, indent=2, default=str)
            
            logger.debug(f"🔍 TRACE: Saved trace for node {trace.node_id} to disk")
        except Exception as e:
            logger.warning(f"🔍 TRACE: Failed to save trace for node {trace.node_id}: {e}")
    
    def _load_trace_from_disk(self, node_id: str) -> Optional[NodeProcessingTrace]:
        """Load trace from disk."""
        try:
            trace_file = self.traces_dir / f"trace_{node_id}.json"
            
            if not trace_file.exists():
                return None
            
            with open(trace_file, 'r') as f:
                trace_data = json.load(f)
            
            # Reconstruct the trace object
            trace = NodeProcessingTrace(
                node_id=trace_data['node_id'],
                node_goal=trace_data['node_goal'],
                trace_id=trace_data['trace_id'],
                created_at=trace_data['created_at']
            )
            
            # Reconstruct stages
            for stage_data in trace_data['stages']:
                # Create stage with all fields except computed ones
                stage_fields = {
                    k: v for k, v in stage_data.items() 
                    if k not in ['duration_ms']  # Skip computed fields
                }
                
                # Debug log for additional_data
                if 'additional_data' in stage_fields:
                    logger.debug(f"🔍 TRACE LOAD: Stage {stage_fields.get('stage_name')} has additional_data with keys: {list(stage_fields['additional_data'].keys()) if isinstance(stage_fields['additional_data'], dict) else 'Not a dict'}")
                
                stage = ProcessingStage(**stage_fields)
                trace.stages.append(stage)
            
            trace.metadata = trace_data.get('metadata', {})
            
            logger.debug(f"🔍 TRACE: Loaded trace for node {node_id} from disk")
            return trace
            
        except Exception as e:
            logger.warning(f"🔍 TRACE: Failed to load trace for node {node_id}: {e}")
            return None
    
    def _list_disk_traces(self) -> List[str]:
        """List available trace files on disk."""
        try:
            trace_files = list(self.traces_dir.glob("trace_*.json"))
            return [f.stem.replace("trace_", "") for f in trace_files]
        except Exception:
            return []
    
    def save_project_traces(self, project_id: str):
        """Save all current traces for a project."""
        try:
            project_traces_dir = self.traces_dir / project_id
            project_traces_dir.mkdir(exist_ok=True)
            
            saved_count = 0
            for trace in self._traces.values():
                trace_file = project_traces_dir / f"trace_{trace.node_id}.json"
                trace_data = trace.to_dict()
                
                with open(trace_file, 'w') as f:
                    json.dump(trace_data, f, indent=2, default=str)
                
                saved_count += 1
            
            logger.info(f"🔍 TRACE: Saved {saved_count} traces for project {project_id}")
            
        except Exception as e:
            logger.error(f"🔍 TRACE: Failed to save project traces for {project_id}: {e}")
    
    def load_project_traces(self, project_id: str):
        """Load all traces for a project."""
        try:
            project_traces_dir = self.traces_dir / project_id
            
            if not project_traces_dir.exists():
                logger.info(f"🔍 TRACE: No trace directory found for project {project_id}")
                return
            
            trace_files = list(project_traces_dir.glob("trace_*.json"))
            loaded_count = 0
            
            for trace_file in trace_files:
                node_id = trace_file.stem.replace("trace_", "")
                trace = self._load_trace_from_project_dir(trace_file)
                
                if trace:
                    self._traces[trace.trace_id] = trace
                    self._node_to_trace[node_id] = trace.trace_id
                    loaded_count += 1
            
            logger.info(f"🔍 TRACE: Loaded {loaded_count} traces for project {project_id}")
            
        except Exception as e:
            logger.error(f"🔍 TRACE: Failed to load project traces for {project_id}: {e}")
    
    def _load_trace_from_project_dir(self, trace_file: Path) -> Optional[NodeProcessingTrace]:
        """Load trace from project-specific trace file."""
        try:
            with open(trace_file, 'r') as f:
                trace_data = json.load(f)
            
            # Reconstruct the trace object (same as _load_trace_from_disk)
            trace = NodeProcessingTrace(
                node_id=trace_data['node_id'],
                node_goal=trace_data['node_goal'],
                trace_id=trace_data['trace_id'],
                created_at=trace_data['created_at']
            )
            
            # Reconstruct stages
            for stage_data in trace_data['stages']:
                # Create stage with all fields except computed ones
                stage_fields = {
                    k: v for k, v in stage_data.items() 
                    if k not in ['duration_ms']  # Skip computed fields
                }
                
                # Debug log for additional_data
                if 'additional_data' in stage_fields:
                    logger.debug(f"🔍 TRACE LOAD: Stage {stage_fields.get('stage_name')} has additional_data with keys: {list(stage_fields['additional_data'].keys()) if isinstance(stage_fields['additional_data'], dict) else 'Not a dict'}")
                
                stage = ProcessingStage(**stage_fields)
                trace.stages.append(stage)
            
            trace.metadata = trace_data.get('metadata', {})
            return trace
            
        except Exception as e:
            logger.warning(f"🔍 TRACE: Failed to load trace from {trace_file}: {e}")
            return None
    
    def clear_stages_by_type(self, node_id: str, stage_types: List[str]):
        """Clear stages of specific types from a node's trace."""
        trace = self.get_trace_for_node(node_id)
        if not trace:
            logger.warning(f"🔍 TRACE: No trace found for node {node_id} when clearing stages")
            return
        
        original_count = len(trace.stages)
        # Remove stages that match the specified types
        trace.stages = [stage for stage in trace.stages if stage.stage_name not in stage_types]
        cleared_count = original_count - len(trace.stages)
        
        if cleared_count > 0:
            logger.info(f"🔍 TRACE: Cleared {cleared_count} stages of types {stage_types} from node {node_id}")
            # Auto-save trace after clearing stages
            self._save_trace_to_disk(trace)
        else:
            logger.debug(f"🔍 TRACE: No stages of types {stage_types} found to clear from node {node_id}")


# TraceManager is now instantiated per-project instead of as a global singleton
# This prevents race conditions when running multiple projects in parallel 