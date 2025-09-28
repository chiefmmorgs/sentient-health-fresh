"""
HITLService - Centralized Human-in-the-Loop service.

This service consolidates all HITL logic in one place,
making it easier to understand and modify HITL behavior.
"""

from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
import asyncio
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import PlanOutput

if TYPE_CHECKING:
    from sentientresearchagent.config import SentientConfig


class HITLCheckpoint(Enum):
    """HITL checkpoint types."""
    ROOT_GOAL_REVIEW = "root_goal_review"
    PLAN_GENERATION = "plan_generation"
    PLAN_MODIFICATION = "plan_modification"
    ATOMIZATION = "atomization"
    BEFORE_EXECUTION = "before_execution"
    AGGREGATION_REVIEW = "aggregation_review"


class HITLDecision(Enum):
    """HITL decision types."""
    APPROVED = "approved"
    REQUEST_MODIFICATION = "request_modification"
    REJECTED = "rejected"
    ABORTED = "aborted"
    TIMEOUT = "timeout"


@dataclass
class HITLConfig:
    """Configuration for HITL behavior."""
    enabled: bool = False
    root_plan_only: bool = False
    timeout_seconds: float = 300.0
    
    # Checkpoint enablement
    enable_root_goal_review: bool = True
    enable_plan_generation: bool = True
    enable_plan_modification: bool = True
    enable_atomization: bool = False
    enable_before_execution: bool = False
    enable_aggregation_review: bool = False
    
    # Auto-approval settings
    auto_approve_after_timeout: bool = False
    auto_approve_trivial_tasks: bool = True
    
    @classmethod
    def from_config(cls, config: "SentientConfig") -> "HITLConfig":
        """Create HITLConfig from system config."""
        execution_config = config.execution
        
        return cls(
            enabled=execution_config.enable_hitl,
            root_plan_only=getattr(execution_config, 'hitl_root_plan_only', False),
            timeout_seconds=getattr(execution_config, 'hitl_timeout_seconds', 300.0),
            enable_plan_generation=getattr(execution_config, 'hitl_after_plan_generation', True),
            enable_plan_modification=getattr(execution_config, 'hitl_after_modified_plan', True),
            enable_atomization=getattr(execution_config, 'hitl_after_atomizer', False),
            enable_before_execution=getattr(execution_config, 'hitl_before_execute', False),
            auto_approve_after_timeout=getattr(execution_config, 'hitl_auto_approve_timeout', False)
        )


