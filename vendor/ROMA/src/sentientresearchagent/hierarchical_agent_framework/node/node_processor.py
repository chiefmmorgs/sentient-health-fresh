from typing import List, Optional, Any, Dict, TYPE_CHECKING
from pydantic import BaseModel
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.hitl_coordinator import HITLCoordinator
from sentientresearchagent.hierarchical_agent_framework.node.inode_handler import INodeHandler
from sentientresearchagent.hierarchical_agent_framework.node_handlers import AggregateHandler as AggregatingNodeHandler, ReplanHandler as NeedsReplanNodeHandler, ReadyNodeHandler, HandlerContext
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    AgentTaskInput, PlanOutput, AtomizerOutput, ContextItem,
    PlannerInput, ReplanRequestDetails,
    CustomSearcherOutput, PlanModifierInput
)
# REMOVED incorrect imports of get_agent_adapter and NAMED_AGENTS
from sentientresearchagent.hierarchical_agent_framework.agents.registry import AgentRegistry
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
# Corrected imports:
from sentientresearchagent.hierarchical_agent_framework.context.context_builder import (
    resolve_context_for_agent
)
from sentientresearchagent.hierarchical_agent_framework.context.planner_context_builder import resolve_input_for_planner_agent
from sentientresearchagent.hierarchical_agent_framework.agents.utils import get_context_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES
# Import blueprint-related items
from sentientresearchagent.hierarchical_agent_framework.agent_blueprints import AgentBlueprint, get_blueprint_by_name
from .node_creation_utils import SubNodeCreator
from .node_atomizer_utils import NodeAtomizer
from .node_configs import NodeProcessorConfig
from sentientresearchagent.config import SentientConfig
from ..tracing.manager import TraceManager

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph


MAX_REPLAN_ATTEMPTS = 1


# This local definition of ProcessorContext should mirror the one in inode_handler.py
class ProcessorContext:
    """Holds shared resources and configurations for node handlers."""
    def __init__(self,
                 task_graph: "TaskGraph",
                 knowledge_store: KnowledgeStore,
                 agent_registry: AgentRegistry,
                 config: NodeProcessorConfig,
                 hitl_coordinator: HITLCoordinator,
                 sub_node_creator: SubNodeCreator,
                 node_atomizer: NodeAtomizer,
                 trace_manager: TraceManager,
                 current_agent_blueprint: Optional[AgentBlueprint] = None,
                 update_callback: Optional[callable] = None,
                 update_manager: Optional[Any] = None,
                 context_builder: Optional[Any] = None):
        self.task_graph = task_graph
        self.knowledge_store = knowledge_store
        self.agent_registry = agent_registry
        self.config = config
        self.hitl_coordinator = hitl_coordinator
        self.sub_node_creator = sub_node_creator
        self.node_atomizer = node_atomizer
        self.trace_manager = trace_manager
        self.current_agent_blueprint = current_agent_blueprint
        self.update_callback = update_callback
        self.update_manager = update_manager
        self.context_builder = context_builder


