from pydantic import BaseModel, Field, validator
from typing import List, Any, Optional, Dict, Union

# Import reasoning types from agno for reasoning-enabled agents
try:
    from agno.reasoning.step import ReasoningStep
    REASONING_AVAILABLE = True
except ImportError:
    REASONING_AVAILABLE = False
    # Define minimal fallback types if agno is not available
    class ReasoningStep(BaseModel):
        title: Optional[str] = None
        action: Optional[str] = None
        result: Optional[str] = None
        reasoning: Optional[Union[str, Dict[str, Any]]] = None  # Allow both string and structured reasoning
        
        @validator('reasoning', pre=True)
        def process_reasoning(cls, v):
            """Convert structured reasoning to string if needed."""
            if isinstance(v, dict):
                # Convert structured reasoning to readable string
                parts = []
                if 'necessity' in v:
                    parts.append(f"Necessity: {v['necessity']}")
                if 'assumptions' in v and v['assumptions'] != 'N/A':
                    parts.append(f"Assumptions: {v['assumptions']}")
                if 'approach' in v:
                    parts.append(f"Approach: {v['approach']}")
                return " | ".join(parts) if parts else str(v)
            return v

# --- Plan Output Schemas (used by Planner Agents and NodeProcessor) ---
class SubTask(BaseModel):
    """Schema for a single sub-task planned by a Planner agent."""
    goal: str = Field(..., description="Precise description of the sub-task goal.")
    # Assuming TaskType and NodeType enums will be defined in a shared types module or node.task_node
    # For now, using strings and will be validated/converted by adapter or node_processor
    task_type: str = Field(..., description="Type of task (e.g., 'WRITE', 'THINK', 'SEARCH').")
    node_type: str = Field(default="PLAN", description="Node type ('EXECUTE' for atomic, 'PLAN' for complex). Defaults to 'PLAN' since atomizer will make final decision.")
    # You could add estimated_effort, dependencies_within_plan etc. later
    depends_on_indices: Optional[List[int]] = Field(default_factory=list, description="List of 0-based indices of other sub-tasks in *this current plan* that this sub-task depends on. If empty, it only depends on the parent plan completing.")

class PlanOutput(BaseModel):
    """Output schema for a Planner agent, detailing the sub-tasks."""
    sub_tasks: List[SubTask] = Field(..., description="List of planned sub-tasks.")
    # Could add overall_plan_summary or other metadata from the planner
    
    # Optional reasoning steps for reasoning-enabled agents
    reasoning_steps: Optional[List[ReasoningStep]] = Field(default=None, description="Reasoning steps if agent has reasoning enabled")

# --- Atomizer Output Schema ---
class AtomizerOutput(BaseModel):
    """Output schema for Atomizer agents."""
    is_atomic: bool = Field(..., description="True if the refined goal is atomic, False if complex and needs planning.")
    updated_goal: str = Field(..., description="The refined task goal after considering context.")
    # Optionally, the atomizer could also suggest a task_type or agent_name if it changes fundamentally
    # suggested_task_type: Optional[str] = None
    # suggested_agent_name: Optional[str] = None
    
    # Optional reasoning steps for reasoning-enabled agents
    reasoning_steps: Optional[List[ReasoningStep]] = Field(default=None, description="Reasoning steps if agent has reasoning enabled")


# --- Context Structure for Agents ---
class ContextItem(BaseModel):
    """A single piece of structured context provided to an agent."""
    source_task_id: str
    source_task_goal: str # Goal of the task that produced this context
    content: Any # The actual data (text, Pydantic model, multi-modal reference)
    content_type_description: str # e.g., 'outline', 'search_result_summary', 'plan_output'
    # Optional fields for more advanced context handling:
    # relevance_score: Optional[float] = None
    # timestamp_created: Optional[datetime] = None # When the context item was generated
    # modality: Optional[str] = None # For future multi-modal: 'text', 'image', 'audio'

class ParentContextNode(BaseModel):
    """Represents context from a parent node in the hierarchy."""
    task_id: str
    goal: str
    layer: int
    task_type: str
    
    # Key outputs and reasoning from parent
    result_summary: Optional[str] = None
    key_insights: Optional[str] = None
    constraints_identified: Optional[str] = None
    requirements_specified: Optional[str] = None
    
    # Planning context if parent was a PLAN node
    planning_reasoning: Optional[str] = None
    coordination_notes: Optional[str] = None
    
    timestamp_completed: Optional[str] = None

