"""
Exa Custom Searcher Adapter - Uses Exa API for search and LiteLLM for processing results.
"""

import os
import asyncio
from typing import Dict, List, Optional, TYPE_CHECKING
from loguru import logger
from dotenv import load_dotenv

try:
    from exa_py import Exa
except ImportError:
    logger.warning("Warning: exa_py module not found. ExaCustomSearchAdapter will not be usable.")
    Exa = None

try:
    from litellm import acompletion
except ImportError:
    logger.warning("Warning: litellm module not found. ExaCustomSearchAdapter will not be usable.")
    acompletion = None

from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    AnnotationURLCitationModel,
    AgentTaskInput
)
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode
from sentientresearchagent.hierarchical_agent_framework.agent_configs.prompts.searcher_prompts import (
    EXA_CUSTOM_SEARCH_SYSTEM_PROMPT
)

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.tracing.manager import TraceManager

load_dotenv()


class ExaCustomSearchAdapter(BaseAdapter):
    """
    A direct adapter that uses Exa API for search and LiteLLM for processing results.
    Retrieves comprehensive data from multiple sources and formats them for LLM processing.
    """
    adapter_name: str = "ExaCustomSearchAdapter"
    model_id: str = "gpt-4o"  # Default model for LiteLLM, can be configured

    def __init__(self, exa_client=None, model_id: str = "gpt-4o", num_results: int = 5, **kwargs):
        super().__init__(self.adapter_name)
        
        if Exa is None:
            raise ImportError("exa_py module is not available. Please install 'exa-py'.")
        if acompletion is None:
            raise ImportError("litellm module is not available. Please install 'litellm'.")
        
        # Get API key
        api_key = os.getenv("EXA_API_KEY")
        if not api_key:
            raise ValueError("EXA_API_KEY environment variable is required for ExaCustomSearchAdapter")
        
        # Create Exa client
        self.exa_client = exa_client or Exa(api_key=api_key)
        self.model_id = model_id
        self.num_results = num_results
        
        # Store any additional parameters for future use
        self.additional_params = kwargs
        
        logger.info(f"Initialized {self.agent_name} with model: {self.model_id} and num_results: {self.num_results}")

    async def process(self, node: TaskNode, agent_task_input: AgentTaskInput, trace_manager: "TraceManager") -> Dict:
        """
        Processes the task by:
        1. Using Exa API to search for relevant content
        2. Formatting results with source separators
        3. Using LiteLLM to extract and present comprehensive data
        """
        from sentientresearchagent.hierarchical_agent_framework.tracing.manager import TraceManager
        
        query = agent_task_input.current_goal
        logger.info(f"  Adapter '{self.adapter_name}': Processing node {node.task_id} (Query: '{query[:100]}...') with Exa search")
        
        # Build context string from relevant_context_items
        context_strings = []
        for ctx_item in agent_task_input.relevant_context_items:
            context_strings.append(f"\n--- Task ID: {ctx_item.source_task_id} ---\n[{ctx_item.content_type_description}]:\n{ctx_item.content}\n")
        
        full_context = "\n".join(context_strings) if context_strings else "No additional context provided."
        
        # Update the existing execution stage (don't start a new one)
        trace_manager.update_stage(
            node_id=node.task_id,
            stage_name="execution",
            agent_name=self.adapter_name,
            adapter_name=self.__class__.__name__,
            user_input=query,
            input_context={
                "query": query,
                "task_type": str(node.task_type),
                "node_type": str(node.node_type),
                "context_items_count": len(agent_task_input.relevant_context_items),
                "has_dependency_context": any(item.content_type_description == "explicit_dependency_output" for item in agent_task_input.relevant_context_items),
                "full_agent_task_input": agent_task_input.model_dump(),
                "relevant_context": full_context
            },
            model_info={"model": self.model_id, "provider": "litellm"}
        )
        
        try:
            # Step 1: Search using Exa
            logger.info(f"    {self.adapter_name}: Searching with Exa API...")
            
            # Use search_and_contents to get both search results and content
            exa_results = await asyncio.to_thread(
                self.exa_client.search_and_contents,
                query,
                text=True,
                num_results=self.num_results,
                context=True  # Include context for better understanding
            )
            
            if not exa_results or not exa_results.results:
                logger.warning(f"    {self.adapter_name}: No results found from Exa search")
                return {
                    "query_used": query,
                    "output_text": "No results found for the given query."
                }
            
            logger.success(f"    {self.adapter_name}: Retrieved {len(exa_results.results)} results from Exa")
            
            # Step 2: Format results with separators
            formatted_sources = []
            citations = []
            
            for i, result in enumerate(exa_results.results):
                # Extract relevant fields
                title = getattr(result, 'title', f'Source {i+1}')
                url = getattr(result, 'url', '')
                text = getattr(result, 'text', '')
                published_date = getattr(result, 'published_date', None)
                
                # Format source with separators
                source_content = f"-------------START OF SOURCE {i+1}-------------\n"
                source_content += f"Title: {title}\n"
                source_content += f"URL: {url}\n"
                if published_date:
                    source_content += f"Published: {published_date}\n"
                source_content += f"\nContent:\n{text}\n"
                source_content += f"-------------END OF SOURCE {i+1}-------------"
                
                formatted_sources.append(source_content)
                
                # Add to citations
                citations.append({
                    'title': title,
                    'url': url,
                    'start_index': 0,
                    'end_index': len(text),
                    'type': 'url_citation'
                })
            
            # Step 3: Create system prompt for LiteLLM
            system_prompt = EXA_CUSTOM_SEARCH_SYSTEM_PROMPT

            # Step 4: Combine all sources
            all_sources = "\n\n".join(formatted_sources)
            
            # Step 5: Create user prompt with context
            context_section = ""
            if agent_task_input.relevant_context_items:
                context_section = "\n\n[IMPORTANT CONTEXT FROM PREVIOUS TASKS]\n"
                context_section += "This context is CRITICAL for understanding what to extract from the sources below.\n"
                context_section += "The context shows what has already been discovered - use it to identify the specific data needed:\n"
                for ctx_item in agent_task_input.relevant_context_items:
                    context_section += f"\n[{ctx_item.content_type_description}]:\n{ctx_item.content}\n"
                context_section += "\n\n[USE THE ABOVE CONTEXT TO]:\n"
                context_section += "- Identify specific names, terms, or entities mentioned that you should look for in the sources\n"
                context_section += "- Understand what information has already been found and what still needs to be extracted\n"
                context_section += "- Focus your extraction on data that relates to the entities/terms in the context\n"
            
            user_prompt = f"""Query: {query}{context_section}

Below are {len(formatted_sources)} sources with relevant information. Extract and present ALL data related to the query:

{all_sources}

IMPORTANT: Include EVERY piece of relevant data from ALL sources. Do not summarize or truncate."""

            # Step 6: Call LiteLLM
            logger.info(f"    {self.adapter_name}: Processing sources with LiteLLM model {self.model_id}...")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Log the complete LLM input messages
            logger.debug(f"Complete LLM input for {self.adapter_name}:\nSystem: {system_prompt[:200]}...\nUser: {user_prompt[:200]}...")
            
            # Update trace with full LLM input
            trace_manager.update_stage(
                node_id=node.task_id,
                stage_name="execution",
                additional_data={
                    "llm_input_messages": messages,
                    "llm_input_length": sum(len(msg["content"]) for msg in messages),
                    "exa_results_count": len(exa_results.results) if exa_results else 0
                }
            )
            
            # Use acompletion for async call
            llm_response = await acompletion(
                model=self.model_id,
                messages=messages,
                temperature=0.1,  # Low temperature for factual accuracy
                max_tokens=4000   # Allow for comprehensive responses
            )
            
            # Extract the response text with proper null checks
            output_text = None
            if llm_response and hasattr(llm_response, 'choices') and llm_response.choices:
                if len(llm_response.choices) > 0 and llm_response.choices[0].message:
                    output_text = llm_response.choices[0].message.content
            
            if not output_text:
                raise ValueError("No response content received from LLM")
            
            logger.success(f"    {self.adapter_name}: Successfully processed {len(formatted_sources)} sources")
            
            # Return formatted output matching other searchers
            clean_output = {
                "query_used": query,
                "output_text": output_text,
                "citations": [ann if isinstance(ann, dict) else ann.dict() for ann in citations]  # Ensure proper format
            }
            
            # Update and complete tracing
            trace_manager.update_stage(
                node_id=node.task_id,
                stage_name="execution",
                llm_response=output_text,
                additional_data={
                    "llm_input_messages": messages,
                    "llm_input_length": sum(len(msg["content"]) for msg in messages),
                    "full_llm_output": output_text,
                    "llm_output_length": len(output_text),
                    "citations_count": len(citations),
                    "exa_sources_included": len(formatted_sources),
                    "exa_results_count": len(exa_results.results) if exa_results else 0
                }
            )
            
            # Don't complete the stage here - let the node handler do it
            # This prevents overwriting the input_context and other fields
            
            node.output_type_description = "custom_searcher_output"
            
            return clean_output
            
        except Exception as e:
            error_message = f"Error during {self.adapter_name} execution for node {node.task_id} (Query: {query}): {e}"
            logger.error(f"  Adapter Error: {error_message}")
            
            # Update stage with error but don't complete it - let node handler do that
            trace_manager.update_stage(
                node_id=node.task_id,
                stage_name="execution",
                error_message=error_message
            )
            
            return {
                "query_used": query,
                "output_text": f"Search Failed: {e}"
            }