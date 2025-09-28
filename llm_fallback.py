"""
LLM Provider Fallback System

Handles automatic failover between different LLM providers when quota/credits are exhausted.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from litellm import completion
import time

# Configure logging to avoid the "Level 'PLAN' already exists" error
logger = logging.getLogger(__name__)

class LLMFallback:
    """
    Handles automatic fallback between multiple LLM providers
    """
    
    def __init__(self):
        self.providers = self._initialize_providers()
        self.current_provider_index = 0
        self.last_successful_provider = None
        
    def _initialize_providers(self) -> List[Dict[str, Any]]:
        """Initialize available LLM providers based on environment variables"""
        providers = []
        
        # OpenRouter (cheapest, try first)
        if os.getenv("OPENROUTER_API_KEY"):
            providers.append({
                "name": "openrouter",
                "model": "openrouter/google/gemini-2-flash-exp",  # Very cheap
                "api_key": os.getenv("OPENROUTER_API_KEY"),
                "base_url": "https://openrouter.ai/api/v1",
                "cost_per_1k": 0.0001  # Very low cost
            })
            providers.append({
                "name": "openrouter_premium",
                "model": "openrouter/anthropic/claude-3.5-sonnet",
                "api_key": os.getenv("OPENROUTER_API_KEY"), 
                "base_url": "https://openrouter.ai/api/v1",
                "cost_per_1k": 0.003
            })
        
        # OpenAI (if available)
        if os.getenv("OPENAI_API_KEY"):
            providers.append({
                "name": "openai",
                "model": "gpt-3.5-turbo",
                "api_key": os.getenv("OPENAI_API_KEY"),
                "base_url": None,
                "cost_per_1k": 0.0015
            })
            providers.append({
                "name": "openai_premium", 
                "model": "gpt-4o-mini",
                "api_key": os.getenv("OPENAI_API_KEY"),
                "base_url": None,
                "cost_per_1k": 0.00015
            })
        
        # Anthropic (if available)
        if os.getenv("ANTHROPIC_API_KEY"):
            providers.append({
                "name": "anthropic",
                "model": "claude-3-haiku-20240307",
                "api_key": os.getenv("ANTHROPIC_API_KEY"),
                "base_url": None,
                "cost_per_1k": 0.00025
            })
        
        # Local/free options (if configured)
        if os.getenv("LOCAL_MODEL_URL"):
            providers.append({
                "name": "local",
                "model": "local/llama-7b",
                "api_key": "none",
                "base_url": os.getenv("LOCAL_MODEL_URL"),
                "cost_per_1k": 0.0
            })
        
        logger.info(f"Initialized {len(providers)} LLM providers")
        return providers
    
    def call_with_fallback(self, messages: List[Dict], **kwargs) -> Optional[Dict[str, Any]]:
        """
        Call LLM with automatic provider fallback
        
        Tries providers in order until one succeeds
        """
        if not self.providers:
            raise Exception("No LLM providers configured")
        
        last_error = None
        
        # Try each provider
        for i, provider in enumerate(self.providers):
            try:
                logger.info(f"Trying provider {provider['name']} (model: {provider['model']})")
                
                # Prepare call parameters
                call_params = {
                    "model": provider["model"],
                    "messages": messages,
                    "api_key": provider["api_key"],
                    **kwargs
                }
                
                if provider["base_url"]:
                    call_params["base_url"] = provider["base_url"]
                
                # Make the call
                start_time = time.time()
                response = completion(**call_params)
                call_time = time.time() - start_time
                
                # Success! 
                self.last_successful_provider = provider["name"]
                logger.info(f"✅ Success with {provider['name']} in {call_time:.2f}s")
                
                return response
                
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"❌ Provider {provider['name']} failed: {error_msg}")
                last_error = e
                
                # Check for specific quota/credit errors
                if any(keyword in error_msg.lower() for keyword in [
                    "quota", "rate limit", "insufficient", "credits", "billing", "exceeded"
                ]):
                    logger.info(f"🔄 {provider['name']} quota exhausted, trying next provider...")
                    continue
                    
                # For other errors, try next provider after short delay
                time.sleep(1)
                continue
        
        # All providers failed
        logger.error("❌ All LLM providers failed!")
        raise Exception(f"All LLM providers failed. Last error: {last_error}")
    
    def simple_completion(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        """
        Simple text completion with fallback
        
        Returns just the text content, not the full response object
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.call_with_fallback(messages, **kwargs)
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Simple completion failed: {e}")
            return f"Error: LLM completion failed - {str(e)}"
    
    def get_status(self) -> Dict[str, Any]:
        """Get fallback system status"""
        return {
            "providers_configured": len(self.providers),
            "provider_names": [p["name"] for p in self.providers],
            "last_successful": self.last_successful_provider,
            "current_provider": self.providers[self.current_provider_index]["name"] if self.providers else None
        }

# Global instance for easy access
fallback_llm = LLMFallback()

# Convenience functions
def call_llm_with_fallback(prompt: str, system_prompt: str = "", **kwargs) -> str:
    """Global function for easy LLM calling with fallback"""
    return fallback_llm.simple_completion(prompt, system_prompt, **kwargs)

def get_fallback_status() -> Dict[str, Any]:
    """Get fallback system status"""
    return fallback_llm.get_status()
