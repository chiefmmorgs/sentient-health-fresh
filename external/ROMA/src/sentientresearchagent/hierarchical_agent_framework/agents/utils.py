from typing import Any, Optional, Type, TypeVar, List, Dict
from loguru import logger
import json
import re
import asyncio
from dataclasses import dataclass
from json_repair import repair_json
import litellm
from pydantic import BaseModel, Field

# Import the agent instance
from .definitions.utility_agents import context_summarizer_agno_agent

T = TypeVar('T')

MAX_SUMMARY_LENGTH_FALLBACK_CHARS = 140000  # ~20000 words * 7 chars/word average
TARGET_WORD_COUNT_FOR_CTX_SUMMARIES = 20000  # Only summarize if content exceeds 20k words

def get_context_summary(content: Any, target_word_count: int = TARGET_WORD_COUNT_FOR_CTX_SUMMARIES) -> str:
    if not content:
        return ""

    content_str = ""
    if isinstance(content, str):
        content_str = content
    elif hasattr(content, 'model_dump_json'): # Pydantic model
        content_str = content.model_dump_json(indent=None) # Compact JSON
    else:
        content_str = str(content)

    if not content_str.strip():
        return ""

    # Simple pre-check: if already short enough (based on words) and is plain string.
    # For JSON Pydantic dumps, we might still want to summarize.
    current_word_count = len(content_str.split())
    if isinstance(content, str) and current_word_count < target_word_count:
        # If it's already a string and shorter than the target, return as is.
        # No need to check char length here as it's already short.
        return content_str

    # If summarizer agent failed to initialize, fall back to truncation.
    if context_summarizer_agno_agent is None:
        logger.warning("ContextSummarizer_Agno not available, falling back to truncation for content.")
        return content_str[:MAX_SUMMARY_LENGTH_FALLBACK_CHARS] + ("..." if len(content_str) > MAX_SUMMARY_LENGTH_FALLBACK_CHARS else "")

    logger.debug(f"ContextSummarizer: Requesting summary for content (type: {type(content)}, first 100 chars): '{content_str[:100]}...'")
    try:
        # The AgnoAgent's system prompt already has word count guidance.
        # The input to .run() is the main content to be processed.
        response = context_summarizer_agno_agent.run(content_str)

        summary = response.content if response and response.content else ""

        if not summary.strip():
            logger.warning("ContextSummarizer: Agent returned empty or whitespace summary. Falling back to truncation.")
            return content_str[:MAX_SUMMARY_LENGTH_FALLBACK_CHARS] + ("..." if len(content_str) > MAX_SUMMARY_LENGTH_FALLBACK_CHARS else "")

        # Optional: Post-process to remove common LLM conversational artifacts if any slip through
        summary = summary.strip() # Remove leading/trailing whitespace
        # Example: if LLMs sometimes add "Summary: " or "Here's the summary: "
        common_prefixes_to_remove = ["Summary: ", "Here's the summary: ", "Here is the summary: "]
        for prefix in common_prefixes_to_remove:
            if summary.lower().startswith(prefix.lower()):
                summary = summary[len(prefix):]
                break
        
        summary = summary.strip() # Re-strip after potential prefix removal

        logger.info(f"ContextSummarizer: Generated summary (length {len(summary)}): '{summary[:100]}...'")

        # Enforce hard character limit if LLM summary is too verbose, even after word count instruction.
        if len(summary) > MAX_SUMMARY_LENGTH_FALLBACK_CHARS * 1.2: # Allow some leeway
             logger.warning(f"ContextSummarizer: LLM summary exceeded fallback char limit ({len(summary)} > {MAX_SUMMARY_LENGTH_FALLBACK_CHARS * 1.2}). Truncating.")
             summary = summary[:MAX_SUMMARY_LENGTH_FALLBACK_CHARS] + "..."
        return summary

    except Exception as e:
        logger.error(f"ContextSummarizer: Error during summarization: {e}. Falling back to truncation.")
        return content_str[:MAX_SUMMARY_LENGTH_FALLBACK_CHARS] + ("..." if len(content_str) > MAX_SUMMARY_LENGTH_FALLBACK_CHARS else "")


class JsonFixingResponse(BaseModel):
    """Pydantic model for structured LLM JSON fixing responses."""
    rationale: str = Field(
        description="Detailed explanation of what was wrong with the original JSON and how you fixed it"
    )
    fixed_json: str = Field(
        description="The corrected JSON string that should be valid and parseable"
    )


