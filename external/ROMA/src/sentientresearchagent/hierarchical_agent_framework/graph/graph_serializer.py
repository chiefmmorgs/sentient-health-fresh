from typing import Dict, Any, TYPE_CHECKING, Union, List
from enum import Enum
from pydantic import BaseModel

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
    from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode


class GraphSerializer:
    """Serializes a TaskGraph to a dictionary suitable for frontend visualization."""

    def __init__(self, task_graph: 'TaskGraph'):
        self.task_graph = task_graph

    def _serialize_node(self, node_obj: 'TaskNode') -> Dict[str, Any]:
        """Serializes a single TaskNode object."""
        input_context_info_list = []
        if node_obj.input_payload_dict and isinstance(node_obj.input_payload_dict, dict):
            relevant_context = node_obj.input_payload_dict.get('relevant_context_items', [])
            if isinstance(relevant_context, list):
                for item in relevant_context:
                    if isinstance(item, dict):  # Assuming ContextItem structure
                        source_id = item.get('source_task_id')
                        source_goal = item.get('source_task_goal', 'Unknown goal')
                        content_type = item.get('content_type_description', 'Unknown type')
                        if source_id:
                            input_context_info_list.append({
                                "source_task_id": source_id,
                                "source_task_goal_summary": source_goal[:50] + "..." if source_goal and len(source_goal) > 50 else source_goal,
                                "content_type": content_type
                            })
        
        input_payload_summary_str = "N/A"
        if node_obj.input_payload_dict and isinstance(node_obj.input_payload_dict, dict):
            keys = list(node_obj.input_payload_dict.keys())
            input_payload_summary_str = f"Input payload with keys: {', '.join(keys)}"

        task_type_val = node_obj.task_type.value if isinstance(node_obj.task_type, Enum) else str(node_obj.task_type) if node_obj.task_type else None
        node_type_val = node_obj.node_type.value if isinstance(node_obj.node_type, Enum) else str(node_obj.node_type) if node_obj.node_type else None
        status_val = node_obj.status.value if isinstance(node_obj.status, Enum) else str(node_obj.status) if node_obj.status else None

        processed_result = None
        if node_obj.result is not None:
            if isinstance(node_obj.result, BaseModel):
                try:
                    processed_result = node_obj.result.model_dump(mode='json')
                except AttributeError: # For older Pydantic versions
                    processed_result = node_obj.result.dict()
            elif isinstance(node_obj.result, (dict, list, str, int, float, bool)):
                processed_result = node_obj.result
            else:
                processed_result = str(node_obj.result)

        model_info = None
        execution_details = None
        
        # Fix: Check if aux_data is not None before accessing it
        if node_obj.aux_data is not None and "execution_details" in node_obj.aux_data:
            execution_details = node_obj.aux_data["execution_details"]
            if execution_details is not None:
                model_info = execution_details.get("model_info", {})

        if processed_result is None and node_obj.aux_data is not None and "full_result" in node_obj.aux_data:
            processed_result = node_obj.aux_data["full_result"]

        model_display = "Not processed"
        if model_info:
            adapter_name = model_info.get("adapter_name", "")
            provider = model_info.get("model_provider", "unknown")
            model_name = model_info.get("model_name", "unknown")
            
            if provider != "unknown" and model_name != "unknown":
                model_display = f"{provider}/{model_name}"
            elif model_name != "unknown":
                model_display = model_name
            elif adapter_name and adapter_name != "unknown":
                model_display = adapter_name
            else:
                model_display = model_info.get("model_id", "unknown")

        return {
            "task_id": node_obj.task_id,
            "goal": node_obj.goal,
            "task_type": task_type_val,
            "node_type": node_type_val,
            "agent_name": node_obj.agent_name,
            "status": status_val,
            "layer": node_obj.layer,
            "parent_node_id": node_obj.parent_node_id,
            "overall_objective": node_obj.overall_objective,
            "output_summary": node_obj.output_summary,
            "full_result": processed_result,
            "error": node_obj.error,
            "sub_graph_id": node_obj.sub_graph_id,
            "planned_sub_task_ids": node_obj.planned_sub_task_ids,
            "input_payload_summary": input_payload_summary_str,
            "input_context_sources": input_context_info_list,
            "timestamp_created": node_obj.timestamp_created.isoformat() if node_obj.timestamp_created else None,
            "timestamp_updated": node_obj.timestamp_updated.isoformat() if node_obj.timestamp_updated else None,
            "timestamp_completed": node_obj.timestamp_completed.isoformat() if node_obj.timestamp_completed else None,
            "model_display": model_display,
            "model_info": self._process_value(model_info),
            "execution_details": self._process_value(execution_details),
            
            # CRITICAL FIX: Include aux_data for frontend access, but process Pydantic models
            # Handle case where aux_data might be None
            "aux_data": self._process_aux_data(node_obj.aux_data if node_obj.aux_data is not None else {})
        }

    def _process_aux_data(self, aux_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process aux_data to convert Pydantic models to JSON-serializable dictionaries.
        
        Args:
            aux_data: The auxiliary data dictionary from a TaskNode
            
        Returns:
            A processed dictionary where Pydantic models are converted to dicts
        """
        if not aux_data:
            return {}
            
        processed = {}
        for key, value in aux_data.items():
            processed[key] = self._process_value(value)
        return processed
    
    def _process_value(self, value: Any) -> Any:
        """
        Recursively process a value to convert Pydantic models to dicts.
        
        Args:
            value: The value to process
            
        Returns:
            A JSON-serializable version of the value
        """
        if isinstance(value, BaseModel):
            # Convert Pydantic model to dictionary
            try:
                return value.model_dump(mode='json')
            except AttributeError:  # For older Pydantic versions
                return value.dict()
        elif isinstance(value, dict):
            # Recursively process dictionary values
            return {k: self._process_value(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            # Recursively process list/tuple items
            return [self._process_value(item) for item in value]
        elif isinstance(value, Enum):
            # Convert enums to their values
            return value.value
        else:
            # Return as-is for basic types (str, int, float, bool, None)
            return value

    def to_visualization_dict(self) -> Dict[str, Any]:
        """Serializes the entire task graph."""
        output_graphs = {}
        for graph_id, graph_obj in self.task_graph.graphs.items():
            output_graphs[graph_id] = {
                "nodes": list(graph_obj.nodes()),
                "edges": [{"source": u, "target": v} for u, v in graph_obj.edges()]
            }

        output_nodes = {}
        for node_id, node_obj in self.task_graph.nodes.items():
            output_nodes[node_id] = self._serialize_node(node_obj)

        return {
            "overall_project_goal": self.task_graph.overall_project_goal,
            "root_graph_id": self.task_graph.root_graph_id,
            "graphs": output_graphs,
            "all_nodes": output_nodes
        }