class ParentHierarchyContext(BaseModel):
    """Structured context from parent hierarchy, formatted for LLM consumption."""
    current_position: str = Field(..., description="Description of where this task sits in the hierarchy")
    parent_chain: List[ParentContextNode] = Field(default_factory=list, description="Ordered list from immediate parent to root")
    formatted_context: str = Field(..., description="LLM-friendly formatted text of the parent context")
    priority_level: str = Field(default="medium", description="Priority level: critical, high, medium, low")

# Enhanced AgentTaskInput
class AgentTaskInput(BaseModel):
    """Structured input provided to an agent for processing a task."""
    current_task_id: str
    current_goal: str
    current_task_type: str # String representation of TaskNode.TaskType
    
    overall_project_goal: Optional[str] = None
    relevant_context_items: List[ContextItem] = Field(default_factory=list)
    
    # 🔥 NEW: Parent hierarchy context for downward flow
    parent_hierarchy_context: Optional[ParentHierarchyContext] = None
    
    # Enhanced context formatting
    formatted_full_context: Optional[str] = Field(None, description="Complete formatted context for LLM")
    
    # Configuration or agent-specific parameters can also be passed here
    # agent_config: Optional[Dict[str, Any]] = None

# --- Research Agent I/O Schemas ---
class WebSearchResultsOutput(BaseModel):
    """Output schema for a SearchExecutor agent, detailing the search results."""
    query_used: str = Field(..., description="The exact search query that was executed.")
    # DuckDuckGoTools search_ddg method returns a list of dictionaries like:
    # [{'title': '...', 'href': '...', 'body': '...'}]
    # We'll map 'href' to 'link' and 'body' to 'snippet' for consistency if needed,
    # or adjust this model to expect 'href' and 'body'.
    # For now, let's assume the agent can format it to 'title', 'link', 'snippet'.
    results: List[Dict[str, str]] = Field(..., description="A list of search results, each ideally with 'title', 'link', and 'snippet'.")
    
    # Optional reasoning steps for reasoning-enabled agents
    reasoning_steps: Optional[List[ReasoningStep]] = Field(default=None, description="Reasoning steps if agent has reasoning enabled")

class AnnotationURLCitationModel(BaseModel):
    """Represents a URL citation annotation from the OpenAI web_search_preview tool."""
    title: Optional[str] = Field(None, description="The title of the cited page.")
    url: str = Field(..., description="The URL of the citation.")
    start_index: int = Field(..., description="The start index of the citation in the text.")
    end_index: int = Field(..., description="The end index of the citation in the text.")
    type: str = Field("url_citation", description="The type of annotation, typically 'url_citation'.")
    # text_snippet: Optional[str] = Field(None, description="The text snippet this citation refers to.") # Added for clarity from example
    # The above line might not be needed if start/end_index are sufficient.
    # Your example data did not explicitly have `text_snippet` inside the annotation object itself.

class CustomSearcherOutput(BaseModel):
    """Structured output for the OpenAICustomSearchAdapter."""
    query_used: str = Field(..., description="The original query used for the search.")
    output_text_with_citations: str = Field(..., description="The main textual answer from the OpenAI model, including any inline citations.")
    text_content: Optional[str] = Field(None, description="The textual answer parsed from the nested structure (e.g., response.output[1].content[0].text), if available.")
    annotations: List[AnnotationURLCitationModel] = Field(default_factory=list, description="A list of URL annotations, if available from the nested structure.")
    
    # Optional reasoning steps for reasoning-enabled agents
    reasoning_steps: Optional[List[ReasoningStep]] = Field(default=None, description="Reasoning steps if agent has reasoning enabled")

    def __str__(self) -> str:
        # Prioritize the main output text for string conversion
        return self.output_text_with_citations


class ExecutorOutput(BaseModel):
    """A generic wrapper for any executor agent's output."""
    result: Any = Field(..., description="The direct output from the executor agent (e.g., text, a Pydantic model like WebSearchResultsOutput).")
    replan_request: Optional['ReplanRequestDetails'] = Field(None, description="If the agent determines the plan is flawed, it can request a replan by providing details here.")
    
    # Optional reasoning steps for reasoning-enabled agents
    reasoning_steps: Optional[List[ReasoningStep]] = Field(default=None, description="Reasoning steps if agent has reasoning enabled")


