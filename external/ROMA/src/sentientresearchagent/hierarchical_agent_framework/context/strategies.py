from abc import ABC, abstractmethod
from typing import List, Optional
import re

from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    ContextItem,
)
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import (
    KnowledgeStore,
    TaskRecord,
)
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskStatus

# Assuming TARGET_WORD_COUNT_FOR_CTX_SUMMARIES is accessible, e.g. from agents.utils
# If not, we might need to pass it or define it here. For now, let's assume it's imported.
from ..agents.utils import (
    TARGET_WORD_COUNT_FOR_CTX_SUMMARIES,
    get_context_summary,
)

def is_generic_summary(summary: str) -> bool:
    """Check if a summary is generic/unhelpful and should be replaced with actual content."""
    if not summary or not summary.strip():
        return True
    
    # Convert to lowercase for pattern matching
    summary_lower = summary.lower().strip()
    
    # Patterns that indicate generic summaries
    generic_patterns = [
        "planned with",
        "execution completed",
        "data type:",
        "structured output:",
        "aggregation completed",
        "processing complete",
        "task completed"
    ]
    
    # Check if summary starts with any generic pattern
    for pattern in generic_patterns:
        if summary_lower.startswith(pattern):
            return True
    
    # Check if summary is too short to be meaningful (less than 20 chars excluding whitespace)
    if len(summary.strip()) < 20:
        return True
    
    return False

# NEW IMPORT for the summarization utility
from ..agents.utils import get_context_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES


# For AncestorBranchContextStrategy, import the helper from context_utils
from .context_utils import get_task_record_path_to_root


class ContextResolutionStrategy(ABC):
    """Abstract base class for context resolution strategies."""

    @abstractmethod
    def get_context(
        self,
        current_task_record: TaskRecord,
        knowledge_store: KnowledgeStore,
        processed_context_source_ids: set[str],
        overall_project_goal: Optional[str] = None,
        current_task_type: Optional[str] = None,
        # Add other parameters as needed by various strategies
    ) -> List[ContextItem]:
        """
        Fetches and returns a list of context items based on the strategy.

        Args:
            current_task_record: The record of the task for which context is being built.
            knowledge_store: The knowledge store to access other task records.
            processed_context_source_ids: A set of task IDs already processed to avoid duplication.
                                           Strategies should add IDs of context they provide to this set.
            overall_project_goal: The overall goal of the project.
            current_task_type: The type of the current task.

        Returns:
            A list of ContextItem objects.
        """
        pass


