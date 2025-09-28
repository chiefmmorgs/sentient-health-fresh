import re
from typing import List, Optional, Any, Dict
from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import AgentTaskInput, ContextItem # Removed Planner specific models
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore, TaskRecord # Adjusted import
# Removed TaskStatus import as it's not directly used here anymore
# Assuming TaskNode related enums/types are not directly needed here, TaskRecord uses Literals

# Removed summarization utility import, it's now in planner_context_builder
# from ..agents.utils import get_context_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES

# NEW IMPORT for context strategies
from .strategies import (
    ContextResolutionStrategy,
    # ParentContextStrategy,  # Removed - parent plans should not be included in child nodes
    PrerequisiteSiblingContextStrategy,
    AncestorBranchContextStrategy,
    GoalReferenceContextStrategy,
    DependencyContextStrategy,
)

# Removed get_task_record_path_to_root as it's used by planner context builder now
# from .context_utils import get_task_record_path_to_root 

# --- Default and Task-Specific Strategy Configurations ---

DEFAULT_CONTEXT_STRATEGIES: List[ContextResolutionStrategy] = [
    DependencyContextStrategy(),  # Highest priority - explicit dependencies
    PrerequisiteSiblingContextStrategy(),
    AncestorBranchContextStrategy(), 
    GoalReferenceContextStrategy(),
    # ParentContextStrategy removed - parent plans should not be included in child nodes
]

# TASK_TYPE_STRATEGY_MAPPING defines which strategies to use for specific task types.
# The key is the task_type string (e.g., "WRITE", "PLAN", "RESEARCH_WEB").
# The value is a list of instantiated ContextResolutionStrategy objects.
# If a task type is not found here, DEFAULT_CONTEXT_STRATEGIES will be used.
TASK_TYPE_STRATEGY_MAPPING: Dict[str, List[ContextResolutionStrategy]] = {
    # "DEFAULT" key isn't strictly necessary if we always fallback to DEFAULT_CONTEXT_STRATEGIES object
    "WRITE": [
        DependencyContextStrategy(),  # Highest priority - explicit dependencies
        PrerequisiteSiblingContextStrategy(),
        AncestorBranchContextStrategy(), # Crucial for writers
        GoalReferenceContextStrategy(),
        # ParentContextStrategy removed - parent plans should not be included in child nodes
    ],
    "THINK": [ # Similar to WRITE, might need broad context
        DependencyContextStrategy(),  # Highest priority - explicit dependencies
        PrerequisiteSiblingContextStrategy(),
        AncestorBranchContextStrategy(),
        GoalReferenceContextStrategy(),
        # ParentContextStrategy removed - parent plans should not be included in child nodes
    ],
    "PLAN": [ # Planners might need more focused context
        DependencyContextStrategy(),  # Highest priority - explicit dependencies
        PrerequisiteSiblingContextStrategy(), # See what came before in this plan
        GoalReferenceContextStrategy(), # Check if goal refers to other tasks
        # ParentContextStrategy removed - parent plans should not be included in child nodes
        # AncestorBranchContextStrategy might be too broad for initial planning,
        # but could be useful for re-planning or very deep plans.
    ],
    "RESEARCH_WEB": [ # Example: A web research task might prioritize different things
        DependencyContextStrategy(),  # Highest priority - explicit dependencies
        GoalReferenceContextStrategy(), # Any specific prior results to build upon?
        # ParentContextStrategy removed - parent plans should not be included in child nodes
        # PrerequisiteSiblingContextStrategy might be less relevant if it's a standalone search
    ],
    "SEARCH": [ # Search tasks should only use sibling dependencies, not parent context
        DependencyContextStrategy(),  # Highest priority - explicit dependencies
        PrerequisiteSiblingContextStrategy(), # Context from earlier sibling tasks
        GoalReferenceContextStrategy(), # Any specific prior results to build upon?
        # NO ParentContextStrategy - as per user requirement, only sibling dependencies
    ]
    # Add other task types and their specific strategy lists as needed.
    # For example, an "AGGREGATE" task might have no strategies here if its context
    # is entirely prepared by NodeProcessor.
}


