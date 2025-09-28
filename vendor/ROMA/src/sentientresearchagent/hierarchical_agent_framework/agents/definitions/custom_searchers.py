import os
import requests
import json
import types
import asyncio
import time
from dotenv import load_dotenv
from typing import Dict, Optional, List, TYPE_CHECKING
from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode

try:
    from openai import OpenAI, AsyncOpenAI
except ImportError:
    logger.warning("Warning: openai module not found. OpenAICustomSearchAdapter will not be usable.")
    OpenAI = None
    AsyncOpenAI = None

try:
    from google import genai
    from google.genai.types import Tool, GenerateContentConfig, GoogleSearch
except ImportError:
    logger.warning("Warning: google-genai module not found. GeminiCustomSearchAdapter will not be usable.")
    genai = None

try:
    import wikipediaapi
except ImportError:
    logger.warning("Warning: wikipediaapi module not found. Wikipedia enhancement will not be available.")
    wikipediaapi = None

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
    CustomSearcherOutput,
    AnnotationURLCitationModel,
    AgentTaskInput
)
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
from sentientresearchagent.hierarchical_agent_framework.agent_configs.prompts.searcher_prompts import (
    OPENAI_CUSTOM_SEARCH_PROMPT,
    GEMINI_CUSTOM_SEARCH_PROMPT,
    CONTEXT_EMPHASIS_SECTION
)

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode
    from sentientresearchagent.hierarchical_agent_framework.tracing.manager import TraceManager

load_dotenv()

# Helper function to extract Wikipedia content
async def fetch_wikipedia_content(url: str) -> Optional[str]:
    """Fetch content from a Wikipedia URL using wikipediaapi."""
    if wikipediaapi is None:
        return None
    
    try:
        # Extract page title from URL
        # Handle different Wikipedia URL formats
        import re
        patterns = [
            r'wikipedia\.org/wiki/([^#?]+)',  # Standard wiki URL
            r'wikipedia\.org/.*[?&]title=([^&#]+)',  # URL with title parameter
        ]
        
        page_title = None
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                page_title = match.group(1).replace('_', ' ')
                break
        
        if not page_title:
            return None
        
        # Create Wikipedia API client
        wiki_wiki = wikipediaapi.Wikipedia(
            language='en',
            extract_format=wikipediaapi.ExtractFormat.WIKI,
            user_agent='SentientResearchAgent/1.0 (https://github.com/salzubi401/SentientResearchAgent)'
        )
        
        page = wiki_wiki.page(page_title)
        if page.exists():
            # Return summary + first section for manageable content
            content = f"Wikipedia: {page.title}\n\n{page.summary}\n\n"
            
            # Add section content if available
            sections = page.sections
            if sections:
                # Get first few sections (avoid overwhelming the context)
                for i, section in enumerate(sections[:3]):
                    if section.text:
                        content += f"\n## {section.title}\n{section.text}\n"
            
            return content
        else:
            return None
            
    except Exception as e:
        logger.warning(f"Error fetching Wikipedia content from {url}: {e}")
        return None