class NodeProcessor:
    """
    Orchestrates the processing of a TaskNode by delegating to appropriate handlers
    based on the node's status and type.
    """

    def __init__(self,
                 task_graph: "TaskGraph",
                 knowledge_store: KnowledgeStore,
                 agent_registry: AgentRegistry,
                 trace_manager: TraceManager,
                 config: Optional[SentientConfig] = None,
                 node_processor_config: Optional[NodeProcessorConfig] = None,
                 agent_blueprint_name: Optional[str] = None,
                 agent_blueprint: Optional[AgentBlueprint] = None,
                 update_callback: Optional[callable] = None,
                 update_manager: Optional[Any] = None,
                 context_builder: Optional[Any] = None):
        logger.info("NodeProcessor initialized.")
        
        self.config = config or SentientConfig()
        self.node_processor_config = node_processor_config if node_processor_config else NodeProcessorConfig()
        self.update_callback = update_callback
        
        self.task_graph = task_graph
        self.knowledge_store = knowledge_store
        self.agent_registry = agent_registry
        self.trace_manager = trace_manager
        self.update_manager = update_manager
        self.context_builder = context_builder
        
        active_blueprint: Optional[AgentBlueprint] = None
        
        # Prioritize direct blueprint object over name lookup
        if agent_blueprint:
            active_blueprint = agent_blueprint
            logger.info(f"NodeProcessor will use provided Agent Blueprint: {active_blueprint.name}")
        elif agent_blueprint_name:
            active_blueprint = get_blueprint_by_name(agent_blueprint_name)
            if active_blueprint:
                logger.info(f"NodeProcessor will use Agent Blueprint: {active_blueprint.name}")
            else:
                logger.warning(f"Agent Blueprint '{agent_blueprint_name}' not found. NodeProcessor will operate without a specific blueprint.")
        else:
            logger.info("NodeProcessor initialized without a specific Agent Blueprint.")

        self.hitl_coordinator = HITLCoordinator(self.node_processor_config)
        self.sub_node_creator = SubNodeCreator(task_graph, knowledge_store)
        # Assuming NodeAtomizer's constructor was updated to take hitl_coordinator directly
        self.node_atomizer = NodeAtomizer(self.hitl_coordinator)

        # Create the context object that handlers will use
        # Create old-style ProcessorContext for compatibility
        self.processor_context = ProcessorContext(
            task_graph=self.task_graph,
            knowledge_store=self.knowledge_store,
            agent_registry=self.agent_registry,
            config=self.node_processor_config,
            hitl_coordinator=self.hitl_coordinator,
            sub_node_creator=self.sub_node_creator,
            node_atomizer=self.node_atomizer,
            trace_manager=self.trace_manager,
            current_agent_blueprint=active_blueprint,
            update_callback=self.update_callback,
            update_manager=self.update_manager,
            context_builder=self.context_builder
        )

        # Create HandlerContext for v2 handlers
        from sentientresearchagent.hierarchical_agent_framework.services import AgentSelector, ContextBuilderService
        from sentientresearchagent.hierarchical_agent_framework.orchestration.state_transition_manager import StateTransitionManager
        
        # Create state transition manager if not available
        state_manager = StateTransitionManager(self.task_graph, knowledge_store)
        
        # Create services needed by v2 handlers
        agent_selector = AgentSelector(blueprint=active_blueprint)
        # Use provided context builder or create default
        if self.context_builder is None:
            context_builder = ContextBuilderService()
        else:
            context_builder = self.context_builder
        
        # For now, we'll keep hitl_service as None since v2 architecture 
        # doesn't provide a clean way to pass it. This is a limitation that
        # needs to be addressed in the architecture
        hitl_service = None
        
        self.handler_context = HandlerContext(
            knowledge_store=knowledge_store,
            agent_registry=agent_registry,
            state_manager=state_manager,
            agent_selector=agent_selector,
            context_builder=context_builder,
            hitl_service=hitl_service,
            trace_manager=trace_manager,
            config=config.dict() if hasattr(config, 'dict') else config,
            task_graph=task_graph,
            update_callback=update_callback
        )
        
        # Setup strategy mapping for handlers (v2 handlers)
        self.handler_strategies: Dict[TaskStatus, Any] = {
            TaskStatus.READY: ReadyNodeHandler(),
            TaskStatus.AGGREGATING: AggregatingNodeHandler(),
            TaskStatus.NEEDS_REPLAN: NeedsReplanNodeHandler()
        }
        logger.info(f"NodeProcessor initialized with handlers for statuses: {list(self.handler_strategies.keys())}")


    async def process_node(self, node: TaskNode, task_graph: "TaskGraph", knowledge_store: KnowledgeStore, update_manager=None):
        """
        Processes a node based on its current status using a strategy pattern.
        
        Args:
            node: The node to process
            task_graph: The task graph
            knowledge_store: The knowledge store
            update_manager: Optional NodeUpdateManager for optimized updates
        """
        # Set project context for this thread before processing
        from sentientresearchagent.core.project_context import set_project_context
        set_project_context(self.trace_manager.project_id)
        
        self.processor_context.task_graph = task_graph
        self.processor_context.knowledge_store = knowledge_store
        self.processor_context.update_manager = update_manager
        
        original_status = node.status

        logger.info(f"NodeProcessor: Processing node {node.task_id} (Status: {node.status.name}, Type: {node.node_type}, Goal: '{node.goal[:30]}...')")
        
        # Create trace when node starts processing (if not already exists)
        self.trace_manager.create_trace(node.task_id, node.goal)
        
        handler = self.handler_strategies.get(node.status)

        if handler:
            try:
                # Update HandlerContext with current state
                self.handler_context.knowledge_store = knowledge_store
                self.handler_context.task_graph = task_graph
                # Note: HITLCoordinator is not the same as HITLService
                # For now, we'll leave hitl_service as None since v2 handlers
                # expect a different interface
                
                # Call v2 handler with HandlerContext
                await handler.handle(node, self.handler_context)
            except Exception as e:
                logger.exception(f"Node {node.task_id}: Unhandled exception in {handler.__class__.__name__}: {e}")
                if node.status not in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    node.update_status(TaskStatus.FAILED, error_msg=f"Error in {handler.__class__.__name__}: {str(e)}")
        else:
            logger.warning(f"Node {node.task_id}: No specific handler for status {node.status.name}. Node will not be processed further in this cycle unless status changes.")

        # Handle sub-node creation for PLAN_DONE nodes (v2 handlers can't access task_graph)
        if node.status == TaskStatus.PLAN_DONE and node.result and hasattr(node.result, 'sub_tasks'):
            logger.info(f"Node {node.task_id} completed planning - creating sub-nodes")
            plan_output = node.result
            if plan_output.sub_tasks:
                # Use the sub_node_creator from processor context
                created_nodes = self.sub_node_creator.create_sub_nodes(node, plan_output)
                logger.info(f"Created {len(created_nodes)} sub-nodes for {node.task_id}")
                
                # Transition sub-nodes with no dependencies to READY
                for sub_node in created_nodes:
                    depends_on = sub_node.aux_data.get('depends_on_indices', []) if sub_node.aux_data is not None else []
                    if not depends_on:  # No dependencies
                        sub_node.update_status(TaskStatus.READY, validate_transition=True, update_manager=update_manager)
                        self.knowledge_store.add_or_update_record_from_node(sub_node)
                        logger.info(f"Transitioned sub-node {sub_node.task_id} to READY (no dependencies)")
        
        if node.status != original_status or node.result is not None or node.error is not None:
             logger.info(f"Node {node.task_id} status changed from {original_status} to {node.status} or has new results/errors. Updating knowledge store.")
        
        # Use optimized knowledge store update if available
        if hasattr(self.knowledge_store, 'add_or_update_record_from_node'):
            # Check if this is the OptimizedKnowledgeStore by checking class name
            if self.knowledge_store.__class__.__name__ == 'OptimizedKnowledgeStore':
                # This is OptimizedKnowledgeStore that accepts immediate parameter
                immediate = update_manager is None or getattr(update_manager, 'execution_strategy', None) != 'deferred'
                self.knowledge_store.add_or_update_record_from_node(node, immediate=immediate)
            else:
                # Regular KnowledgeStore doesn't have immediate parameter
                self.knowledge_store.add_or_update_record_from_node(node)
        
        logger.info(f"NodeProcessor: Finished processing for node {node.task_id}. Final status: {node.status.name}")