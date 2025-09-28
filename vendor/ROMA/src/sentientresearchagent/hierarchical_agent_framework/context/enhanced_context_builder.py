from typing import Optional
from .parent_context_builder import ParentContextBuilder
from .knowledge_store import KnowledgeStore
from .agent_io_models import AgentTaskInput
from .context_builder import resolve_context_for_agent

def resolve_context_for_agent_with_parents(
    current_task_id: str,
    current_goal: str,
    current_task_type: str, 
    agent_name: str,
    knowledge_store: KnowledgeStore,
    overall_project_goal: Optional[str] = None,
) -> AgentTaskInput:
    """Enhanced version that includes parent hierarchy context."""
    
    # Get existing horizontal context (siblings, ancestors, etc.)
    existing_context = resolve_context_for_agent(
        current_task_id=current_task_id,
        current_goal=current_goal,
        current_task_type=current_task_type,
        agent_name=agent_name,
        knowledge_store=knowledge_store,
        overall_project_goal=overall_project_goal
    )
    
    # 🔥 NEW: Add parent hierarchy context
    parent_builder = ParentContextBuilder(knowledge_store)
    parent_context = parent_builder.build_parent_context(
        current_task_id=current_task_id,
        overall_project_goal=overall_project_goal or "Unknown"
    )
    
    # Create comprehensive formatted context
    formatted_context_parts = []
    
    # Add parent hierarchy context first (highest priority)
    if parent_context:
        formatted_context_parts.append(parent_context.formatted_context)
    
    # Add existing horizontal context
    if existing_context.relevant_context_items:
        formatted_context_parts.append("\n=== PEER & HISTORICAL CONTEXT ===")
        for item in existing_context.relevant_context_items:
            formatted_context_parts.extend([
                f"\nSource: {item.source_task_goal}",
                f"Type: {item.content_type_description}",
                f"Content: {str(item.content)}",
                "---"
            ])
    
    formatted_full_context = "\n".join(formatted_context_parts) if formatted_context_parts else None
    
    # Return enhanced AgentTaskInput
    return AgentTaskInput(
        current_task_id=existing_context.current_task_id,
        current_goal=existing_context.current_goal,
        current_task_type=existing_context.current_task_type,
        overall_project_goal=existing_context.overall_project_goal,
        relevant_context_items=existing_context.relevant_context_items,
        parent_hierarchy_context=parent_context,  # 🔥 NEW
        formatted_full_context=formatted_full_context  # 🔥 NEW
    ) 