def validate_task_dependencies(
    current_task_record: TaskRecord,
    knowledge_store: KnowledgeStore
) -> Dict[str, Any]:
    """
    Validates that all dependencies for a task are properly resolved.
    
    Returns:
        A dictionary with validation results:
        - valid: bool - whether all dependencies are satisfied
        - missing_dependencies: List[str] - list of missing dependency task IDs
        - incomplete_dependencies: List[str] - list of incomplete dependency task IDs
        - validation_errors: List[str] - list of validation error messages
    """
    validation_result = {
        "valid": True,
        "missing_dependencies": [],
        "incomplete_dependencies": [],
        "validation_errors": []
    }
    
    # Get dependency information
    depends_on_indices = getattr(current_task_record, 'depends_on_indices', None)
    if not depends_on_indices:
        aux_data = getattr(current_task_record, 'aux_data', {})
        depends_on_indices = aux_data.get('depends_on_indices', [])
    
    if not depends_on_indices:
        return validation_result  # No dependencies to validate
    
    logger.debug(f"Validating {len(depends_on_indices)} dependencies for task {current_task_record.task_id}")
    
    if not current_task_record.parent_task_id:
        validation_result["valid"] = False
        validation_result["validation_errors"].append(
            f"Task {current_task_record.task_id} has dependencies but no parent task"
        )
        return validation_result
    
    parent_record = knowledge_store.get_record(current_task_record.parent_task_id)
    if not parent_record or not parent_record.child_task_ids_generated:
        validation_result["valid"] = False
        validation_result["validation_errors"].append(
            f"Parent task {current_task_record.parent_task_id} has no generated children"
        )
        return validation_result
    
    for dependency_index in depends_on_indices:
        try:
            if dependency_index >= len(parent_record.child_task_ids_generated):
                validation_result["valid"] = False
                validation_result["validation_errors"].append(
                    f"Dependency index {dependency_index} out of range (parent has {len(parent_record.child_task_ids_generated)} children)"
                )
                continue
            
            dependency_task_id = parent_record.child_task_ids_generated[dependency_index]
            dependency_record = knowledge_store.get_record(dependency_task_id)
            
            if not dependency_record:
                validation_result["valid"] = False
                validation_result["missing_dependencies"].append(dependency_task_id)
                validation_result["validation_errors"].append(
                    f"Dependency task {dependency_task_id} not found in knowledge store"
                )
                continue
            
            # Check if dependency is completed
            if dependency_record.status != "DONE":
                validation_result["valid"] = False
                validation_result["incomplete_dependencies"].append(dependency_task_id)
                validation_result["validation_errors"].append(
                    f"Dependency task {dependency_task_id} not completed (status: {dependency_record.status})"
                )
                continue
            
            # Check if dependency has output
            if not (dependency_record.output_content or dependency_record.output_summary):
                validation_result["valid"] = False
                validation_result["validation_errors"].append(
                    f"Dependency task {dependency_task_id} has no output content"
                )
                continue
            
            logger.debug(f"  Dependency {dependency_task_id} validated successfully")
            
        except (TypeError, IndexError, AttributeError) as e:
            validation_result["valid"] = False
            validation_result["validation_errors"].append(
                f"Error validating dependency {dependency_index}: {str(e)}"
            )
    
    if validation_result["valid"]:
        logger.info(f"All {len(depends_on_indices)} dependencies validated for task {current_task_record.task_id}")
    else:
        logger.warning(f"Dependency validation failed for task {current_task_record.task_id}: {validation_result['validation_errors']}")
    
    return validation_result