# --- OpenAI Custom Searcher with Annotations (Adapter Version) ---
class OpenAICustomSearchAdapter(BaseAdapter):
    """
    A direct adapter that uses OpenAI's gpt-4o (or similar) with the 
    'web_search_preview' tool to get answers with URL annotations.
    
    Supports two modes:
    1. Direct OpenAI API (default) - Uses responses.create with web_search_preview tool
    2. OpenRouter API (when use_openrouter=True) - Uses chat.completions with web_search tool
    
    Configuration options:
    - model_id: The model to use (e.g., "gpt-4o" or "openai/gpt-4o-search-preview")
    - use_openrouter: Whether to use OpenRouter API instead of OpenAI (default: False)
    - search_context_size: Search context depth - "medium", "high", or "low" (default: "standard")
    
    Note: Both modes enforce tool_choice to ensure the web search tool is always used.
    - OpenRouter: tool_choice={"type": "tool", "function": {"name": "web_search"}}
    - OpenAI: tool_choice={"type": "web_search_preview"}
    
    It does not use an underlying AgnoAgent.
    """
    adapter_name: str = "OpenAICustomSearchAdapter" 
    model_id: str = "gpt-4o" # Updated to use gpt-4o for better search results

    def __init__(self, openai_client = None, model_id: str = "gpt-4o", use_openrouter: bool = False, search_context_size: str = "standard", **kwargs):
        super().__init__(self.adapter_name)
        if AsyncOpenAI is None:
            raise ImportError("AsyncOpenAI client from openai library is not available. Please install or update 'openai'.")
        
        self.use_openrouter = use_openrouter
        self.search_context_size = search_context_size  # Can be "medium", "high", or "low"
        
        if use_openrouter:
            # Use OpenRouter configuration
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY environment variable is required when use_openrouter=True")
            
            base_url = "https://openrouter.ai/api/v1"
            logger.info(f"Using OpenRouter with base URL: {base_url}")
            
            # Ensure model_id has the proper OpenRouter format
            if not model_id.startswith("openai/"):
                model_id = f"openai/{model_id}"
            
            self.client = openai_client or AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
        else:
            # Use standard OpenAI configuration
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required for OpenAICustomSearchAdapter")
            
            self.client = openai_client or AsyncOpenAI(api_key=api_key)
        
        self.model_id = model_id
        logger.info(f"Initialized {self.agent_name} with model: {self.model_id} (OpenRouter: {use_openrouter}, search_context_size: {search_context_size})")

    async def process(self, node: TaskNode, agent_task_input: AgentTaskInput, trace_manager: "TraceManager") -> Dict:
        """
        Processes the task by extracting the goal as a query, calling OpenAI with
        web_search_preview using client.responses.create.
        Prioritizes response.output_text, and optionally parses nested text/annotations.
        """
        # Import trace_manager here to avoid circular imports
        from sentientresearchagent.hierarchical_agent_framework.tracing.manager import TraceManager
        
        query = agent_task_input.current_goal
        logger.info(f"  Adapter '{self.adapter_name}': Processing node {node.task_id} (Query: '{query[:100]}...') with OpenAI model {self.model_id}")
        
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
            model_info={"model": self.model_id, "provider": "openai"}
        )
        
        output_text_with_citations = f"Error: Could not retrieve output_text for query: {query}" # Default error
        parsed_text_content: Optional[str] = None
        parsed_annotations: List[AnnotationURLCitationModel] = []

        try:
            # Ensure client is async and has responses.create
            if not isinstance(self.client, AsyncOpenAI) or not hasattr(self.client.responses, 'create'):
                 logger.error(f"  {self.adapter_name}: Invalid OpenAI client. Expected AsyncOpenAI with responses.create. Got: {type(self.client)}")
                 raise TypeError("Invalid OpenAI client setup for async operation.")

            # Build enhanced query with context
            context_section = ""
            context_emphasis = ""
            if agent_task_input.relevant_context_items:
                context_section = "\n\n[IMPORTANT CONTEXT FROM PREVIOUS TASKS - HIGHLY RELEVANT TO YOUR SEARCH]\n"
                context_section += "The following context contains crucial information that will help you search more effectively.\n"
                context_section += "PAY CLOSE ATTENTION as this context likely contains specific names, terms, or data you need to search for:\n"
                for ctx_item in agent_task_input.relevant_context_items:
                    context_section += f"\n[{ctx_item.content_type_description}]:\n{ctx_item.content}\n"
                
                # Add emphasis in guidelines
                context_emphasis = CONTEXT_EMPHASIS_SECTION
            
            # Expert searcher prompt for comprehensive data retrieval
            enhanced_query = f"""{OPENAI_CUSTOM_SEARCH_PROMPT}{context_emphasis}{context_section}

QUERY: {query}

RETRIEVED DATA:"""
            
            # Log the complete LLM input message
            logger.debug(f"Complete LLM input for {self.adapter_name}:\n{enhanced_query}")
            
            # Update trace with full LLM input
            trace_manager.update_stage(
                node_id=node.task_id,
                stage_name="execution",
                additional_data={
                    "llm_input_messages": [{"role": "user", "content": enhanced_query}],
                    "llm_input_length": len(enhanced_query)
                }
            )
            
            # Configure web search options based on search_context_size
            if self.use_openrouter:
                # OpenRouter uses the standard chat completions API with web_search_options
                web_search_options = {}
                if self.search_context_size and self.search_context_size != "standard":
                    web_search_options["search_context_size"] = self.search_context_size
                
                api_response = await self.client.chat.completions.create(
                    model=self.model_id,
                    web_search_options=web_search_options if web_search_options else None,
                    tool_choice={"type": "tool", "function": {"name": "web_search_preview"}},
                    messages=[
                        {
                            "role": "user",
                            "content": enhanced_query
                        }
                    ]
                )
            else:
                # Standard OpenAI API with responses.create
                # Build web_search_preview tool configuration
                web_search_tool = {"type": "web_search_preview"}
                if self.search_context_size and self.search_context_size != "standard":
                    web_search_tool["search_context_size"] = self.search_context_size
                
                api_response = await self.client.responses.create(
                    model=self.model_id,
                    tools=[web_search_tool],
                    tool_choice={"type": "web_search_preview"},  # Force use of web search tool
                    input=enhanced_query
                )

            # 1. Handle different response formats based on API type
            if self.use_openrouter:
                # OpenRouter returns standard chat completion format
                if hasattr(api_response, 'choices') and api_response.choices:
                    # CRITICAL FIX: Check that choices array has items and message exists
                    if len(api_response.choices) > 0 and hasattr(api_response.choices[0], 'message'):
                        if api_response.choices[0].message and hasattr(api_response.choices[0].message, 'content'):
                            raw_output = api_response.choices[0].message.content
                        else:
                            logger.error(f"    {self.adapter_name}: No message content in OpenRouter response")
                            raw_output = None
                    else:
                        logger.error(f"    {self.adapter_name}: Empty choices array or no message in OpenRouter response")
                        raw_output = None
                else:
                    logger.error(f"    {self.adapter_name}: No choices found in OpenRouter response")
                    raw_output = None
            else:
                # Standard OpenAI responses.create format
                if hasattr(api_response, 'output_text') and api_response.output_text:
                    raw_output = api_response.output_text
                else:
                    logger.error(f"    {self.adapter_name}: 'output_text' not found or empty in API response. Main output will be error message.")
                    raw_output = None
            
            # Post-process to extract just the retrieved data if it contains our prompt
            if raw_output:
                if "RETRIEVED DATA:" in raw_output:
                    # Extract everything after "RETRIEVED DATA:"
                    data_parts = raw_output.split("RETRIEVED DATA:", 1)
                    if len(data_parts) > 1:
                        output_text_with_citations = data_parts[1].strip()
                    else:
                        output_text_with_citations = raw_output
                else:
                    output_text_with_citations = raw_output
                    
                logger.success(f"    {self.adapter_name}: Retrieved 'output_text' (length: {len(output_text_with_citations)}).")
            else:
                # Keep the default error message for output_text_with_citations
                pass

            # 2. Attempt to parse nested text_content and annotations as supplementary info
            raw_annotations_data = []
            parsed_text_content = None
            try:
                if not self.use_openrouter and hasattr(api_response, 'output') and \
                   isinstance(api_response.output, list) and \
                   len(api_response.output) > 1 and \
                   hasattr(api_response.output[1], 'content') and \
                   isinstance(api_response.output[1].content, list) and \
                   len(api_response.output[1].content) > 0:
                    
                    content_item = api_response.output[1].content[0]
                    
                    if hasattr(content_item, 'text') and content_item.text:
                        parsed_text_content = content_item.text
                        logger.success(f"    {self.adapter_name}: Retrieved nested 'text_content' (length: {len(parsed_text_content)}).")
                    else:
                        logger.warning(f"    {self.adapter_name}: Nested 'text' attribute not found or empty.")

                    if hasattr(content_item, 'annotations') and isinstance(content_item.annotations, list):
                        temp_raw_annotations = []
                        for ann_obj in content_item.annotations:
                            ann_dict = {
                                'title': getattr(ann_obj, 'title', None),
                                'url': getattr(ann_obj, 'url', None),
                                'start_index': getattr(ann_obj, 'start_index', -1),
                                'end_index': getattr(ann_obj, 'end_index', -1),
                                'type': getattr(ann_obj, 'type', 'url_citation')
                            }
                            if ann_dict['url'] and ann_dict['start_index'] != -1 and ann_dict['end_index'] != -1:
                                temp_raw_annotations.append(ann_dict)
                            else:
                                logger.warning(f"    {self.adapter_name}: Skipping invalid nested annotation object: {ann_obj}")
                        
                        if temp_raw_annotations:
                            raw_annotations_data = temp_raw_annotations # Assign if we got valid annotations
                            logger.success(f"    {self.adapter_name}: Retrieved {len(raw_annotations_data)} nested 'annotations'.")
                    else:
                        logger.warning(f"    {self.adapter_name}: Nested 'annotations' attribute not found or not a list.")
                else:
                    logger.warning(f"    {self.adapter_name}: Nested API response structure 'output[1].content[0]' not found. No supplementary text/annotations.")
            except (AttributeError, IndexError, TypeError) as e:
                logger.warning(f"    {self.adapter_name}: Could not parse nested content from API response: {e}")

            for ann_data in raw_annotations_data:
                try:
                    parsed_annotations.append(AnnotationURLCitationModel(**ann_data))
                except Exception as e_pydantic:
                    logger.warning(f"    {self.adapter_name}: Error parsing an annotation dict: {ann_data}, Error: {e_pydantic}")

            # Wikipedia API fetching disabled for now
            # Simply return the output without Wikipedia enhancement
            
            # Return a simple dictionary with a consistent key schema
            clean_output = {
                "query_used": query,
                "output_text": output_text_with_citations,
                "citations": [ann.model_dump() for ann in parsed_annotations]  # Include citations for transparency
            }

            main_output_preview = clean_output["output_text"][:150] + "..." if len(clean_output["output_text"]) > 150 else clean_output["output_text"]
            logger.success(f"  Adapter '{self.adapter_name}': Processed. Main output: '{main_output_preview}', Annotations: {len(parsed_annotations)}")
            node.output_type_description = "custom_searcher_output"
            
            # FIXED: Complete tracing stage with rich output
            # Update the stage with both input and output data
            trace_manager.update_stage(
                node_id=node.task_id,
                stage_name="execution",
                llm_response=clean_output["output_text"],
                additional_data={
                    "llm_input_messages": [{"role": "user", "content": enhanced_query}],
                    "llm_input_length": len(enhanced_query),
                    "full_llm_output": output_text_with_citations,
                    "llm_output_length": len(output_text_with_citations),
                    "citations_count": len(parsed_annotations),
                    "raw_api_response_type": type(api_response).__name__
                }
            )
            
            # Don't complete the stage here - let the node handler do it
            # This prevents overwriting the input_context and other fields
            
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
            
            # Return a simple dictionary with the error
            return {
                "query_used": query,
                "output_text": f"API Call Failed: {e}"
            }


