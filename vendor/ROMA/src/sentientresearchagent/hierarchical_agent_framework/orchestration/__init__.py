"""
Orchestration components for the Sentient Research Agent framework.

This module contains the refactored components that replace the monolithic
ExecutionEngine with a clean, modular architecture.
"""

from .execution_orchestrator import ExecutionOrchestrator
from .task_scheduler import TaskScheduler
from .deadlock_detector import DeadlockDetector, DeadlockPattern, DeadlockInfo
from .recovery_manager import (
    RecoveryManager,
    RecoveryStrategy,
    RecoveryResult,
    RecoveryAction,
    RetryStrategy,
    ReplanStrategy,
    TimeoutRecoveryStrategy,
    DeadlockRecoveryStrategy
)
from .state_transition_manager import (
    StateTransitionManager,
    StateTransition,
    TransitionEvent
)

__all__ = [
    # Core orchestration
    "ExecutionOrchestrator",
    "TaskScheduler",
    
    # Deadlock detection
    "DeadlockDetector",
    "DeadlockPattern",
    "DeadlockInfo",
    
    # Recovery management
    "RecoveryManager",
    "RecoveryStrategy",
    "RecoveryResult",
    "RecoveryAction",
    "RetryStrategy", 
    "ReplanStrategy",
    "TimeoutRecoveryStrategy",
    "DeadlockRecoveryStrategy",
    
    # State management
    "StateTransitionManager",
    "StateTransition",
    "TransitionEvent",
]