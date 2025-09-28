from loguru import logger

# Import the class, not the global instances
from .registry import AgentRegistry

logger.info("🤖 Initializing YAML-based agent system...")

# YAML-based agent integration (replaces legacy system)
def integrate_yaml_agents_lazy(agent_registry: AgentRegistry):
    """
    Load and integrate YAML-configured agents into the provided registry instance.
    
    Args:
        agent_registry: The AgentRegistry instance to populate.
    """
    try:
        from ..agent_configs.registry_integration import integrate_yaml_agents
        
        logger.info("🔄 Loading YAML-based agents into instance registry...")
        integration_results = integrate_yaml_agents(agent_registry)
        
        if integration_results:
            logger.info(f"✅ YAML Agent Integration Results:")
            logger.info(f"   📋 Action keys registered: {integration_results.get('registered_action_keys', 0)}")
            logger.info(f"   🏷️  Named keys registered: {integration_results.get('registered_named_keys', 0)}")
            logger.info(f"   ⏭️  Skipped agents: {integration_results.get('skipped_agents', 0)}")
            logger.info(f"   ❌ Failed registrations: {integration_results.get('failed_registrations', 0)}")
            
            # Log final registry state from the instance
            num_adapters = len(agent_registry.get_all_registered_agents())
            num_named = len(agent_registry.get_all_named_agents())
            logger.info(f"📊 Final instance registry state - AGENTS: {num_adapters} entries, NAMED: {num_named} entries")
        
        return integration_results
        
    except Exception as e:
        logger.error(f"❌ Failed to integrate YAML agents: {e}", exc_info=True)
        logger.error("🚨 No agents will be available! Check your YAML configuration.")
        return None

# Final check is no longer relevant here as we don't rely on global state at import time.
logger.info("✅ Agent system module loaded successfully")

__all__ = [
    "AgentRegistry",
    "integrate_yaml_agents_lazy",
]
