"""
Agent Adapters

Core adapter classes for the YAML-based agent system.
These adapters bridge AgnoAgent instances with the task execution framework.
"""

from typing import Any, Optional
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import LlmApiAdapter
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    PlannerInput, PlanOutput, AgentTaskInput, PlanModifierInput
)
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode

# Import the plan modifier agent that's still needed
from .definitions.plan_modifier_agents import plan_modifier_agno_agent, PLAN_MODIFIER_AGENT_NAME


class PlannerAdapter(LlmApiAdapter):
    """Adapter for planning agents that generate task breakdowns."""
    
    def __init__(self, agno_agent_instance, agent_name: str = "PlannerAdapter"):
        super().__init__(agno_agent_instance, agent_name)

    async def process(self, node: TaskNode, agent_task_input: PlannerInput, trace_manager: "TraceManager") -> PlanOutput:
        """Process planning task and return structured plan output."""
        logger.info(f"  PlannerAdapter: Processing planning task for node {node.task_id}")
        
        # Call the parent's process method which handles the AgnoAgent execution
        result = await super().process(node, agent_task_input, trace_manager)
        
        # Ensure we return PlanOutput
        if isinstance(result, PlanOutput):
            return result
        elif isinstance(result, str):
            # If the model returned a string, try to parse it as JSON
            logger.warning(f"PlannerAdapter: Got string response instead of PlanOutput, attempting JSON extraction")
            
            # Try to extract and parse JSON from the string
            parsed_result = self._extract_and_parse_json(result, PlanOutput)
            if parsed_result:
                logger.info(f"PlannerAdapter: Successfully extracted PlanOutput from string response")
                return parsed_result
            
            # If JSON extraction failed, create an empty plan
            logger.error(f"PlannerAdapter: Failed to extract valid PlanOutput from string response")
            logger.error(f"String content: {result[:500]}...")  # Log first 500 chars for debugging
            
            # Return empty plan to prevent crash
            empty_plan = PlanOutput(sub_goals=[])
            logger.warning(f"PlannerAdapter: Returning empty plan for node {node.task_id}")
            return empty_plan
        else:
            logger.error(f"PlannerAdapter: Expected PlanOutput, got {type(result)}")
            # Return empty plan instead of raising error
            empty_plan = PlanOutput(sub_goals=[])
            logger.warning(f"PlannerAdapter: Returning empty plan for node {node.task_id}")
            return empty_plan


class ExecutorAdapter(LlmApiAdapter):
    """Adapter for execution agents that perform specific tasks."""
    
    def __init__(self, agno_agent_instance, agent_name: str = "ExecutorAdapter"):
        super().__init__(agno_agent_instance, agent_name)

    async def process(self, node: TaskNode, agent_task_input: AgentTaskInput, trace_manager: "TraceManager") -> Any:
        """
        Process execution task.
        If the underlying agent returns a raw string, wrap it in a standardized
        dictionary to ensure consistent output format from all executors.
        """
        logger.info(f"  ExecutorAdapter: Processing execution task for node {node.task_id}")
        
        # Call the parent's process method which handles the AgnoAgent execution
        result = await super().process(node, agent_task_input, trace_manager)
        
        # NEW: Standardize string outputs into a dictionary consistent with searcher output
        if isinstance(result, str):
            logger.info(f"    ExecutorAdapter: Wrapping raw string output in standardized dictionary for node {node.task_id}")
            return {
                "query_used": agent_task_input.current_goal,
                "output_text": result
            }
        
        # If it's not a string, return it as is (e.g., a dictionary from a custom searcher)
        return result


class AtomizerAdapter(LlmApiAdapter):
    """Adapter for atomizer agents that break down complex tasks."""
    
    def __init__(self, agno_agent_instance, agent_name: str = "AtomizerAdapter"):
        super().__init__(agno_agent_instance, agent_name)

    async def process(self, node: TaskNode, agent_task_input: AgentTaskInput, trace_manager: "TraceManager") -> Any:
        """Process atomization task and return result."""
        logger.info(f"  AtomizerAdapter: Processing atomization task for node {node.task_id}")
        
        # Call the parent's process method which handles the AgnoAgent execution
        result = await super().process(node, agent_task_input, trace_manager)
        return result


class AggregatorAdapter(LlmApiAdapter):
    """Adapter for aggregator agents that combine results."""
    
    def __init__(self, agno_agent_instance, agent_name: str = "AggregatorAdapter"):
        super().__init__(agno_agent_instance, agent_name)

    async def process(self, node: TaskNode, agent_task_input: AgentTaskInput, trace_manager: "TraceManager") -> Any:
        """Process aggregation task and return result."""
        logger.info(f"  AggregatorAdapter: Processing aggregation task for node {node.task_id}")
        
        # Call the parent's process method which handles the AgnoAgent execution
        result = await super().process(node, agent_task_input, trace_manager)
        return result


class PlanModifierAdapter(LlmApiAdapter):
    """Adapter for plan modification agents (HITL functionality)."""
    
    def __init__(self, agno_agent_instance=None, agent_name: str = PLAN_MODIFIER_AGENT_NAME):
        # Use the global plan modifier agent if none provided
        if agno_agent_instance is None:
            agno_agent_instance = plan_modifier_agno_agent
        super().__init__(agno_agent_instance, agent_name)

    async def process(self, node: TaskNode, agent_task_input: PlanModifierInput, trace_manager: "TraceManager") -> PlanOutput:
        """Process plan modification task and return updated plan."""
        logger.info(f"  PlanModifierAdapter: Processing plan modification for node {node.task_id}")
        
        # Call the parent's process method which handles the AgnoAgent execution
        result = await super().process(node, agent_task_input, trace_manager)
        
        # Ensure we return PlanOutput
        if isinstance(result, PlanOutput):
            return result
        else:
            logger.error(f"PlanModifierAdapter: Expected PlanOutput, got {type(result)}")
            raise ValueError(f"PlanModifierAdapter returned unexpected type: {type(result)}")