"""
Unified Context Formatting Service

Provides consistent formatting for context across all components:
- Inter-dependent nodes (execution context)
- Aggregator context (child results)
- Planning context
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import ContextItem


class ContextFormat(Enum):
    """Different context formatting styles."""
    EXECUTION = "execution"       # For inter-dependent nodes
    AGGREGATION = "aggregation"   # For aggregator nodes
    PLANNING = "planning"         # For planning nodes
    MINIMAL = "minimal"          # Minimal format


@dataclass
class FormattedContext:
    """Structured formatted context."""
    header: Optional[str] = None
    sections: List[Dict[str, str]] = None
    footer: Optional[str] = None
    raw_text: str = ""
    

class ContextFormatter:
    """
    Unified context formatter for consistent presentation across components.
    
    Format Structure:
    1. For Execution (Inter-dependent nodes):
       ```
       === Task Dependencies ===
       
       Task ID: root.1
       Goal: [specific goal]
       Output:
       [full output content]
       
       Task ID: root.2
       Goal: [specific goal]  
       Output:
       [full output content]
       ```
    
    2. For Aggregation (Child results):
       ```
       === Child Task Results ===
       
       Task ID: root.1.1
       Goal: [specific goal]
       Status: DONE
       Output:
       [full output content]
       
       Task ID: root.1.2
       Goal: [specific goal]
       Status: DONE
       Output:
       [full output content]
       ```
    
    3. For Planning:
       ```
       === Planning Context ===
       
       Overall Objective: [objective]
       Current Task: [task]
       
       Related Context:
       - [context item 1]
       - [context item 2]
       ```
    """
    
    @staticmethod
    def format_context(
        context_items: List[ContextItem],
        format_type: ContextFormat = ContextFormat.EXECUTION,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format context items according to the specified format type.
        
        Args:
            context_items: List of context items to format
            format_type: Type of formatting to apply
            additional_info: Additional information for formatting
            
        Returns:
            Formatted context string
        """
        if not context_items:
            return ""
        
        if format_type == ContextFormat.EXECUTION:
            return ContextFormatter._format_execution_context(context_items)
        elif format_type == ContextFormat.AGGREGATION:
            return ContextFormatter._format_aggregation_context(context_items, additional_info)
        elif format_type == ContextFormat.PLANNING:
            return ContextFormatter._format_planning_context(context_items, additional_info)
        else:
            return ContextFormatter._format_minimal_context(context_items)
    
    @staticmethod
    def _format_execution_context(context_items: List[ContextItem]) -> str:
        """Format context for inter-dependent node execution."""
        sections = []
        
        # Group by dependency vs other context
        dependency_items = [item for item in context_items if item.content_type_description == "dependency_result"]
        other_items = [item for item in context_items if item.content_type_description != "dependency_result"]
        
        if dependency_items:
            sections.append("=== Task Dependencies ===")
            sections.append("")
            
            for item in dependency_items:
                sections.append(f"Task ID: {item.source_task_id}")
                sections.append(f"Goal: {item.source_task_goal}")
                sections.append("Output:")
                sections.append(ContextFormatter._extract_output(item.content))
                sections.append("")  # Blank line between items
        
        if other_items:
            if dependency_items:
                sections.append("=== Additional Context ===")
                sections.append("")
            
            for item in other_items:
                sections.append(f"Source: {item.source_task_goal}")
                sections.append("Content:")
                sections.append(ContextFormatter._extract_output(item.content))
                sections.append("")
        
        return "\n".join(sections).strip()
    
    @staticmethod
    def _format_aggregation_context(
        context_items: List[ContextItem], 
        additional_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format context for aggregation nodes."""
        sections = []
        
        sections.append("=== Child Task Results ===")
        sections.append("")
        
        for item in context_items:
            sections.append(f"Task ID: {item.source_task_id}")
            sections.append(f"Goal: {item.source_task_goal}")
            
            # Add status if available
            if additional_info and item.source_task_id in additional_info.get('statuses', {}):
                status = additional_info['statuses'][item.source_task_id]
                sections.append(f"Status: {status}")
            
            sections.append("Output:")
            sections.append(ContextFormatter._extract_output(item.content))
            sections.append("")  # Blank line between items
        
        return "\n".join(sections).strip()
    
    @staticmethod
    def _format_planning_context(
        context_items: List[ContextItem],
        additional_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format context for planning nodes."""
        sections = []
        
        sections.append("=== Planning Context ===")
        sections.append("")
        
        if additional_info:
            if 'overall_objective' in additional_info:
                sections.append(f"Overall Objective: {additional_info['overall_objective']}")
            if 'current_task' in additional_info:
                sections.append(f"Current Task: {additional_info['current_task']}")
            sections.append("")
        
        if context_items:
            sections.append("Related Context:")
            for item in context_items:
                sections.append(f"- From {item.source_task_id}: {item.source_task_goal}")
                content_preview = str(item.content)[:100] + "..." if len(str(item.content)) > 100 else str(item.content)
                sections.append(f"  {content_preview}")
        
        return "\n".join(sections).strip()
    
    @staticmethod
    def _format_minimal_context(context_items: List[ContextItem]) -> str:
        """Minimal context formatting."""
        sections = []
        
        for item in context_items:
            sections.append(f"Task: {item.source_task_goal}")
            sections.append(f"Output: {ContextFormatter._extract_output(item.content)}")
            sections.append("")
        
        return "\n".join(sections).strip()
    
    @staticmethod
    def _extract_output(content: Any) -> str:
        """
        Extract meaningful output from various content types.
        NO TRUNCATION - returns full content.
        """
        if content is None:
            return "[No output]"
        
        # Handle string content
        if isinstance(content, str):
            return content
        
        # Handle objects with specific output fields
        if hasattr(content, 'output_text_with_citations'):
            return content.output_text_with_citations
        elif hasattr(content, 'output_text'):
            return content.output_text
        elif hasattr(content, 'query_used') and hasattr(content, 'results'):
            # Search results
            output_parts = [f"Query: {content.query_used}"]
            if hasattr(content, 'results') and content.results:
                output_parts.append("Results:")
                for i, result in enumerate(content.results, 1):
                    if isinstance(result, dict):
                        title = result.get('title', 'No title')
                        snippet = result.get('snippet', result.get('body', 'No content'))
                        output_parts.append(f"{i}. {title}")
                        output_parts.append(f"   {snippet}")
            return "\n".join(output_parts)
        
        # Handle dict
        if isinstance(content, dict):
            if 'output_text_with_citations' in content:
                return content['output_text_with_citations']
            elif 'output_text' in content:
                return content['output_text']
            elif 'result' in content:
                return str(content['result'])
            elif 'sub_tasks' in content:
                return f"[Plan with {len(content.get('sub_tasks', []))} sub-tasks]"
        
        # Handle PlanOutput
        if hasattr(content, 'sub_tasks'):
            return f"[Plan with {len(content.sub_tasks)} sub-tasks]"
        
        # Default: convert to string
        return str(content)
    
    @staticmethod
    def create_section_separator(title: str) -> str:
        """Create a consistent section separator."""
        return f"\n{'='*3} {title} {'='*3}\n"