class ParentContextStrategy(ContextResolutionStrategy):
    """
    Provides context from the direct parent of the current task,
    if the parent's output is relevant (e.g., a plan for a sub-task).
    """

    def get_context(
        self,
        current_task_record: TaskRecord,
        knowledge_store: KnowledgeStore,
        processed_context_source_ids: set[str],
        overall_project_goal: Optional[str] = None,
        current_task_type: Optional[str] = None,
    ) -> List[ContextItem]:
        context_items: List[ContextItem] = []
        if not current_task_record.parent_task_id:
            return context_items

        parent_id = current_task_record.parent_task_id
        if parent_id in processed_context_source_ids:
            logger.debug(
                f"ParentContextStrategy: Parent {parent_id} already processed. Skipping."
            )
            return context_items

        parent_record = knowledge_store.get_record(parent_id)
        if not parent_record:
            logger.warning(
                f"ParentContextStrategy: Parent record {parent_id} not found in KnowledgeStore."
            )
            return context_items

        # Check if parent has output_content or output_summary
        if parent_record.output_content is not None or parent_record.output_summary is not None:
            is_completed_parent = parent_record.status == TaskStatus.DONE.value
            is_plan_done_parent = parent_record.status == TaskStatus.PLAN_DONE.value

            if is_completed_parent or is_plan_done_parent:
                content_desc = parent_record.output_type_description or "parent_output"
                # Prioritize plan/outline if parent was a PLAN or THINK node
                if parent_record.task_type in ["PLAN", "THINK"] and (
                    "plan" in content_desc
                    or "outline" in content_desc
                    or is_plan_done_parent
                ):
                    content_desc = "parental_plan_or_outline"

                summarized_content = parent_record.output_summary
                log_reason = f"used existing output_summary (len: {len(summarized_content or '')})"

                # Check if existing summary is generic/unhelpful using the global function

                # ENHANCED: Prefer original content unless it's too large
                needs_processing = False
                use_original_content = False
                
                # First check if we have original content and how large it is
                if parent_record.output_content is not None:
                    original_word_count = len(str(parent_record.output_content).split())
                    if original_word_count <= TARGET_WORD_COUNT_FOR_CTX_SUMMARIES:
                        # Original content is within our threshold, use it directly
                        summarized_content = str(parent_record.output_content)
                        log_reason = f"used original output_content directly (len: {len(summarized_content)} chars, {original_word_count} words)"
                        use_original_content = True
                    else:
                        # Original content is too large, we need to summarize
                        needs_processing = True
                        log_reason = f"original content too large ({original_word_count} words > {TARGET_WORD_COUNT_FOR_CTX_SUMMARIES}), will summarize"
                
                # If we don't have original content or it's too large, check the summary
                if not use_original_content:
                    if not summarized_content:
                        needs_processing = True
                    elif is_generic_summary(summarized_content):
                        logger.debug(f"  PARENT ({parent_record.task_id}): Existing output_summary is generic, will use output_content instead.")
                        needs_processing = True
                        log_reason = "bypassed generic output_summary in favor of output_content"
                    else:
                        try:
                            # Ensure summarized_content is a string before calling split()
                            summary_word_count = len(str(summarized_content).split())
                            if summary_word_count > TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 1.2:
                                needs_processing = True
                                log_reason = f"existing summary too long ({summary_word_count} words), will re-summarize"
                            else:
                                log_reason = f"used existing output_summary (len: {len(summarized_content or '')} chars, {summary_word_count} words)"
                        except Exception as e:
                            logger.warning(f"ParentContextStrategy: Error processing summary for {parent_record.task_id}: {e}. Will attempt to re-summarize/truncate.")
                            needs_processing = True


                if needs_processing:
                    if parent_record.output_content is not None:
                        logger.debug(
                            f"  PARENT ({parent_record.task_id}): Summarizing output_content. "
                            f"Prev summary len: {len(str(summarized_content or ''))}."
                        )
                        summarized_content = get_context_summary(
                            parent_record.output_content,
                            target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES,
                        )
                        log_reason = (
                            f"summarized output_content (original content len: {len(str(parent_record.output_content))}, "
                            f"new summary len: {len(summarized_content)})"
                        )
                    elif summarized_content:  # Existing summary was too long, and no output_content
                        logger.debug(
                            f"  PARENT ({parent_record.task_id}): Existing output_summary too long, truncating. "
                            f"Len: {len(summarized_content)}."
                        )
                        # Ensure summarized_content is a string before slicing
                        summarized_content = str(summarized_content)[:(TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 7)] # Approx char limit
                        log_reason = f"truncated long existing output_summary (new len: {len(summarized_content)})"
                
                if summarized_content and str(summarized_content).strip():
                    context_items.append(
                        ContextItem(
                            source_task_id=parent_record.task_id,
                            source_task_goal=parent_record.goal,
                            content=str(summarized_content).strip(),
                            content_type_description=content_desc,
                        )
                    )
                    processed_context_source_ids.add(parent_record.task_id)
                    logger.info(
                        f"  ParentContextStrategy: Added context from PARENT: {parent_record.task_id} "
                        f"(Status: {parent_record.status}). How: {log_reason}. Final len: {len(str(summarized_content).strip())}"
                    )
                else:
                    logger.warning(
                        f"  PARENT ({parent_record.task_id}): Summarization resulted in empty content. Not added."
                    )
        return context_items