# --- Gemini Custom Searcher with Annotations (Adapter Version) ---
class GeminiCustomSearchAdapter(BaseAdapter):
    """
    A direct adapter that uses Google Gemini with Google Search tool to get answers with URL annotations.
    It does not use an underlying AgnoAgent.
    """
    adapter_name: str = "GeminiCustomSearchAdapter" 
    model_id: str = "gemini-2.5-flash" # As per your example, can be configured

    def __init__(self, gemini_client = None, model_id: str = "gemini-2.5-flash"):
        super().__init__(self.adapter_name)
        if genai is None:
            raise ImportError("google-genai module is not available. Please install 'google-genai'.")
        
        # Debug: Let's see what environment variables are actually set
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        logger.info(f"🔍 DEBUG: GOOGLE_API_KEY/GEMINI_API_KEY from os.getenv: {api_key[:10] if api_key else 'None'}...{api_key[-4:] if api_key and len(api_key) > 10 else ''}")
        
        # Also check if there are any other Google/Gemini-related env vars
        for key, value in os.environ.items():
            if "GOOGLE" in key.upper() or "GEMINI" in key.upper():
                logger.info(f"🔍 DEBUG: Found env var {key}: {value[:10] if value else 'None'}...{value[-4:] if value and len(value) > 10 else ''}")
        
        if not api_key:
            raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY environment variable is required for GeminiCustomSearchAdapter")
        
        # Create client with explicit API key - ensure we're creating a fresh client to avoid event loop issues
        try:
            self.client = gemini_client or genai.Client(api_key=api_key)
        except Exception as e:
            logger.error(f"Error creating Gemini client: {e}")
            raise
        
        self.model_id = model_id
        logger.info(f"Initialized {self.agent_name} with model: {self.model_id} (API key: {api_key[:10]}...{api_key[-4:]})")

    async def process(self, node: TaskNode, agent_task_input: AgentTaskInput, trace_manager: "TraceManager") -> Dict:
        """
        Processes the task by extracting the goal as a query, calling Gemini with
        google_search tool using client.aio.models.generate_content (async API).
        Parses response.text and grounding_metadata for citations.
        """
        # Import trace_manager here to avoid circular imports
        from sentientresearchagent.hierarchical_agent_framework.tracing.manager import TraceManager
        
        query = agent_task_input.current_goal
        logger.info(f"  Adapter '{self.adapter_name}': Processing node {node.task_id} (Query: '{query[:100]}...') with Gemini model {self.model_id}")
        
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
            model_info={"model": self.model_id, "provider": "google_gemini"}
        )
        
        output_text_with_citations = f"Error: Could not retrieve output_text for query: {query}" # Default error
        parsed_text_content: Optional[str] = None
        parsed_annotations: List[AnnotationURLCitationModel] = []

        try:
            # Build enhanced query with context
            context_section = ""
            context_emphasis = ""
            if agent_task_input.relevant_context_items:
                context_section = "\n\n[IMPORTANT CONTEXT FROM PREVIOUS TASKS - HIGHLY RELEVANT TO YOUR SEARCH]\n"
                context_section += "The following context contains crucial information that will help you search more effectively.\n"
                context_section += "PAY CLOSE ATTENTION as this context likely contains specific names, terms, or data you need to search for:\n"
                for ctx_item in agent_task_input.relevant_context_items:
                    context_section += f"\n[{ctx_item.content_type_description}]:\n{ctx_item.content}\n"
                
                # Add emphasis in guidelines
                context_emphasis = CONTEXT_EMPHASIS_SECTION
            
            # Expert searcher prompt for comprehensive data retrieval
            enhanced_query = f"""{OPENAI_CUSTOM_SEARCH_PROMPT}{context_emphasis}{context_section}

QUERY: {query}

RETRIEVED DATA:"""
            
            # Log the complete LLM input message
            logger.debug(f"Complete LLM input for {self.adapter_name}:\n{enhanced_query}")
            
            # Update trace with full LLM input
            trace_manager.update_stage(
                node_id=node.task_id,
                stage_name="execution",
                additional_data={
                    "llm_input_messages": [{"role": "user", "content": enhanced_query}],
                    "llm_input_length": len(enhanced_query)
                }
            )
            
            # Call Gemini API with Google Search tool using ASYNC API
            # Add better error handling for event loop issues and rate limiting
            max_retries = 3
            base_delay = 5.0
            
            for attempt in range(max_retries):
                try:
                    api_response = await self.client.aio.models.generate_content(
                        model=self.model_id,
                        contents=enhanced_query,
                        config={"tools": [{"google_search": {}}]},
                    )
                    break  # Success, exit retry loop
                
                except RuntimeError as e:
                    if "event loop" in str(e).lower():
                        # Event loop issue - try recreating the client
                        logger.warning(f"Event loop issue detected, recreating client: {e}")
                        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
                        self.client = genai.Client(api_key=api_key)
                        # Retry with new client
                        continue
                    else:
                        raise
                
                except Exception as e:
                    error_str = str(e).lower()
                    
                    # Handle rate limiting errors
                    if any(keyword in error_str for keyword in ['rate limit', '429', 'quota', 'throttle', 'exceeded']):
                        if attempt < max_retries - 1:
                            # Exponential backoff for rate limiting
                            delay = base_delay * (2 ** attempt) + (attempt * 10)  # Extra delay for rate limits
                            logger.warning(f"Rate limit hit (attempt {attempt + 1}/{max_retries}), retrying in {delay:.1f}s: {e}")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            logger.error(f"Rate limit exceeded after {max_retries} attempts: {e}")
                            raise
                    
                    # Handle other API errors with shorter retry
                    elif any(keyword in error_str for keyword in ['timeout', 'connection', 'network', 'internal error']):
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(f"API error (attempt {attempt + 1}/{max_retries}), retrying in {delay:.1f}s: {e}")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            logger.error(f"API error after {max_retries} attempts: {e}")
                            raise
                    
                    # For other errors, don't retry
                    else:
                        raise

            # Check if api_response is None or has unexpected structure
            if api_response is None:
                logger.error(f"    {self.adapter_name}: API response is None")
                raise ValueError("API response is None")

            # 1. Get the main response text
            if hasattr(api_response, 'text') and api_response.text:
                raw_output = api_response.text
                
                # Post-process to extract just the retrieved data if it contains our prompt
                if "RETRIEVED DATA:" in raw_output:
                    # Extract everything after "RETRIEVED DATA:"
                    data_parts = raw_output.split("RETRIEVED DATA:", 1)
                    if len(data_parts) > 1:
                        output_text_with_citations = data_parts[1].strip()
                    else:
                        output_text_with_citations = raw_output
                else:
                    output_text_with_citations = raw_output
                
                parsed_text_content = output_text_with_citations  # Same content for both fields
                logger.success(f"    {self.adapter_name}: Retrieved response text (length: {len(output_text_with_citations)}).")
            else:
                logger.error(f"    {self.adapter_name}: 'text' not found or empty in API response. Main output will be error message.")
                logger.debug(f"    {self.adapter_name}: API response attributes: {dir(api_response) if api_response else 'None'}")
                # Keep the default error message for output_text_with_citations

            # 2. Parse grounding metadata for citations
            raw_annotations_data = []
            # Add more robust null checking to prevent NoneType iteration errors
            if (hasattr(api_response, 'candidates') and 
                api_response.candidates is not None and 
                isinstance(api_response.candidates, (list, tuple)) and
                len(api_response.candidates) > 0 and
                hasattr(api_response.candidates[0], 'grounding_metadata') and
                api_response.candidates[0].grounding_metadata is not None and
                hasattr(api_response.candidates[0].grounding_metadata, 'grounding_chunks') and
                api_response.candidates[0].grounding_metadata.grounding_chunks is not None):
                
                grounding_chunks = api_response.candidates[0].grounding_metadata.grounding_chunks
                
                # Additional safety check for grounding_chunks
                if isinstance(grounding_chunks, (list, tuple)):
                    for i, chunk in enumerate(grounding_chunks):
                        if hasattr(chunk, 'web') and chunk.web:
                            web_info = chunk.web
                            ann_dict = {
                                'title': getattr(web_info, 'title', f"Source {i+1}"),
                                'url': getattr(web_info, 'uri', None),
                                'start_index': 0,  # Gemini doesn't provide exact indices, so we'll use defaults
                                'end_index': len(output_text_with_citations) if output_text_with_citations else 0,
                                'type': 'url_citation'
                            }
                            
                            if ann_dict['url']:
                                raw_annotations_data.append(ann_dict)
                            else:
                                logger.warning(f"    {self.adapter_name}: Skipping grounding chunk without URL: {chunk}")
                else:
                    logger.warning(f"    {self.adapter_name}: grounding_chunks is not iterable: {type(grounding_chunks)}")
                
                if raw_annotations_data:
                    logger.success(f"    {self.adapter_name}: Retrieved {len(raw_annotations_data)} grounding citations.")
            else:
                logger.warning(f"    {self.adapter_name}: No grounding metadata found in API response.")

            # Convert to AnnotationURLCitationModel objects
            for ann_data in raw_annotations_data:
                try:
                    parsed_annotations.append(AnnotationURLCitationModel(**ann_data))
                except Exception as e_pydantic:
                    logger.warning(f"    {self.adapter_name}: Error parsing an annotation dict: {ann_data}, Error: {e_pydantic}")

            # Check for Wikipedia URLs in citations and enhance output
            wikipedia_contents = []
            if parsed_annotations:
                for ann in parsed_annotations:
                    if ann.url and 'wikipedia.org' in ann.url.lower():
                        logger.info(f"    {self.adapter_name}: Found Wikipedia citation: {ann.url}")
                        wiki_content = await fetch_wikipedia_content(ann.url)
                        if wiki_content:
                            wikipedia_contents.append(wiki_content)
                            logger.success(f"    {self.adapter_name}: Successfully fetched Wikipedia content for: {ann.title or ann.url}")
            
            # Enhance output with Wikipedia content if available
            enhanced_output_text = output_text_with_citations
            if wikipedia_contents:
                enhanced_output_text += "\n\n--- Additional Wikipedia Content ---\n\n"
                enhanced_output_text += "\n\n".join(wikipedia_contents)
                logger.info(f"    {self.adapter_name}: Enhanced output with {len(wikipedia_contents)} Wikipedia article(s)")
            
            # Return a simple dictionary with a consistent key schema
            clean_output = {
                "query_used": query,
                "output_text": enhanced_output_text,
                "citations": [ann.model_dump() for ann in parsed_annotations]  # Include citations for transparency
            }
            
            main_output_preview = clean_output["output_text"][:150] + "..." if len(clean_output["output_text"]) > 150 else clean_output["output_text"]
            logger.success(f"  Adapter '{self.adapter_name}': Processed. Main output: '{main_output_preview}', Citations processed: {len(parsed_annotations)}")
            node.output_type_description = "custom_searcher_output"
            
            # FIXED: Complete tracing stage with rich output
            trace_manager.update_stage(
                node_id=node.task_id,
                stage_name="execution",
                llm_response=clean_output["output_text"],
                additional_data={
                    "llm_input_messages": [{"role": "user", "content": enhanced_query}],
                    "llm_input_length": len(enhanced_query),
                    "full_llm_output": output_text_with_citations,
                    "llm_output_length": len(output_text_with_citations),
                    "enhanced_output_length": len(enhanced_output_text),
                    "citations_count": len(parsed_annotations),
                    "wikipedia_additions": len(wikipedia_contents),
                    "raw_api_response_type": type(api_response).__name__
                }
            )
            
            # Don't complete the stage here - let the node handler do it
            # This prevents overwriting the input_context and other fields
            
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
            
            # Return a simple dictionary with the error
            return {
                "query_used": query,
                "output_text": f"API Call Failed: {e}"
            }

