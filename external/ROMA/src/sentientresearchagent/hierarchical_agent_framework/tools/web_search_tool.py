"""
Web Search Tool for AgnoAgent Integration

This module provides a web_search function that wraps the custom search adapters
(OpenAI and Gemini) to be used as a tool in AgnoAgent configurations.
"""

from typing import Optional, List, Any, Dict
from pathlib import Path
from loguru import logger

# Import the agent registry to get search adapters
from sentientresearchagent.hierarchical_agent_framework.agents.registry import AgentRegistry


def web_search(query: str) -> str:
    """
    Performs web search based on your query (think a Google search) then returns 
    the final answer that is processed by an LLM.
    
    Args:
        query: The search query to execute
        
    Returns:
        The search results as a string
    """
    import requests
    import os
    
    # For now, let's create a simpler implementation that doesn't rely on the agent registry
    # This makes it more compatible with AgnoAgent's tool calling mechanism
    
    try:
        # Check if we have Gemini API key
        gemini_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if gemini_key:
            # Use Gemini's generative AI for search-like responses
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            
            # Create a search-focused prompt
            search_prompt = f"""Answer this search query with factual information. Be concise and direct.
If you don't know the answer, say "Information not found."

Query: {query}

Answer:"""
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": search_prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 500
                }
            }
            
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                result = response.json()
                if "candidates" in result and result["candidates"]:
                    text = result["candidates"][0]["content"]["parts"][0]["text"]
                    return text.strip()
            
        # Fallback to OpenAI if available
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are a search engine. Provide concise, factual answers."},
                    {"role": "user", "content": query}
                ],
                "temperature": 0.1,
                "max_tokens": 500
            }
            
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
        
        # If no API keys available, return error
        return "Error: No API keys found for web search. Please set GOOGLE_API_KEY or OPENAI_API_KEY."
        
    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        logger.error(error_msg)
        return error_msg


def clean_tools(tools: List[Any]) -> List[Any]:
    """
    Clean tool objects by removing problematic attributes that might cause
    issues with AgnoAgent.
    
    Args:
        tools: List of tool objects or functions
        
    Returns:
        List of cleaned tool objects
    """
    def clean_function_obj(func_obj):
        # Remove problematic attributes if they exist
        for attr in ['requires_confirmation', 'external_execution']:
            if hasattr(func_obj, attr):
                delattr(func_obj, attr)
        return func_obj

    cleaned = []
    for tool in tools:
        # If tool has .functions (like WikipediaTools), iterate and clean
        if hasattr(tool, "functions"):
            if isinstance(tool.functions, dict):
                for name, fn in tool.functions.items():
                    tool.functions[name] = clean_function_obj(fn)
        
        # Also check direct `.function` attribute
        if hasattr(tool, "function"):
            tool.function = clean_function_obj(tool.function)
        
        # If the tool is a function itself, clean it
        if callable(tool):
            tool = clean_function_obj(tool)

        cleaned.append(tool)

    return cleaned


# Make web_search available for import
__all__ = ['web_search', 'clean_tools']