class PrerequisiteSiblingContextStrategy(ContextResolutionStrategy):
    """
    Provides context from completed direct prerequisite siblings of the current task
    within the same sub-graph (i.e., children of the same parent).
    """

    def get_context(
        self,
        current_task_record: TaskRecord,
        knowledge_store: KnowledgeStore,
        processed_context_source_ids: set[str],
        overall_project_goal: Optional[str] = None,
        current_task_type: Optional[str] = None,
    ) -> List[ContextItem]:
        context_items: List[ContextItem] = []
        if not current_task_record.parent_task_id:
            return context_items

        parent_of_current_task_record = knowledge_store.get_record(
            current_task_record.parent_task_id
        )
        if not (
            parent_of_current_task_record
            and parent_of_current_task_record.child_task_ids_generated
        ):
            return context_items

        try:
            sibling_ids_in_plan = (
                parent_of_current_task_record.child_task_ids_generated
            )
            current_task_index_in_plan = sibling_ids_in_plan.index(
                current_task_record.task_id
            )

            for i in range(current_task_index_in_plan):
                prereq_sibling_id = sibling_ids_in_plan[i]
                if prereq_sibling_id in processed_context_source_ids:
                    logger.debug(f"PrerequisiteSiblingContextStrategy: Sibling {prereq_sibling_id} already processed. Skipping.")
                    continue

                prereq_record = knowledge_store.get_record(prereq_sibling_id)
                if (
                    prereq_record
                    and prereq_record.status == TaskStatus.DONE.value
                    and (
                        prereq_record.output_content is not None
                        or prereq_record.output_summary is not None
                    )
                ):
                    # ENHANCED: Prefer original content unless it's too large
                    needs_processing = False
                    use_original_content = False
                    
                    # First check if we have original content and how large it is
                    if prereq_record.output_content is not None:
                        original_word_count = len(str(prereq_record.output_content).split())
                        if original_word_count <= TARGET_WORD_COUNT_FOR_CTX_SUMMARIES:
                            # Original content is within our threshold, use it directly
                            summarized_content = str(prereq_record.output_content)
                            log_reason = f"used original output_content directly (len: {len(summarized_content)} chars, {original_word_count} words)"
                            use_original_content = True
                        else:
                            # Original content is too large, we need to summarize
                            needs_processing = True
                            log_reason = f"original content too large ({original_word_count} words > {TARGET_WORD_COUNT_FOR_CTX_SUMMARIES}), will summarize"
                    
                    # If we don't have original content or it's too large, check the summary
                    if not use_original_content:
                        summarized_content = prereq_record.output_summary
                        if not summarized_content:
                            needs_processing = True
                        else:
                            try:
                                summary_word_count = len(str(summarized_content).split())
                                if summary_word_count > TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 1.2:
                                    needs_processing = True
                                    log_reason = f"existing summary too long ({summary_word_count} words), will re-summarize"
                                else:
                                    log_reason = f"used existing output_summary (len: {len(summarized_content or '')} chars, {summary_word_count} words)"
                            except Exception as e:
                                logger.warning(f"PrerequisiteSiblingContextStrategy: Error processing summary for {prereq_record.task_id}: {e}. Will attempt to re-summarize/truncate.")
                                needs_processing = True


                    if needs_processing:
                        if prereq_record.output_content is not None:
                            logger.debug(
                                f"  PREREQ SIBLING ({prereq_record.task_id}): Summarizing output_content. "
                                f"Prev summary len: {len(str(summarized_content or ''))}."
                            )
                            summarized_content = get_context_summary(
                                prereq_record.output_content,
                                target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES,
                            )
                            log_reason = (
                                f"summarized output_content (original content len: {len(str(prereq_record.output_content))}, "
                                f"new summary len: {len(summarized_content)})"
                            )
                        elif summarized_content:  # Existing summary was too long
                            logger.debug(
                                f"  PREREQ SIBLING ({prereq_record.task_id}): Existing output_summary too long, truncating. "
                                f"Len: {len(summarized_content)}."
                            )
                            summarized_content = str(summarized_content)[:(TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 7)]
                            log_reason = f"truncated long existing output_summary (new len: {len(summarized_content)})"

                    if summarized_content and str(summarized_content).strip():
                        context_items.append(
                            ContextItem(
                                source_task_id=prereq_record.task_id,
                                source_task_goal=prereq_record.goal,
                                content=str(summarized_content).strip(),
                                content_type_description=prereq_record.output_type_description
                                or "prerequisite_sibling_output",
                            )
                        )
                        processed_context_source_ids.add(prereq_record.task_id)
                        logger.info(
                            f"  PrerequisiteSiblingContextStrategy: Added context from PREREQUISITE SIBLING: {prereq_record.task_id}. "
                            f"How: {log_reason}. Final len: {len(str(summarized_content).strip())}"
                        )
                    else:
                        logger.warning(
                            f"  PREREQ SIBLING ({prereq_record.task_id}): Summarization resulted in empty content. Not added."
                        )
        except ValueError:
            logger.warning(
                f"PrerequisiteSiblingContextStrategy: Task {current_task_record.task_id} not found in parent "
                f"{parent_of_current_task_record.task_id}'s generated children list, or other ValueError."
            )
        except Exception as e:
            logger.error(f"PrerequisiteSiblingContextStrategy: Error processing siblings for task {current_task_record.task_id}: {e}", exc_info=True)

        return context_items


