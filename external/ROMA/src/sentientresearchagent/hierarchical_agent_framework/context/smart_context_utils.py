from typing import Any, Optional
from loguru import logger
from ..agents.definitions.utility_agents import context_summarizer_agno_agent

# New intelligent thresholds - INCREASED LIMITS
FULL_CONTENT_WORD_LIMIT = 20000      # Increased from 5000
FULL_CONTENT_CHAR_LIMIT = 150000     # 20000 words * 7.5 chars/word average
DETAILED_SUMMARY_TARGET_WORDS = 10000  # Increased from 1250 - for when we do need to summarize
MAX_DETAILED_SUMMARY_CHARS = 150000   # 20000 words * 7.5 chars/word average

def get_smart_child_context(
    content: Any, 
    child_task_goal: str,
    child_task_type: str,
    force_detailed_summary: bool = False
) -> tuple[str, str]:
    """
    Smart context sizing for child->parent flow.
    
    Returns:
        tuple[content_text, processing_method]
        - content_text: The actual content to pass up
        - processing_method: Description of how it was processed ("full", "detailed_summary")
    """
    if not content:
        return "", "empty"
    
    # Convert to string
    content_str = ""
    if isinstance(content, str):
        content_str = content
    elif hasattr(content, 'model_dump_json'):
        content_str = content.model_dump_json(indent=2)  # Pretty JSON for readability
    else:
        content_str = str(content)
    
    if not content_str.strip():
        return "", "empty"
    
    # Calculate size metrics
    char_count = len(content_str)
    word_count = len(content_str.split())
    
    logger.debug(f"Smart context sizing: {word_count} words, {char_count} chars for {child_task_goal[:50]}...")
    
    # Decision logic: Include full content unless exceedingly long
    if not force_detailed_summary and word_count <= FULL_CONTENT_WORD_LIMIT and char_count <= FULL_CONTENT_CHAR_LIMIT:
        logger.info(f"Including FULL child content ({word_count} words, {char_count} chars)")
        return content_str, "full"
    
    # Content is exceedingly long - create detailed summary
    logger.info(f"Creating DETAILED summary for long content ({word_count} words, {char_count} chars)")
    return get_detailed_summary(content_str, child_task_goal, child_task_type), "detailed_summary"


def get_detailed_summary(content_str: str, task_goal: str, task_type: str) -> str:
    """Create a detailed, comprehensive summary preserving key information."""
    
    if context_summarizer_agno_agent is None:
        logger.warning("ContextSummarizer not available, using intelligent truncation")
        return _intelligent_truncation(content_str)
    
    # Enhanced prompt for detailed summarization
    detailed_prompt = f"""Task Goal: {task_goal}
Task Type: {task_type}

Content to Summarize:
{content_str}

Create a comprehensive, detailed summary that preserves:
1. All key findings, conclusions, and insights
2. Important data points, numbers, and statistics
3. Main arguments and reasoning
4. Critical details needed for parent task synthesis
5. Any constraints, recommendations, or next steps identified

Target length: {DETAILED_SUMMARY_TARGET_WORDS} words. Be thorough and preserve nuance.
Do not include conversational elements - provide only the detailed summary content."""

    try:
        response = context_summarizer_agno_agent.run(detailed_prompt)
        summary = response.content if response and response.content else ""
        
        if not summary.strip():
            logger.warning("Detailed summarizer returned empty content, using intelligent truncation")
            return _intelligent_truncation(content_str)
        
        # Clean up the response
        summary = summary.strip()
        
        # Enforce reasonable limits while preserving detail
        if len(summary) > MAX_DETAILED_SUMMARY_CHARS:
            logger.warning(f"Detailed summary too long ({len(summary)} chars), truncating")
            summary = summary[:MAX_DETAILED_SUMMARY_CHARS] + "..."
        
        logger.info(f"Generated detailed summary: {len(summary)} chars, {len(summary.split())} words")
        return summary
        
    except Exception as e:
        logger.error(f"Error creating detailed summary: {e}")
        return _intelligent_truncation(content_str)


def _intelligent_truncation(content_str: str) -> str:
    """Fallback: Truncate intelligently by preserving structure."""
    
    # Try to preserve structure by truncating at paragraph boundaries
    lines = content_str.split('\n')
    truncated_lines = []
    char_count = 0
    
    for line in lines:
        if char_count + len(line) + 1 > MAX_DETAILED_SUMMARY_CHARS * 0.8:  # Leave room for truncation notice
            break
        truncated_lines.append(line)
        char_count += len(line) + 1
    
    truncated = '\n'.join(truncated_lines)
    if char_count < len(content_str):
        truncated += f"\n\n... [Content truncated from {len(content_str)} to {len(truncated)} chars for context limits]"
    
    return truncated 