from pydantic import BaseModel, Field

class NodeProcessorConfig(BaseModel):
    """Configuration for the NodeProcessor and its components."""
    
    # Master switch for HITL feature
    enable_hitl: bool = True
    
    # Specific HITL checkpoints
    enable_hitl_after_plan_generation: bool = True
    enable_hitl_after_atomizer: bool = False
    enable_hitl_before_execute: bool = False
    enable_hitl_after_modified_plan: bool = True
    max_planning_layer: int = 5
    max_replan_attempts: int = 5

    # CHANGED: Default to root plan only mode
    hitl_root_plan_only: bool = True
    
    # NEW: Force root nodes to always plan (skip atomizer)
    force_root_node_planning: bool = True
    
    # NEW: Skip atomization entirely and use depth-based rules
    skip_atomization: bool = False