class AncestorBranchContextStrategy(ContextResolutionStrategy):
    """
    Provides "Broad Context" for Writers/Thinkers from completed branches
    of an ancestor plan.
    """

    def get_context(
        self,
        current_task_record: TaskRecord,
        knowledge_store: KnowledgeStore,
        processed_context_source_ids: set[str],
        overall_project_goal: Optional[str] = None,
        current_task_type: Optional[str] = None,
    ) -> List[ContextItem]:
        context_items: List[ContextItem] = []
        if not current_task_type or current_task_type not in ["WRITE", "THINK"]:
            return context_items
        
        path_to_root = get_task_record_path_to_root(
            current_task_record.task_id, knowledge_store
        )
        ancestor_for_broad_context: Optional[TaskRecord] = None

        if len(path_to_root) > 1:  # Parent exists
            ancestor_for_broad_context = path_to_root[-2]
        if len(path_to_root) > 2:  # Grandparent exists
            potential_broader_ancestor = path_to_root[-3]
            if potential_broader_ancestor.task_type == "PLAN":
                ancestor_for_broad_context = potential_broader_ancestor
        
        if not ancestor_for_broad_context or not ancestor_for_broad_context.child_task_ids_generated:
            return context_items

        logger.debug(
            f"  AncestorBranchContextStrategy: Seeking broad context from children of ancestor '{ancestor_for_broad_context.task_id}'"
        )
        for sibling_branch_id in ancestor_for_broad_context.child_task_ids_generated:
            if (
                sibling_branch_id == current_task_record.task_id
                or sibling_branch_id == current_task_record.parent_task_id
            ):
                continue
            if sibling_branch_id in processed_context_source_ids:
                logger.debug(f"AncestorBranchContextStrategy: Ancestor branch {sibling_branch_id} already processed. Skipping.")
                continue

            sibling_branch_record = knowledge_store.get_record(sibling_branch_id)
            if (
                sibling_branch_record
                and sibling_branch_record.status == TaskStatus.DONE.value
                and (
                    sibling_branch_record.output_content is not None
                    or sibling_branch_record.output_summary is not None
                )
            ):
                content_type_desc = (
                    sibling_branch_record.output_type_description
                    or "ancestor_branch_output"
                )
                if sibling_branch_record.task_type == "PLAN" and "aggregate" in (
                    sibling_branch_record.output_type_description or ""
                ).lower():
                    content_type_desc = "aggregated_ancestor_branch_output"

                # ENHANCED: Prefer original content unless it's too large
                needs_processing = False
                use_original_content = False
                
                # First check if we have original content and how large it is
                if sibling_branch_record.output_content is not None:
                    original_word_count = len(str(sibling_branch_record.output_content).split())
                    if original_word_count <= TARGET_WORD_COUNT_FOR_CTX_SUMMARIES:
                        # Original content is within our threshold, use it directly
                        summarized_content = str(sibling_branch_record.output_content)
                        log_reason = f"used original output_content directly (len: {len(summarized_content)} chars, {original_word_count} words)"
                        use_original_content = True
                    else:
                        # Original content is too large, we need to summarize
                        needs_processing = True
                        log_reason = f"original content too large ({original_word_count} words > {TARGET_WORD_COUNT_FOR_CTX_SUMMARIES}), will summarize"
                
                # If we don't have original content or it's too large, check the summary
                if not use_original_content:
                    summarized_content = sibling_branch_record.output_summary
                    if not summarized_content:
                        needs_processing = True
                    else:
                        try:
                            summary_word_count = len(str(summarized_content).split())
                            if summary_word_count > TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 1.2:
                                needs_processing = True
                                log_reason = f"existing summary too long ({summary_word_count} words), will re-summarize"
                            else:
                                log_reason = f"used existing output_summary (len: {len(summarized_content or '')} chars, {summary_word_count} words)"
                        except Exception as e:
                            logger.warning(f"AncestorBranchContextStrategy: Error processing summary for {sibling_branch_record.task_id}: {e}. Will attempt to re-summarize/truncate.")
                            needs_processing = True
                
                if needs_processing:
                    if sibling_branch_record.output_content is not None:
                        logger.debug(
                            f"  ANCESTOR BRANCH ({sibling_branch_record.task_id}): Summarizing output_content. "
                            f"Prev summary len: {len(str(summarized_content or ''))}."
                        )
                        summarized_content = get_context_summary(
                            sibling_branch_record.output_content,
                            target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES,
                        )
                        log_reason = (
                            f"summarized output_content (original content len: {len(str(sibling_branch_record.output_content))}, "
                            f"new summary len: {len(summarized_content)})"
                        )
                    elif summarized_content:  # Existing summary was too long
                        logger.debug(
                            f"  ANCESTOR BRANCH ({sibling_branch_record.task_id}): Existing output_summary too long, truncating. "
                            f"Len: {len(summarized_content)}."
                        )
                        summarized_content = str(summarized_content)[:(TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 7)]
                        log_reason = f"truncated long existing output_summary (new len: {len(summarized_content)})"
                
                if summarized_content and str(summarized_content).strip():
                    context_items.append(
                        ContextItem(
                            source_task_id=sibling_branch_record.task_id,
                            source_task_goal=sibling_branch_record.goal,
                            content=str(summarized_content).strip(),
                            content_type_description=content_type_desc,
                        )
                    )
                    processed_context_source_ids.add(sibling_branch_id)
                    logger.info(
                        f"  AncestorBranchContextStrategy: Added BROAD context from ANCESTOR BRANCH: {sibling_branch_record.task_id}. "
                        f"How: {log_reason}. Final len: {len(str(summarized_content).strip())}"
                    )
                else:
                    logger.warning(
                        f"  ANCESTOR BRANCH ({sibling_branch_record.task_id}): Summarization resulted in empty content. Not added."
                    )
        return context_items


