from typing import List, Optional
from loguru import logger

from .agent_io_models import PlannerInput, ExecutionHistoryItem, ExecutionHistoryAndContext, ReplanRequestDetails
from .knowledge_store import KnowledgeStore, TaskRecord
from ..node.task_node import TaskStatus
from ..agents.utils import get_context_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES
from .context_utils import get_task_record_path_to_root


def _get_parent_context_for_planner(
    parent_task_record: TaskRecord,
    knowledge_store: KnowledgeStore, # knowledge_store might not be needed if parent_task_record has all info
) -> Optional[ExecutionHistoryItem]:
    """
    Extracts and summarizes the parent task's output for planner input.
    Returns None if no suitable context can be derived.
    """
    if parent_task_record.status in [TaskStatus.DONE.value, TaskStatus.PLAN_DONE.value]:
        parent_summary = parent_task_record.output_summary
        log_reason = "used existing output_summary"

        # Summarization/truncation logic (similar to strategies)
        needs_processing = False
        if not parent_summary:
            needs_processing = True
        else:
            try:
                summary_word_count = len(str(parent_summary).split())
                if summary_word_count > TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 1.2:
                    needs_processing = True
            except Exception as e: # Broad exception to catch any issue with split()
                logger.warning(f"_get_parent_context_for_planner: Error processing summary for {parent_task_record.task_id}: {e}. Will attempt to re-summarize/truncate.")
                needs_processing = True
        
        if needs_processing:
            if parent_task_record.output_content is not None:
                parent_summary = get_context_summary(
                    parent_task_record.output_content,
                    target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES
                )
                log_reason = (
                    f"summarized output_content (original content len: {len(str(parent_task_record.output_content))}, "
                    f"summary len: {len(str(parent_summary))})"
                )
            elif parent_summary:  # Existing summary was too long, and no output_content
                parent_summary = str(parent_summary)[:(TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 7)] # Approx char limit based on word count
                log_reason = f"truncated long existing output_summary (summary len: {len(str(parent_summary))})"

        if parent_summary and str(parent_summary).strip():
            logger.info(
                f"  PLANNER_INPUT: Preparing PARENT context from: {parent_task_record.task_id} "
                f"(Status: {parent_task_record.status}). How: {log_reason}"
            )
            return ExecutionHistoryItem(
                task_goal=parent_task_record.goal,
                outcome_summary=str(parent_summary).strip(),
                full_output_reference_id=parent_task_record.task_id
            )
        else:
            logger.warning(
                f"  PLANNER_INPUT (Parent {parent_task_record.task_id}): "
                "Summarization resulted in empty content. Not adding to relevant_ancestor_outputs."
            )
    return None


def _get_prior_sibling_context_for_planner(
    current_task_id: str,
    parent_task_record: Optional[TaskRecord], # Parent of the current task
    knowledge_store: KnowledgeStore,
    replan_details: Optional[ReplanRequestDetails] = None,
    previous_attempt_successful_outputs: Optional[List[ExecutionHistoryItem]] = None
) -> List[ExecutionHistoryItem]:
    """
    Gathers outputs from prior sibling tasks for planner input.
    Prioritizes `previous_attempt_successful_outputs` if available (for re-planning).
    """
    prior_sibling_task_outputs: List[ExecutionHistoryItem] = []

    if replan_details and previous_attempt_successful_outputs is not None:
        logger.info(
            f"  PLANNER_INPUT (Re-plan): Using {len(previous_attempt_successful_outputs)} "
            "successful outputs from previous attempt as prior_sibling_task_outputs."
        )
        return previous_attempt_successful_outputs # Return directly as these are already formatted

    if not parent_task_record or not parent_task_record.child_task_ids_generated:
        return prior_sibling_task_outputs

    try:
        sibling_ids_in_plan = parent_task_record.child_task_ids_generated
        current_task_index_in_plan = sibling_ids_in_plan.index(current_task_id)

        for i in range(current_task_index_in_plan):
            prereq_sibling_id = sibling_ids_in_plan[i]
            prereq_record = knowledge_store.get_record(prereq_sibling_id)

            if prereq_record and prereq_record.status == TaskStatus.DONE.value:
                summary = prereq_record.output_summary
                log_reason_sib = "used existing output_summary"

                needs_processing = False
                if not summary:
                    needs_processing = True
                else:
                    try:
                        summary_word_count = len(str(summary).split())
                        if summary_word_count > TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 1.2:
                            needs_processing = True
                    except Exception as e:
                        logger.warning(f"_get_prior_sibling_context_for_planner: Error processing summary for {prereq_record.task_id}: {e}. Will attempt to re-summarize/truncate.")
                        needs_processing = True

                if needs_processing:
                    if prereq_record.output_content is not None:
                        summary = get_context_summary(
                            prereq_record.output_content,
                            target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES
                        )
                        log_reason_sib = (
                            f"summarized output_content (original content len: {len(str(prereq_record.output_content))}, "
                            f"summary len: {len(str(summary))})"
                        )
                    elif summary:  # Existing summary was too long
                        summary = str(summary)[:(TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 7)]
                        log_reason_sib = f"truncated long existing output_summary (summary len: {len(str(summary))})"
                
                if summary and str(summary).strip():
                    prior_sibling_task_outputs.append(ExecutionHistoryItem(
                        task_goal=prereq_record.goal,
                        outcome_summary=str(summary).strip(),
                        full_output_reference_id=prereq_record.task_id
                    ))
                    logger.info(
                        f"  PLANNER_INPUT: Added SIBLING context from: {prereq_record.task_id}. How: {log_reason_sib}"
                    )
                else:
                    logger.warning(
                        f"  PLANNER_INPUT (Sibling {prereq_record.task_id}): Summarization resulted in empty content. "
                        "Not added to prior_sibling_task_outputs_for_context."
                    )
    except ValueError:
        logger.debug(
            f"  PLANNER_INPUT: Task {current_task_id} not found in parent "
            f"{parent_task_record.task_id if parent_task_record else 'None'}\'s generated children list, or other ValueError. No prior sibling context by this path."
        )
    except Exception as e:
        logger.error(f"_get_prior_sibling_context_for_planner: Error processing siblings for task {current_task_id}: {e}", exc_info=True)
        
    return prior_sibling_task_outputs