@dataclass
class FixingAttempt:
    """Tracks a single JSON fixing attempt with context."""
    attempt_number: int
    malformed_input: str
    llm_response: Optional[JsonFixingResponse]
    error_message: str
    success: bool = False
    rationale: Optional[str] = None


class OutputFixingParser:
    """
    Comprehensive output parser with progressive fixing strategies inspired by LangChain's OutputFixingParser.
    
    Parsing strategies (applied in order):
    1. Direct parsing (with json_repair fallback)
    2. Markdown code block extraction (with json_repair fallback)
    3. Bracket detection (with json_repair fallback)  
    4. JSONDecoder (with json_repair fallback)
    5. LLM-based fixing with structured output and rationale (optional)
    """
    
    # Detailed system prompt as class variable
    SYSTEM_PROMPT = """You are an expert JSON repair specialist with deep understanding of JSON syntax and structure.

YOUR EXPERTISE:
- JSON syntax rules: proper quoting, bracket matching, comma placement
- Common AI model output issues: trailing commas, unquoted keys, malformed strings
- Data preservation: maintaining original intent and structure while fixing syntax
- Schema compliance: ensuring output matches expected Pydantic model structure

YOUR TASK:
- Analyze malformed JSON and identify specific syntax/structure issues
- Fix the JSON while preserving ALL original data and intent
- Provide detailed rationale explaining your diagnostic process and fixes
- Return valid JSON that will successfully parse into the target Pydantic model

FIXING PRINCIPLES:
1. Preserve original data: Never add, remove, or modify data values unless absolutely necessary
2. Fix syntax only: Focus on quotes, brackets, commas, and structural issues
3. Maintain structure: Keep the same object/array hierarchy as intended
4. Handle edge cases: Deal with escaped characters, nested objects, mixed data types
5. Learn from context: Use previous attempt failures to avoid repeating mistakes

OUTPUT REQUIREMENTS:
- rationale: Detailed analysis of problems found and specific fixes applied
- fixed_json: Clean, valid JSON string ready for parsing

You are methodical, precise, and focused on preserving the original intent of the malformed JSON."""

    def __init__(self, model_id: str = "openrouter/google/gemini-2.5-flash", 
                 max_llm_retries: int = 3, 
                 max_previous_attempts_in_context: int = 2):
        """
        Initialize the output fixing parser.
        
        Args:
            model_id: LiteLLM model identifier for JSON fixing
            max_llm_retries: Maximum number of LLM fixing attempts
            max_previous_attempts_in_context: How many previous failed attempts to include in context
        """
        self.model_id = model_id
        self.max_llm_retries = max_llm_retries
        self.max_previous_attempts_in_context = max_previous_attempts_in_context
    
    async def parse(self, text: str, response_model: Type[T], use_llm_fixing: bool = True, 
                   original_error: Optional[str] = None) -> Optional[T]:
        """Unified parsing method that applies all fixing strategies progressively."""
        logger.debug(f"Starting output parsing for {response_model.__name__} (text length: {len(text)})")
        
        # Strategy 1: Direct parsing (with json_repair fallback)
        result = self._try_parse_and_repair(text, response_model)
        if result:
            logger.debug("✅ Strategy 1: Direct parsing successful")
            return result
        
        # Strategy 2: Markdown code block extraction
        result = self._try_markdown_extraction(text, response_model)
        if result:
            logger.debug("✅ Strategy 2: Markdown extraction successful")
            return result
            
        # Strategy 3: Bracket detection
        result = self._try_bracket_detection(text, response_model)
        if result:
            logger.debug("✅ Strategy 3: Bracket detection successful")
            return result
            
        # Strategy 4: JSONDecoder
        result = self._try_json_decoder(text, response_model)
        if result:
            logger.debug("✅ Strategy 4: JSONDecoder successful")
            return result
            
        # Strategy 5: LLM-based fixing (optional)
        if use_llm_fixing:
            logger.info("Attempting LLM-based JSON fixing as last resort...")
            result = await self._try_llm_fixing(text, response_model, original_error or "Unknown parsing error")
            if result:
                logger.debug("✅ Strategy 5: LLM-based fixing successful")
                return result
        
        logger.error(f"❌ All parsing strategies failed for {response_model.__name__}")
        return None
    
    def _try_parse_and_repair(self, json_str: str, response_model: Type[T]) -> Optional[T]:
        """Try direct parsing, then json_repair as automatic fallback."""
        try:
            return response_model.model_validate_json(json_str)
        except Exception:
            try:
                repaired = repair_json(json_str)
                return response_model.model_validate_json(repaired)
            except Exception:
                return None
    
    def _try_markdown_extraction(self, text: str, response_model: Type[T]) -> Optional[T]:
        """Extract JSON from markdown code blocks."""
        match = re.search(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", text, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            return self._try_parse_and_repair(json_str, response_model)
        return None
    
    def _try_bracket_detection(self, text: str, response_model: Type[T]) -> Optional[T]:
        """Extract JSON using bracket detection from first to last bracket."""
        first_bracket = min(
            (text.find('{') if text.find('{') != -1 else float('inf')),
            (text.find('[') if text.find('[') != -1 else float('inf'))
        )
        if first_bracket != float('inf'):
            last_bracket = max(text.rfind('}'), text.rfind(']'))
            if last_bracket > first_bracket:
                json_str = text[first_bracket:last_bracket+1].strip()
                return self._try_parse_and_repair(json_str, response_model)
        return None
    
    def _try_json_decoder(self, text: str, response_model: Type[T]) -> Optional[T]:
        """Use JSONDecoder to find first valid JSON object."""
        try:
            obj, _ = json.JSONDecoder().raw_decode(text.strip())
            json_str = json.dumps(obj)
            return self._try_parse_and_repair(json_str, response_model)
        except Exception:
            return None
    
    async def _try_llm_fixing(self, malformed_text: str, response_model: Type[T], original_error: str) -> Optional[T]:
        """LLM-based fixing with structured output and progressive retries."""
        attempts: List[FixingAttempt] = []
        
        for attempt_num in range(1, self.max_llm_retries + 1):
            logger.info(f"LLM fixing attempt {attempt_num}/{self.max_llm_retries}")
            
            try:
                user_prompt = self._build_user_prompt(malformed_text, original_error, response_model, attempts, attempt_num)
                fixing_response = await self._call_litellm_structured(user_prompt)
                
                if not fixing_response or not fixing_response.fixed_json:
                    error_msg = "LiteLLM returned empty or invalid structured response"
                    attempts.append(FixingAttempt(
                        attempt_number=attempt_num,
                        malformed_input=malformed_text[:200] + "..." if len(malformed_text) > 200 else malformed_text,
                        llm_response=fixing_response,
                        error_message=error_msg
                    ))
                    continue
                
                logger.info(f"LLM Rationale (attempt {attempt_num}): {fixing_response.rationale}")
                
                # Parse LLM-fixed JSON without LLM fixing to avoid recursion
                parsed_result = await self.parse(fixing_response.fixed_json, response_model, use_llm_fixing=False)
                
                if parsed_result:
                    logger.info(f"✅ LLM JSON fixing successful! Rationale: {fixing_response.rationale}")
                    attempts.append(FixingAttempt(
                        attempt_number=attempt_num,
                        malformed_input=malformed_text[:200] + "..." if len(malformed_text) > 200 else malformed_text,
                        llm_response=fixing_response,
                        error_message="Success",
                        success=True,
                        rationale=fixing_response.rationale
                    ))
                    return parsed_result
                else:
                    error_msg = "Fixed JSON still failed to parse with all non-LLM strategies"
                    attempts.append(FixingAttempt(
                        attempt_number=attempt_num,
                        malformed_input=malformed_text[:200] + "..." if len(malformed_text) > 200 else malformed_text,
                        llm_response=fixing_response,
                        error_message=error_msg,
                        rationale=fixing_response.rationale
                    ))
                    
            except Exception as e:
                attempts.append(FixingAttempt(
                    attempt_number=attempt_num,
                    malformed_input=malformed_text[:200] + "..." if len(malformed_text) > 200 else malformed_text,
                    llm_response=None,
                    error_message=f"Exception during attempt: {str(e)}"
                ))
                
                if attempt_num < self.max_llm_retries:
                    await asyncio.sleep(1.0 * attempt_num)
        
        logger.error(f"❌ LLM JSON fixing failed after {self.max_llm_retries} attempts")
        self._log_detailed_failure_summary(attempts)
        return None
    
    def _build_user_prompt(self, malformed_text: str, original_error: str, response_model: Type[T],
                          previous_attempts: List[FixingAttempt], attempt_number: int) -> str:
        """Build comprehensive user prompt with configurable previous attempt history."""
        
        prompt_parts = [
            f"TASK: Fix this malformed JSON to match the {response_model.__name__} Pydantic model structure.",
            "",
            "MALFORMED JSON INPUT:",
            "```json",
            malformed_text,
            "```",
            "",
            f"ORIGINAL PARSING ERROR: {original_error}",
            ""
        ]
        
        # Add context from previous attempts (configurable number)
        if previous_attempts:
            relevant_attempts = previous_attempts[-self.max_previous_attempts_in_context:]
            
            prompt_parts.extend([
                f"CONTEXT - PREVIOUS FAILED ATTEMPTS (this is attempt #{attempt_number}):",
                f"Showing last {len(relevant_attempts)} attempts for context:",
                ""
            ])
            
            for attempt in relevant_attempts:
                prompt_parts.extend([
                    f"❌ FAILED Attempt {attempt.attempt_number}:",
                    f"   Rationale: {attempt.rationale or 'No rationale provided'}",
                    ""
                ])
                
                # Include the actual LLM output that failed
                if attempt.llm_response and attempt.llm_response.fixed_json:
                    llm_output = attempt.llm_response.fixed_json
                    if len(llm_output) > 300:
                        llm_output = llm_output[:300] + "... [truncated]"
                    
                    prompt_parts.extend([
                        f"   LLM Output that failed:",
                        f"   ```json",
                        f"   {llm_output}",
                        f"   ```",
                        ""
                    ])
                else:
                    prompt_parts.append("   LLM Output: None (call failed)")
                    prompt_parts.append("")
                
                prompt_parts.extend([
                    f"   Final Error: {attempt.error_message}",
                    ""
                ])
            
            prompt_parts.extend([
                "CRITICAL: Learn from the failed attempts above!",
                "- Analyze why each previous approach failed",
                "- Try a fundamentally different fixing strategy",  
                "- Focus on the specific parsing errors that occurred",
                "- Your rationale should explain why your approach differs from previous attempts",
                ""
            ])
        
        prompt_parts.extend([
            "RESPONSE REQUIREMENTS:",
            "- Provide detailed rationale explaining what you found wrong and how you fixed it",
            "- Return corrected JSON that will successfully parse",
            "- Preserve ALL original data values and structure intent"
        ])
            
        return "\n".join(prompt_parts)
    
    async def _call_litellm_structured(self, user_prompt: str) -> Optional[JsonFixingResponse]:
        """Make structured LiteLLM call with detailed system prompt."""
        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await litellm.acompletion(
                model=self.model_id,
                messages=messages,
                max_tokens=4000,
                temperature=0.1,
                response_format=JsonFixingResponse
            )
            
            content = response.choices[0].message.content
            return JsonFixingResponse.model_validate_json(content) if content else None
            
        except Exception as e:
            logger.error(f"LiteLLM structured call failed: {e}")
            return None
    
    def _log_detailed_failure_summary(self, attempts: List[FixingAttempt]) -> None:
        """Log comprehensive failure summary with all attempt details."""
        logger.debug("=== COMPREHENSIVE LLM JSON FIXING FAILURE SUMMARY ===")
        for attempt in attempts:
            logger.debug(f"--- Attempt {attempt.attempt_number} ---")
            logger.debug(f"Error: {attempt.error_message}")
            if attempt.rationale:
                logger.debug(f"Rationale: {attempt.rationale}")
            if attempt.llm_response and attempt.llm_response.fixed_json:
                logger.debug(f"LLM Output: {attempt.llm_response.fixed_json[:200]}...")
            logger.debug("")
        logger.debug("===================================================")


# Global parser instance with configurable settings
_global_output_parser: Optional[OutputFixingParser] = None

def get_global_output_parser(max_previous_attempts_in_context: int = 2) -> OutputFixingParser:
    """Get or create the global output fixing parser instance with configurable context."""
    global _global_output_parser
    if _global_output_parser is None:
        _global_output_parser = OutputFixingParser(
            max_previous_attempts_in_context=max_previous_attempts_in_context
        )
    return _global_output_parser