class GoalReferenceContextStrategy(ContextResolutionStrategy):
    """
    Provides context from tasks explicitly mentioned (by ID) in the current task's goal.
    Expected format in goal: `task_id` (e.g., `root.1.2`)
    """

    def get_context(
        self,
        current_task_record: TaskRecord,
        knowledge_store: KnowledgeStore,
        processed_context_source_ids: set[str],
        overall_project_goal: Optional[str] = None,
        current_task_type: Optional[str] = None,
    ) -> List[ContextItem]:
        context_items: List[ContextItem] = []
        # current_goal is on current_task_record.goal
        explicitly_referenced_task_ids = re.findall(
            r"`(root(?:\.\d+)*)`", current_task_record.goal
        )

        if not explicitly_referenced_task_ids:
            return context_items

        unique_referenced_ids = list(dict.fromkeys(explicitly_referenced_task_ids))
        logger.debug(f"  GoalReferenceContextStrategy: Task goal references IDs: {unique_referenced_ids}")

        for ref_task_id in unique_referenced_ids:
            if ref_task_id == current_task_record.task_id or ref_task_id in processed_context_source_ids:
                logger.debug(f"GoalReferenceContextStrategy: Referenced task {ref_task_id} is current or already processed. Skipping.")
                continue

            referenced_record = knowledge_store.get_record(ref_task_id)
            if (
                referenced_record
                and referenced_record.status == TaskStatus.DONE.value
                and (
                    referenced_record.output_content is not None
                    or referenced_record.output_summary is not None
                )
            ):
                # 🔄 ENHANCED: Check original content first, prefer it if under 4k words
                summarized_content = None
                log_reason = ""
                
                # Check if we have original content and it's reasonably sized
                if referenced_record.output_content is not None:
                    original_content_str = str(referenced_record.output_content)
                    original_word_count = len(original_content_str.split())
                    
                    if original_word_count <= TARGET_WORD_COUNT_FOR_CTX_SUMMARIES:
                        # Original content is small enough, use it directly
                        summarized_content = original_content_str
                        log_reason = f"used original output_content directly (words: {original_word_count} <= {TARGET_WORD_COUNT_FOR_CTX_SUMMARIES})"
                        logger.debug(f"  EXPLICIT REF ({referenced_record.task_id}): Using original content directly (words: {original_word_count})")
                    else:
                        # Original content is too large, need to summarize
                        logger.debug(f"  EXPLICIT REF ({referenced_record.task_id}): Original content too large (words: {original_word_count}), will summarize")
                        summarized_content = get_context_summary(
                            referenced_record.output_content,
                            target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES,
                        )
                        log_reason = f"summarized large output_content (original words: {original_word_count}, summary len: {len(summarized_content)})"
                
                # If we don't have original content or summarization failed, fall back to existing summary
                if not summarized_content and referenced_record.output_summary is not None:
                    existing_summary = str(referenced_record.output_summary)
                    
                    # Check if existing summary is generic and should be replaced
                    if is_generic_summary(existing_summary):
                        logger.debug(f"  EXPLICIT REF ({referenced_record.task_id}): Existing summary is generic, skipping")
                        log_reason = "skipped generic existing summary"
                    else:
                        summary_word_count = len(existing_summary.split())
                        if summary_word_count <= TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 1.2:
                            summarized_content = existing_summary
                            log_reason = f"used existing output_summary (words: {summary_word_count})"
                        else:
                            # Existing summary is too long, truncate it
                            summarized_content = existing_summary[:(TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 7)]
                            log_reason = f"truncated long existing output_summary (new len: {len(summarized_content)})"
                
                if summarized_content and str(summarized_content).strip():
                    context_items.append(
                        ContextItem(
                            source_task_id=referenced_record.task_id,
                            source_task_goal=referenced_record.goal,
                            content=str(summarized_content).strip(),
                            content_type_description=referenced_record.output_type_description
                            or "explicit_goal_reference",
                        )
                    )
                    processed_context_source_ids.add(ref_task_id)
                    logger.info(
                        f"  GoalReferenceContextStrategy: Added context from EXPLICITLY REFERENCED task: {ref_task_id}. "
                        f"How: {log_reason}. Final len: {len(str(summarized_content).strip())}"
                    )
                else:
                    logger.warning(
                        f"  EXPLICIT REF ({referenced_record.task_id}): Summarization resulted in empty content. Not added."
                    )
            elif referenced_record:
                logger.warning(
                    f"    GoalReferenceContextStrategy: Referenced task {ref_task_id} not {TaskStatus.DONE.value} or no output/summary. Status: {referenced_record.status}"
                )
            else:
                logger.warning(
                    f"    GoalReferenceContextStrategy: Referenced task {ref_task_id} not found in KnowledgeStore."
                )
        return context_items