class HITLService:
    """
    Centralized service for all Human-in-the-Loop interactions.
    
    This service:
    - Manages HITL configuration and policies
    - Handles all HITL checkpoints consistently
    - Provides a clean interface for HITL reviews
    - Tracks HITL metrics and history
    """
    
    def __init__(self, config: HITLConfig, websocket_handler: Optional[Any] = None):
        """
        Initialize the HITL service.
        
        Args:
            config: HITL configuration
            websocket_handler: Handler for WebSocket communication (optional)
        """
        self.config = config
        self.websocket_handler = websocket_handler
        
        # Metrics tracking
        self._metrics = {
            "total_reviews": 0,
            "approved": 0,
            "modified": 0,
            "rejected": 0,
            "timeouts": 0,
            "average_response_time": 0.0
        }
        
        # Review history
        self._review_history: List[Dict[str, Any]] = []
        self._max_history = 100
        
        logger.info(f"HITLService initialized - enabled: {config.enabled}, "
                   f"root_only: {config.root_plan_only}")
    
    async def review_plan(
        self,
        node: TaskNode,
        plan_output: PlanOutput,
        planning_context: Optional[Dict[str, Any]] = None,
        is_replan: bool = False
    ) -> Dict[str, Any]:
        """
        Review a generated plan.
        
        Args:
            node: Node with the plan
            plan_output: The generated plan
            planning_context: Context used for planning
            is_replan: Whether this is a replan
            
        Returns:
            Review result with status and optional modification instructions
        """
        checkpoint = HITLCheckpoint.PLAN_GENERATION
        
        # Check if review is needed
        if not self._should_review(checkpoint, node):
            return {"status": HITLDecision.APPROVED.value, "auto_approved": True}
        
        # Prepare review data
        review_data = {
            "node_id": node.task_id,
            "node_goal": node.goal,
            "node_layer": node.layer,
            "is_replan": is_replan,
            "plan_summary": self._summarize_plan(plan_output),
            "sub_tasks": [
                {
                    "goal": task.goal,
                    "task_type": task.task_type.value if hasattr(task.task_type, 'value') else str(task.task_type),
                    "dependencies": getattr(task, 'dependencies', [])
                }
                for task in plan_output.sub_tasks[:10]  # Limit for UI
            ]
        }
        
        # Request review
        result = await self._request_review(
            checkpoint=checkpoint,
            node=node,
            data=review_data,
            message=f"Review {'re' if is_replan else ''}plan for: {node.goal}"
        )
        
        return result
    
    async def review_modified_plan(
        self,
        node: TaskNode,
        modified_plan: PlanOutput,
        replan_attempt: int
    ) -> Dict[str, Any]:
        """
        Review a modified plan.
        
        Args:
            node: Node with the modified plan
            modified_plan: The modified plan
            replan_attempt: Current replan attempt number
            
        Returns:
            Review result
        """
        checkpoint = HITLCheckpoint.PLAN_MODIFICATION
        
        # Check if review is needed
        if not self._should_review(checkpoint, node):
            return {"status": HITLDecision.APPROVED.value, "auto_approved": True}
        
        # Prepare review data
        review_data = {
            "node_id": node.task_id,
            "node_goal": node.goal,
            "replan_attempt": replan_attempt,
            "modification_reason": node.aux_data.get('user_modification_instructions', 'System replan'),
            "plan_summary": self._summarize_plan(modified_plan),
            "sub_tasks": [
                {"goal": task.goal, "task_type": str(task.task_type)}
                for task in modified_plan.sub_tasks[:10]
            ]
        }
        
        # Request review
        result = await self._request_review(
            checkpoint=checkpoint,
            node=node,
            data=review_data,
            message=f"Review modified plan (attempt {replan_attempt})"
        )
        
        return result
    
    async def review_execution(
        self,
        node: TaskNode,
        execution_context: Any
    ) -> Dict[str, Any]:
        """
        Review before execution.
        
        Args:
            node: Node to execute
            execution_context: Context for execution
            
        Returns:
            Review result
        """
        checkpoint = HITLCheckpoint.BEFORE_EXECUTION
        
        # Check if review is needed
        if not self._should_review(checkpoint, node):
            return {"status": HITLDecision.APPROVED.value, "auto_approved": True}
        
        # Check if this is a trivial task
        if self._is_trivial_task(node) and self.config.auto_approve_trivial_tasks:
            logger.info(f"Auto-approving trivial task: {node.task_id}")
            return {"status": HITLDecision.APPROVED.value, "auto_approved": True}
        
        # Prepare review data
        review_data = {
            "node_id": node.task_id,
            "node_goal": node.goal,
            "task_type": str(node.task_type),
            "context_summary": self._summarize_context(execution_context)
        }
        
        # Request review
        result = await self._request_review(
            checkpoint=checkpoint,
            node=node,
            data=review_data,
            message=f"Review before executing: {node.goal}"
        )
        
        return result
    
    def _should_review(self, checkpoint: HITLCheckpoint, node: TaskNode) -> bool:
        """
        Determine if a checkpoint should be reviewed.
        
        Args:
            checkpoint: Type of checkpoint
            node: Node being reviewed
            
        Returns:
            True if review is needed
        """
        # Check if HITL is enabled
        if not self.config.enabled:
            return False
        
        # Check root-only mode
        if self.config.root_plan_only:
            is_root = (
                node.task_id == "root" or
                node.layer == 0 or
                node.parent_node_id is None
            )
            
            # In root-only mode, only review root node plans
            if checkpoint == HITLCheckpoint.PLAN_GENERATION:
                return is_root
            elif checkpoint == HITLCheckpoint.PLAN_MODIFICATION:
                return is_root  # Allow modification reviews for root
            else:
                return False  # Skip other checkpoints in root-only mode
        
        # Check checkpoint-specific enablement
        checkpoint_enabled = {
            HITLCheckpoint.ROOT_GOAL_REVIEW: self.config.enable_root_goal_review,
            HITLCheckpoint.PLAN_GENERATION: self.config.enable_plan_generation,
            HITLCheckpoint.PLAN_MODIFICATION: self.config.enable_plan_modification,
            HITLCheckpoint.ATOMIZATION: self.config.enable_atomization,
            HITLCheckpoint.BEFORE_EXECUTION: self.config.enable_before_execution,
            HITLCheckpoint.AGGREGATION_REVIEW: self.config.enable_aggregation_review,
        }
        
        return checkpoint_enabled.get(checkpoint, False)
    
    def _is_trivial_task(self, node: TaskNode) -> bool:
        """Check if a task is trivial and can be auto-approved."""
        # Simple heuristics for trivial tasks
        goal_lower = node.goal.lower()
        
        trivial_patterns = [
            "format", "convert", "extract", "count", "list",
            "get", "fetch", "retrieve", "check", "verify"
        ]
        
        return any(pattern in goal_lower for pattern in trivial_patterns)
    
    async def _request_review(
        self,
        checkpoint: HITLCheckpoint,
        node: TaskNode,
        data: Dict[str, Any],
        message: str
    ) -> Dict[str, Any]:
        """
        Request human review via WebSocket or other mechanism.
        
        Args:
            checkpoint: Type of checkpoint
            node: Node being reviewed
            data: Data for review
            message: Message to display
            
        Returns:
            Review result
        """
        import time
        start_time = time.time()
        
        logger.info(f"Requesting HITL review for {checkpoint.value} on node {node.task_id}")
        
        # Update metrics
        self._metrics["total_reviews"] += 1
        
        try:
            # If we have a WebSocket handler, use it
            if self.websocket_handler:
                result = await self._websocket_review(checkpoint, data, message)
            else:
                # Fallback to console or auto-approval
                result = await self._console_review(checkpoint, data, message)
            
            # Update metrics based on result
            status = result.get("status", HITLDecision.APPROVED.value)
            if status == HITLDecision.APPROVED.value:
                self._metrics["approved"] += 1
            elif status == HITLDecision.REQUEST_MODIFICATION.value:
                self._metrics["modified"] += 1
            elif status == HITLDecision.REJECTED.value:
                self._metrics["rejected"] += 1
            elif status == HITLDecision.TIMEOUT.value:
                self._metrics["timeouts"] += 1
            
            # Update average response time
            response_time = time.time() - start_time
            self._update_average_response_time(response_time)
            
            # Record in history
            self._record_review(checkpoint, node, status, response_time)
            
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"HITL review timed out for {node.task_id}")
            self._metrics["timeouts"] += 1
            
            if self.config.auto_approve_after_timeout:
                logger.info("Auto-approving after timeout")
                return {"status": HITLDecision.APPROVED.value, "timeout": True}
            else:
                return {"status": HITLDecision.TIMEOUT.value}
        
        except Exception as e:
            logger.error(f"HITL review error: {e}")
            # Default to approval on error
            return {"status": HITLDecision.APPROVED.value, "error": str(e)}
    
    async def _websocket_review(
        self,
        checkpoint: HITLCheckpoint,
        data: Dict[str, Any],
        message: str
    ) -> Dict[str, Any]:
        """Request review via WebSocket."""
        # This would integrate with the actual WebSocket implementation
        # For now, return a placeholder
        logger.info("WebSocket review not implemented - auto-approving")
        return {"status": HITLDecision.APPROVED.value, "auto_approved": True}
    
    async def _console_review(
        self,
        checkpoint: HITLCheckpoint,
        data: Dict[str, Any],
        message: str
    ) -> Dict[str, Any]:
        """Simple console-based review for testing."""
        # In production, this would integrate with the UI
        # For now, auto-approve
        logger.info(f"Console review: {message}")
        logger.info(f"Data: {data}")
        logger.info("Auto-approving (console mode)")
        
        return {"status": HITLDecision.APPROVED.value, "console_mode": True}
    
    def _summarize_plan(self, plan: PlanOutput) -> str:
        """Create a summary of a plan."""
        if not plan.sub_tasks:
            return "Empty plan"
        
        task_types = {}
        for task in plan.sub_tasks:
            task_type = str(task.task_type)
            task_types[task_type] = task_types.get(task_type, 0) + 1
        
        summary_parts = [f"{count} {task_type}" for task_type, count in task_types.items()]
        return f"{len(plan.sub_tasks)} tasks: {', '.join(summary_parts)}"
    
    def _summarize_context(self, context: Any) -> str:
        """Create a summary of execution context."""
        if hasattr(context, 'formatted_full_context'):
            context_text = context.formatted_full_context or ""
            return f"{len(context_text)} characters of context"
        return "Context provided"
    
    def _update_average_response_time(self, response_time: float):
        """Update the running average response time."""
        current_avg = self._metrics["average_response_time"]
        total_reviews = self._metrics["total_reviews"]
        
        self._metrics["average_response_time"] = (
            (current_avg * (total_reviews - 1) + response_time) / total_reviews
        )
    
    def _record_review(
        self,
        checkpoint: HITLCheckpoint,
        node: TaskNode,
        status: str,
        response_time: float
    ):
        """Record a review in history."""
        record = {
            "checkpoint": checkpoint.value,
            "node_id": node.task_id,
            "node_goal": node.goal[:100],
            "status": status,
            "response_time": response_time,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        self._review_history.append(record)
        
        # Trim history if needed
        if len(self._review_history) > self._max_history:
            self._review_history = self._review_history[-self._max_history:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get HITL metrics."""
        return self._metrics.copy()
    
    def get_review_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent review history."""
        return self._review_history[-limit:]
    
    def update_config(self, new_config: HITLConfig):
        """Update HITL configuration."""
        self.config = new_config
        logger.info(f"HITL config updated - enabled: {new_config.enabled}, "
                   f"root_only: {new_config.root_plan_only}")