# --- New Planner Input Schemas (for the enhanced PLANNER_SYSTEM_MESSAGE) ---

class ExecutionHistoryItem(BaseModel):
    """Represents a single item in the execution history (sibling or ancestor output)."""
    task_goal: str = Field(..., description="Goal of the historical task.")
    outcome_summary: str = Field(..., description="Brief summary of what the task achieved or produced.")
    full_output_reference_id: Optional[str] = Field(None, description="An ID to fetch the full output if needed.")

class ExecutionHistoryAndContext(BaseModel):
    """Structured execution history and context for the planner."""
    prior_sibling_task_outputs: List[ExecutionHistoryItem] = Field(default_factory=list)
    relevant_ancestor_outputs: List[ExecutionHistoryItem] = Field(default_factory=list)
    global_knowledge_base_summary: Optional[str] = Field(None)

class ReplanRequestDetails(BaseModel):
    """Structured feedback for a re-plan request."""
    failed_sub_goal: str = Field(..., description="The specific sub-goal that previously failed or requires re-planning.")
    reason_for_failure_or_replan: str = Field(..., description="Detailed explanation of why the previous attempt failed or why a re-plan is necessary.")
    previous_attempt_output_summary: Optional[str] = Field(None, description="Summary of what the failed attempt did produce, if anything.")
    specific_guidance_for_replan: Optional[str] = Field(None, description="Concrete suggestions on how to approach the re-plan differently.")

class PlannerInput(BaseModel):
    """Defines the structured input for the enhanced Planner Agent."""
    current_task_goal: str = Field(..., description="The specific goal for this planning instance.")
    overall_objective: str = Field(..., description="The ultimate high-level goal of the entire operation.")
    parent_task_goal: Optional[str] = Field(None, description="The goal of the immediate parent task. Null if root task.")
    planning_depth: Optional[int] = Field(0, description="Current recursion depth (e.g., 0 for initial, 1 for sub-tasks).")
    execution_history_and_context: ExecutionHistoryAndContext = Field(default_factory=ExecutionHistoryAndContext)
    replan_request_details: Optional[ReplanRequestDetails] = Field(None)
    global_constraints_or_preferences: Optional[List[str]] = Field(default_factory=list)
    # Potentially add available_executor_capabilities: List[str] = Field(default_factory=list) in the future

    class Config:
        validate_assignment = True # Ensures that even if you update fields later, they are validated.

class PlanModifierInput(BaseModel):
    """
    Input model for an agent tasked with modifying an existing plan based on user feedback.
    """
    original_plan: PlanOutput = Field(description="The current plan (PlanOutput model) that needs modification.")
    user_modification_instructions: str = Field(description="Textual instructions from the user on how to modify the plan.")
    overall_objective: str = Field(description="The overarching goal that the original and revised plan must achieve.")
    # Optional context that might be useful for the modifier agent
    parent_task_id: Optional[str] = Field(default=None, description="The ID of the parent task for which this plan is being modified.")
    planning_depth: Optional[int] = Field(default=None, description="The current planning depth/layer of the parent task.")
    # You could also include prior modification attempts or other metadata if helpful for the LLM
    # prior_attempts: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="History of prior modification instructions and outcomes for this plan, if any.")

    # If you prefer to send the plan as a JSON string to the LLM for easier prompting:
    # original_plan_json: str = Field(description="The current plan (JSON string representation of PlanOutput) that needs modification.")
    # For now, let's try passing the Pydantic model directly, as Agno might handle its serialization.
    # If the LLM struggles with the full Pydantic model as context, converting to a simpler dict or JSON string
    # in the adapter before sending to the LLM might be necessary.

# You might also consider a specific model for what the user provides if it's more structured
# class UserFeedbackOnPlan(BaseModel):
#     target_task_index: Optional[int] = None # If feedback is about a specific task
#     instruction: str # e.g., "Change goal to X", "Remove this task"
#     new_task_definition: Optional[SubTaskDefinition] = None # If user wants to add/replace a task