class DependencyContextStrategy(ContextResolutionStrategy):
    """
    Provides context from tasks that the current task explicitly depends on.
    This looks at the task graph dependencies (depends_on_indices) to find
    prerequisite tasks that must be completed before the current task can execute.
    """

    def get_context(
        self,
        current_task_record: TaskRecord,
        knowledge_store: KnowledgeStore,
        processed_context_source_ids: set[str],
        overall_project_goal: Optional[str] = None,
        current_task_type: Optional[str] = None,
    ) -> List[ContextItem]:
        context_items: List[ContextItem] = []
        
        # Get the current task's dependency information
        # Note: depends_on_indices might be stored in aux_data or another field
        depends_on_indices = getattr(current_task_record, 'depends_on_indices', None)
        if not depends_on_indices:
            # Try to get it from aux_data if it's stored there
            aux_data = getattr(current_task_record, 'aux_data', {})
            depends_on_indices = aux_data.get('depends_on_indices', [])
        
        # ENHANCED DEBUG: Log detailed dependency information
        logger.info(f"🔗 DependencyContextStrategy: Checking dependencies for task {current_task_record.task_id}")
        logger.info(f"🔗 DependencyContextStrategy: current_task_record.depends_on_indices = {getattr(current_task_record, 'depends_on_indices', 'NOT_FOUND')}")
        logger.info(f"🔗 DependencyContextStrategy: current_task_record.aux_data = {getattr(current_task_record, 'aux_data', 'NOT_FOUND')}")
        logger.info(f"🔗 DependencyContextStrategy: resolved depends_on_indices = {depends_on_indices}")
        
        if not depends_on_indices:
            logger.info(f"🔗 DependencyContextStrategy: No explicit dependencies found for task {current_task_record.task_id}")
            return context_items
        
        logger.info(f"🔗 DependencyContextStrategy: Found {len(depends_on_indices)} dependencies for task {current_task_record.task_id}: {depends_on_indices}")
        
        for dependency_index in depends_on_indices:
            # Convert dependency index to task ID
            # This assumes the dependency is referenced by index in the same parent's child list
            if not current_task_record.parent_task_id:
                logger.warning(f"DependencyContextStrategy: Cannot resolve dependency {dependency_index} - no parent task")
                continue
                
            parent_record = knowledge_store.get_record(current_task_record.parent_task_id)
            if not parent_record or not parent_record.child_task_ids_generated:
                logger.warning(f"DependencyContextStrategy: Cannot resolve dependency {dependency_index} - parent has no children")
                continue
            
            # Get the dependency task ID from the parent's child list
            try:
                if dependency_index < len(parent_record.child_task_ids_generated):
                    dependency_task_id = parent_record.child_task_ids_generated[dependency_index]
                else:
                    logger.warning(f"DependencyContextStrategy: Dependency index {dependency_index} out of range for parent {current_task_record.parent_task_id}")
                    continue
            except (TypeError, IndexError) as e:
                logger.warning(f"DependencyContextStrategy: Error resolving dependency index {dependency_index}: {e}")
                continue
            
            # Skip if already processed
            if dependency_task_id in processed_context_source_ids:
                logger.debug(f"DependencyContextStrategy: Dependency {dependency_task_id} already processed. Skipping.")
                continue
            
            # Get the dependency task record
            dependency_record = knowledge_store.get_record(dependency_task_id)
            if not dependency_record:
                logger.warning(f"DependencyContextStrategy: Dependency task {dependency_task_id} not found in KnowledgeStore.")
                continue
            
            # Check if dependency is completed
            if dependency_record.status != TaskStatus.DONE.value:
                logger.warning(f"DependencyContextStrategy: Dependency task {dependency_task_id} not completed (status: {dependency_record.status})")
                continue
            
            # Check if dependency has output
            if not (dependency_record.output_content or dependency_record.output_summary):
                logger.warning(f"DependencyContextStrategy: Dependency task {dependency_task_id} has no output content")
                continue
            
            # Process the dependency content
            summarized_content = dependency_record.output_summary
            log_reason = f"used existing output_summary (len: {len(summarized_content or '')})"
            
            # Check if existing summary is generic/unhelpful using the global function
            
            # ENHANCED: Prefer original content unless it's too large
            needs_processing = False
            use_original_content = False
            
            # First check if we have original content and how large it is
            if dependency_record.output_content is not None:
                original_word_count = len(str(dependency_record.output_content).split())
                if original_word_count <= TARGET_WORD_COUNT_FOR_CTX_SUMMARIES:
                    # Original content is within our threshold, use it directly
                    summarized_content = str(dependency_record.output_content)
                    log_reason = f"used original output_content directly (len: {len(summarized_content)} chars, {original_word_count} words)"
                    use_original_content = True
                else:
                    # Original content is too large, we need to summarize
                    needs_processing = True
                    log_reason = f"original content too large ({original_word_count} words > {TARGET_WORD_COUNT_FOR_CTX_SUMMARIES}), will summarize"
            
            # If we don't have original content or it's too large, check the summary
            if not use_original_content:
                if not summarized_content:
                    needs_processing = True
                elif is_generic_summary(summarized_content):
                    logger.info(f"🔗 DEPENDENCY ({dependency_record.task_id}): Existing output_summary is generic ('{summarized_content[:50]}...'), will use output_content instead.")
                    needs_processing = True
                    log_reason = "bypassed generic output_summary in favor of output_content"
                else:
                    try:
                        summary_word_count = len(str(summarized_content).split())
                        if summary_word_count > TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 1.2:
                            needs_processing = True
                            log_reason = f"existing summary too long ({summary_word_count} words), will re-summarize"
                        else:
                            log_reason = f"used existing output_summary (len: {len(summarized_content or '')} chars, {summary_word_count} words)"
                    except Exception as e:
                        logger.warning(f"DependencyContextStrategy: Error processing summary for {dependency_record.task_id}: {e}. Will attempt to re-summarize/truncate.")
                        needs_processing = True
            
            if needs_processing:
                if dependency_record.output_content is not None:
                    logger.debug(f"  DEPENDENCY ({dependency_record.task_id}): Summarizing output_content. Prev summary len: {len(str(summarized_content or ''))}.")
                    summarized_content = get_context_summary(
                        dependency_record.output_content,
                        target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES,
                    )
                    log_reason = f"summarized output_content (original content len: {len(str(dependency_record.output_content))}, new summary len: {len(summarized_content)})"
                elif summarized_content:  # Existing summary was too long
                    logger.debug(f"  DEPENDENCY ({dependency_record.task_id}): Existing output_summary too long, truncating. Len: {len(summarized_content)}.")
                    summarized_content = str(summarized_content)[:(TARGET_WORD_COUNT_FOR_CTX_SUMMARIES * 7)]
                    log_reason = f"truncated long existing output_summary (new len: {len(summarized_content)})"
            
            if summarized_content and str(summarized_content).strip():
                context_items.append(
                    ContextItem(
                        source_task_id=dependency_record.task_id,
                        source_task_goal=dependency_record.goal,
                        content=str(summarized_content).strip(),
                        content_type_description=dependency_record.output_type_description or "explicit_dependency_output",
                    )
                )
                processed_context_source_ids.add(dependency_task_id)
                logger.info(f"🔗 DependencyContextStrategy: Added context from EXPLICIT DEPENDENCY: {dependency_record.task_id}. How: {log_reason}. Final len: {len(str(summarized_content).strip())}")
            else:
                logger.warning(f"🔗 DEPENDENCY ({dependency_record.task_id}): Summarization resulted in empty content. Not added.")
        
        return context_items