def resolve_input_for_planner_agent(
    current_task_id: str, 
    knowledge_store: KnowledgeStore,
    overall_objective: str, 
    planning_depth: int = 0, 
    replan_details: Optional[ReplanRequestDetails] = None,
    global_constraints: Optional[List[str]] = None,
    previous_attempt_successful_outputs: Optional[List[ExecutionHistoryItem]] = None
) -> PlannerInput:
    logger.info(f"PlannerContextBuilder: Resolving INPUT for PLANNER for task \'{current_task_id}\'")

    current_task_record = knowledge_store.get_record(current_task_id)
    if not current_task_record:
        logger.error(f"PlannerContextBuilder CRITICAL: TaskRecord for current planning task {current_task_id} not found.")
        # Consider raising an exception or returning a more explicit error response
        return PlannerInput(
            current_task_goal="Error: Original task goal not found", # Should be current_task_record.goal if found
            overall_objective=overall_objective,
            parent_task_goal=None,
            planning_depth=planning_depth,
            execution_history_and_context=ExecutionHistoryAndContext(), 
            replan_request_details=replan_details,
            global_constraints_or_preferences=global_constraints or []
        )

    current_task_goal = current_task_record.goal
    parent_task_goal_str: Optional[str] = None
    relevant_ancestor_outputs: List[ExecutionHistoryItem] = []
    
    path_to_root = get_task_record_path_to_root(current_task_id, knowledge_store)
    parent_task_record_for_planner: Optional[TaskRecord] = None
    if len(path_to_root) > 1:
        parent_task_record_for_planner = path_to_root[-2] 
        parent_task_goal_str = parent_task_record_for_planner.goal
        
        parent_context_item = _get_parent_context_for_planner(
            parent_task_record=parent_task_record_for_planner,
            knowledge_store=knowledge_store # Pass KS if helper needs it
        )
        if parent_context_item:
            relevant_ancestor_outputs.append(parent_context_item)

    prior_sibling_task_outputs_for_context = _get_prior_sibling_context_for_planner(
        current_task_id=current_task_id,
        parent_task_record=parent_task_record_for_planner, # This is the parent of current_task_id
        knowledge_store=knowledge_store,
        replan_details=replan_details,
        previous_attempt_successful_outputs=previous_attempt_successful_outputs
    )
    
    global_knowledge_summary: Optional[str] = None # Placeholder for future use

    exec_history_context = ExecutionHistoryAndContext(
        prior_sibling_task_outputs=prior_sibling_task_outputs_for_context,
        relevant_ancestor_outputs=relevant_ancestor_outputs,
        global_knowledge_base_summary=global_knowledge_summary
    )

    planner_input = PlannerInput(
        current_task_goal=current_task_goal,
        overall_objective=overall_objective,
        parent_task_goal=parent_task_goal_str,
        planning_depth=planning_depth,
        execution_history_and_context=exec_history_context,
        replan_request_details=replan_details,
        global_constraints_or_preferences=global_constraints or []
    )
    
    logger.success(
        f"PlannerContextBuilder: Successfully resolved PlannerInput for task \'{current_task_id}\'. "
        f"Replan: {'Yes' if replan_details else 'No'}. "
        f"Prior Siblings: {len(prior_sibling_task_outputs_for_context)}. "
        f"Ancestor Outputs: {len(relevant_ancestor_outputs)}."
    )

    return planner_input