def resolve_context_for_agent(
    current_task_id: str,
    current_goal: str,
    current_task_type: str, 
    agent_name: str,
    knowledge_store: KnowledgeStore,
    overall_project_goal: Optional[str] = None,
) -> AgentTaskInput:
    logger.info(f"ContextBuilder: Resolving context for task '{current_task_id}' (Agent: {agent_name}, Type: {current_task_type})")
    
    relevant_items: List[ContextItem] = []
    processed_context_source_ids = set()

    current_task_record = knowledge_store.get_record(current_task_id)
    if not current_task_record:
        logger.warning(f"ContextBuilder Warning: TaskRecord for current task {current_task_id} not found. Returning empty context.")
        return AgentTaskInput(
            current_task_id=current_task_id, 
            current_goal=current_goal,
            current_task_type=current_task_type or "UNKNOWN", # Ensure task type is a string
            overall_project_goal=overall_project_goal,
            relevant_context_items=[]
        )

    # ENHANCED: Validate task dependencies before context resolution
    dependency_validation = validate_task_dependencies(current_task_record, knowledge_store)
    if not dependency_validation["valid"]:
        logger.warning(f"ContextBuilder: Dependency validation failed for task {current_task_id}: {dependency_validation['validation_errors']}")
        # Continue with context resolution but log the issues
        # In a production system, you might want to fail the task or retry later

    # Get the list of strategies based on the current task type.
    # Fallback to DEFAULT_CONTEXT_STRATEGIES if the specific type is not in the mapping.
    context_strategies = TASK_TYPE_STRATEGY_MAPPING.get(str(current_task_type), DEFAULT_CONTEXT_STRATEGIES) # Ensure current_task_type is string for dict key
    
    if str(current_task_type) not in TASK_TYPE_STRATEGY_MAPPING:
        logger.debug(f"Task type '{current_task_type}' not found in TASK_TYPE_STRATEGY_MAPPING. Using default strategies.")
    
    logger.debug(f"Using context strategies for task type '{current_task_type}': {[s.__class__.__name__ for s in context_strategies]}")

    # Enhanced context debugging - track what context is being resolved
    context_debug_info = {
        "task_id": current_task_id,
        "task_type": current_task_type,
        "strategies_used": [s.__class__.__name__ for s in context_strategies],
        "context_items_found": [],
        "dependency_validation": dependency_validation
    }

    for strategy in context_strategies:
        try:
            # Ensure current_task_type is passed as a string to strategies if they expect it
            strategy_items = strategy.get_context(
                current_task_record=current_task_record,
                knowledge_store=knowledge_store,
                processed_context_source_ids=processed_context_source_ids,
                overall_project_goal=overall_project_goal,
                current_task_type=str(current_task_type) 
            )
            
            # Enhanced logging for context items found by each strategy
            if strategy_items:
                logger.info(f"  Strategy {strategy.__class__.__name__} found {len(strategy_items)} context items:")
                for item in strategy_items:
                    logger.info(f"    - {item.source_task_id}: {item.content_type_description} ({len(str(item.content))} chars)")
                    context_debug_info["context_items_found"].append({
                        "strategy": strategy.__class__.__name__,
                        "source_task_id": item.source_task_id,
                        "source_task_goal": item.source_task_goal,
                        "content_type": item.content_type_description,
                        "content_length": len(str(item.content))
                    })
            else:
                logger.debug(f"  Strategy {strategy.__class__.__name__} found no context items")
            
            relevant_items.extend(strategy_items)
        except Exception as e:
            logger.error(f"ContextBuilder: Error executing strategy {strategy.__class__.__name__} for task {current_task_id}: {e}", exc_info=True)
    
    # Enhanced final logging with context summary
    if relevant_items:
        logger.success(f"ContextBuilder: Found {len(relevant_items)} relevant context items for task '{current_task_id}':")
        
        # Group context items by strategy for summary
        strategy_summary = {}
        for item_info in context_debug_info["context_items_found"]:
            strategy_name = item_info["strategy"]
            if strategy_name not in strategy_summary:
                strategy_summary[strategy_name] = []
            strategy_summary[strategy_name].append(item_info["source_task_id"])
        
        for strategy_name, task_ids in strategy_summary.items():
            logger.info(f"  - {strategy_name}: {len(task_ids)} items from tasks {task_ids}")
        
        # Log dependency context specifically
        dependency_items = [item for item in context_debug_info["context_items_found"] if item["strategy"] == "DependencyContextStrategy"]
        if dependency_items:
            logger.info(f"  🔗 DEPENDENCY CONTEXT: Found {len(dependency_items)} dependency context items:")
            for item in dependency_items:
                logger.info(f"    - {item['source_task_id']}: {item['content_type']} ({item['content_length']} chars)")
        
    else:
        logger.warning(f"ContextBuilder: No relevant context items found for task '{current_task_id}'.")
        if not dependency_validation["valid"]:
            logger.warning(f"  This might be because dependency validation failed: {dependency_validation['validation_errors']}")
        
    return AgentTaskInput(
        current_task_id=current_task_id,
        current_goal=current_goal,
        current_task_type=str(current_task_type), # Ensure task type is a string
        overall_project_goal=overall_project_goal,
        relevant_context_items=relevant_items
    )

# --- Planner-specific input building functions have been moved to planner_context_builder.py ---
