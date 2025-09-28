"""
Agent Prompts Module

Contains all system prompts for agents, organized by agent type.
Prompts are kept in Python files for better IDE support, syntax highlighting,
and the ability to use dynamic content.
"""

from .planner_prompts import *
from .executor_prompts import *
from .aggregator_prompts import *
from .atomizer_prompts import *
from .plan_modifier_prompts import *

__all__ = [
    # Planner prompts
    'PLANNER_SYSTEM_MESSAGE',
    'ENHANCED_SEARCH_PLANNER_SYSTEM_MESSAGE',
    'ENHANCED_THINK_PLANNER_SYSTEM_MESSAGE',
    'ENHANCED_WRITE_PLANNER_SYSTEM_MESSAGE',
    'DEEP_RESEARCH_PLANNER_SYSTEM_MESSAGE',
    'GENERAL_TASK_SOLVER_SYSTEM_MESSAGE',     
    # Executor prompts
    'SEARCH_EXECUTOR_SYSTEM_MESSAGE',
    'SEARCH_SYNTHESIZER_SYSTEM_MESSAGE', 
    'BASIC_REPORT_WRITER_SYSTEM_MESSAGE',
    'REASONING_EXECUTOR_SYSTEM_MESSAGE',
    
    # Aggregator prompts
    'DEFAULT_AGGREGATOR_SYSTEM_MESSAGE',
    'SEARCH_AGGREGATOR_SYSTEM_MESSAGE',
    'THINK_AGGREGATOR_SYSTEM_MESSAGE',
    'WRITE_AGGREGATOR_SYSTEM_MESSAGE',
    
    # Atomizer prompts
    'ATOMIZER_SYSTEM_MESSAGE',
    
    # Plan modifier prompts
    'PLAN_MODIFIER_SYSTEM_PROMPT',
] 