from typing import List, Optional
from loguru import logger

# Assuming KnowledgeStore and TaskRecord are accessible.
# These would typically be imported from their original locations.
# For this standalone util, we might need to adjust imports based on final structure,
# or ensure this util is always used in a context where these are available.
from .knowledge_store import KnowledgeStore, TaskRecord


def get_task_record_path_to_root(task_id: str, knowledge_store: KnowledgeStore) -> List[TaskRecord]:
    """Helper to get the path of task records from a task_id up to the root."""
    path: List[TaskRecord] = []
    current_id: Optional[str] = task_id
    max_depth = 20 # Safety break for deep hierarchies or loops
    count = 0
    while current_id and count < max_depth:
        record = knowledge_store.get_record(current_id)
        if record:
            path.append(record)
            current_id = record.parent_task_id
        else:
            # If a record is not found, stop traversing.
            # This might happen if parent_task_id is None or points to a non-existent ID.
            logger.debug(f"get_task_record_path_to_root: Record not found for ID '{current_id}'. Path terminated.")
            break
        count +=1
    if count >= max_depth:
        logger.warning(f"get_task_record_path_to_root: Max depth ({max_depth}) reached finding path to root for task '{task_id}'. Path may be incomplete.")
    return path[::-1] # Return from root to task
