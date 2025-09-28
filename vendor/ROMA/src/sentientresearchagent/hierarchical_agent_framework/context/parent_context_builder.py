from typing import List, Optional
from loguru import logger
from .agent_io_models import ParentHierarchyContext, ParentContextNode
from .knowledge_store import KnowledgeStore, TaskRecord
from .context_utils import get_task_record_path_to_root

class ParentContextBuilder:
    """Builds structured parent context for downward flow to child nodes."""
    
    def __init__(self, knowledge_store: KnowledgeStore):
        self.knowledge_store = knowledge_store
    
    def build_parent_context(self, current_task_id: str, overall_project_goal: str) -> Optional[ParentHierarchyContext]:
        """
        Build structured parent context for a task.
        
        Args:
            current_task_id: The task requesting context
            overall_project_goal: The project's main goal
        
        Returns:
            ParentHierarchyContext with formatted parent information
        """
        try:
            # Get path from current task to root
            path_to_root = get_task_record_path_to_root(current_task_id, self.knowledge_store)
            
            # 🔥 FIX: The function returns root-to-current, but we need current-to-root
            # So we need to reverse it, then get parents
            path_from_current = path_to_root[::-1]  # Now: [current, parent, grandparent, ...]
            
            if len(path_from_current) <= 1:  # No parents (root task)
                return None
            
            # Current task is first, parents follow
            current_task = path_from_current[0]
            parent_records = path_from_current[1:]  # Immediate parent to root
            
            # Build parent context nodes with prioritization
            parent_nodes = []
            for i, parent_record in enumerate(parent_records):
                priority = self._determine_priority(i, len(parent_records), parent_record)
                
                parent_node = ParentContextNode(
                    task_id=parent_record.task_id,
                    goal=parent_record.goal,
                    layer=parent_record.layer or 0,
                    task_type=parent_record.task_type,
                    result_summary=None,  # Don't pass parent outputs to children
                    key_insights=None,  # Don't extract insights from parent outputs
                    constraints_identified=None,  # Don't extract constraints from parent outputs
                    requirements_specified=None,  # Don't extract requirements from parent outputs
                    planning_reasoning=None,  # Don't pass planning reasoning
                    coordination_notes=None,  # Don't pass coordination notes
                    timestamp_completed=parent_record.timestamp_completed.isoformat() if parent_record.timestamp_completed else None
                )
                parent_nodes.append(parent_node)
            
            # Format for LLM consumption with clean format
            formatted_context = self._format_context_for_llm(
                current_task=current_task,
                parent_nodes=parent_nodes,
                overall_project_goal=overall_project_goal
            )
            
            # Determine overall priority
            overall_priority = self._determine_overall_priority(parent_nodes)
            
            # Create position description
            position_desc = self._create_position_description(current_task, parent_nodes)
            
            return ParentHierarchyContext(
                current_position=position_desc,
                parent_chain=parent_nodes,
                formatted_context=formatted_context,
                priority_level=overall_priority
            )
            
        except Exception as e:
            logger.error(f"ParentContextBuilder: Error building context for {current_task_id}: {e}")
            return None
    
    def _determine_priority(self, index: int, total_parents: int, parent_record: TaskRecord) -> str:
        """Determine priority based on position in hierarchy and content."""
        if index == 0:  # Immediate parent
            return "critical"
        elif index == 1 and total_parents > 2:  # Grandparent if exists
            return "high"
        elif parent_record.task_type in ["PLAN", "THINK"]:  # Strategic nodes
            return "high"
        else:
            return "medium"
    
    def _extract_key_insights(self, parent_record: TaskRecord) -> Optional[str]:
        """Extract key insights from parent's output."""
        if not parent_record.output_content:
            return None
        
        # Look for insights, analysis, or conclusions in the output
        output_str = str(parent_record.output_content)
        
        # Simple heuristics - could be enhanced with LLM extraction
        insight_keywords = ["insight", "analysis", "conclusion", "finding", "discovered", "learned"]
        
        lines = output_str.split('\n')
        insights = []
        
        for line in lines:
            if any(keyword in line.lower() for keyword in insight_keywords):
                insights.append(line.strip())
        
        return "; ".join(insights[:3]) if insights else None  # Top 3 insights
    
    def _extract_constraints(self, parent_record: TaskRecord) -> Optional[str]:
        """Extract constraints or limitations identified by parent."""
        if not parent_record.output_content:
            return None
        
        output_str = str(parent_record.output_content)
        constraint_keywords = ["constraint", "limitation", "requirement", "must", "cannot", "should not"]
        
        lines = output_str.split('\n')
        constraints = []
        
        for line in lines:
            if any(keyword in line.lower() for keyword in constraint_keywords):
                constraints.append(line.strip())
        
        return "; ".join(constraints[:3]) if constraints else None
    
    def _extract_requirements(self, parent_record: TaskRecord) -> Optional[str]:
        """Extract specific requirements from parent."""
        if not parent_record.output_content:
            return None
        
        output_str = str(parent_record.output_content)
        requirement_keywords = ["require", "need", "necessary", "essential", "critical", "important"]
        
        lines = output_str.split('\n')
        requirements = []
        
        for line in lines:
            if any(keyword in line.lower() for keyword in requirement_keywords):
                requirements.append(line.strip())
        
        return "; ".join(requirements[:3]) if requirements else None
    
    def _extract_planning_reasoning(self, parent_record: TaskRecord) -> Optional[str]:
        """Extract planning reasoning if parent was a PLAN node."""
        if parent_record.task_type != "PLAN" or not parent_record.output_content:
            return None
        
        # If output_content is a PlanOutput, extract reasoning
        try:
            if hasattr(parent_record.output_content, 'sub_tasks'):
                return f"Planned {len(parent_record.output_content.sub_tasks)} sub-tasks"
            else:
                # Look for planning keywords in text output
                output_str = str(parent_record.output_content)
                planning_keywords = ["strategy", "approach", "plan", "breakdown", "steps"]
                
                lines = output_str.split('\n')
                reasoning = []
                
                for line in lines:
                    if any(keyword in line.lower() for keyword in planning_keywords):
                        reasoning.append(line.strip())
                
                return "; ".join(reasoning[:2]) if reasoning else None
        except Exception:
            return None
    
    def _extract_coordination_notes(self, parent_record: TaskRecord) -> Optional[str]:
        """Extract coordination or dependency notes."""
        if not parent_record.output_content:
            return None
        
        output_str = str(parent_record.output_content)
        coord_keywords = ["coordinate", "dependency", "depends", "sequence", "order", "synchronize"]
        
        lines = output_str.split('\n')
        coordination = []
        
        for line in lines:
            if any(keyword in line.lower() for keyword in coord_keywords):
                coordination.append(line.strip())
        
        return "; ".join(coordination[:2]) if coordination else None
    
    def _format_context_for_llm(self, current_task: TaskRecord, parent_nodes: List[ParentContextNode], overall_project_goal: str) -> str:
        """Format the parent context in a clean, LLM-friendly way."""
        
        if not parent_nodes:
            return f"Project Goal: {overall_project_goal}\n\nThis is the root task with no parent context."
        
        context_lines = [f"Project Goal: {overall_project_goal}"]
        
        # Add parent context in a clean, hierarchical way
        context_lines.append("\nParent Task Context:")
        
        for i, parent in enumerate(parent_nodes):
            level_name = "Immediate Parent" if i == 0 else f"Ancestor Level {i+1}"
            
            # Basic info
            parent_info = [f"  {level_name}: {parent.goal}"]
            
            # Add result/outcome if available and meaningful
            if parent.result_summary and parent.result_summary.strip() and parent.result_summary not in ["N/A", "None", ""]:
                # Clean up common non-informative summaries
                if not parent.result_summary.startswith("Planned") or "sub-task" not in parent.result_summary:
                    parent_info.append(f"    Outcome: {parent.result_summary}")
            
            # Add key insights if available
            if parent.key_insights:
                parent_info.append(f"    Key Insights: {parent.key_insights}")
            
            # Add constraints if available
            if parent.constraints_identified:
                parent_info.append(f"    Constraints: {parent.constraints_identified}")
            
            # Add requirements if available
            if parent.requirements_specified:
                parent_info.append(f"    Requirements: {parent.requirements_specified}")
            
            # Add planning reasoning if it's meaningful
            if parent.planning_reasoning and not parent.planning_reasoning.startswith("Planned 0"):
                parent_info.append(f"    Planning Approach: {parent.planning_reasoning}")
            
            context_lines.extend(parent_info)
            
            # Only show first 2-3 levels to avoid overwhelming context
            if i >= 2:
                if len(parent_nodes) > 3:
                    context_lines.append(f"  ... and {len(parent_nodes) - 3} more ancestor levels")
                break
        
        # Add simple, actionable guidance
        if len(parent_nodes) > 0:
            context_lines.append(f"\nNote: Your task should contribute to achieving the immediate parent goal.")
        
        return "\n".join(context_lines)
    
    def _determine_overall_priority(self, parent_nodes: List[ParentContextNode]) -> str:
        """Determine overall priority level for the context."""
        if not parent_nodes:
            return "low"
        
        # Immediate parent always makes it at least medium priority
        if len(parent_nodes) == 1:
            return "medium"
        elif len(parent_nodes) >= 2 and any(p.task_type == "PLAN" for p in parent_nodes[:2]):
            return "high"
        # Removed check for constraints/requirements since we're not passing them anymore
        else:
            return "medium"
    
    def _create_position_description(self, current_task: TaskRecord, parent_nodes: List[ParentContextNode]) -> str:
        """Create a description of the current task's position in hierarchy."""
        if not parent_nodes:
            return f"Root task: {current_task.goal}"
        
        depth = len(parent_nodes)
        immediate_parent = parent_nodes[0]
        
        return f"Layer {current_task.layer or 0} task under '{immediate_parent.goal}' (depth: {depth})" 