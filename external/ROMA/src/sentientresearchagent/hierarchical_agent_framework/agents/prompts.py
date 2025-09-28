# Basic prompt templates for the adapters.
# The detailed instructions for the agent should be in the agno.Agent's system_message.

import os

INPUT_PROMPT = """Current Task Goal: {input_goal}

Context:
{context_str}"""

AGGREGATOR_PROMPT = """Parent Goal: {input_goal}
Sub-task Results:
{context_str}"""


def get_project_folder_context() -> str:
    """Generate universal folder context information for system prompts.
    
    This function creates folder context that works across all platforms
    (local, E2B, Docker, etc.) using universal environment variables that
    are set by ProjectManager.create_project().
    
    Returns:
        str: Formatted folder context for system prompts, or empty string if no project is active
    """
    from sentientresearchagent.core.project_context import get_project_context, get_project_directories
    
    project_data = get_project_directories()
    project_id = project_data.get('project_id')
    toolkits_dir = project_data.get('toolkits_dir')
    results_dir = project_data.get('results_dir')
    
    # Only return context if all required data is available
    if not project_id or not toolkits_dir or not results_dir:
        return ""
    
    return f"""
## Project Execution Environment
Project ID: {project_id}

### Available Directories:
- **Toolkit Data**: `{toolkits_dir}/` - Access data stored by toolkits
- **Results Output**: `{results_dir}/` - Save your execution results
  - Plots: `{results_dir}/plots/`
  - Artifacts: `{results_dir}/artifacts/`
  - Reports: `{results_dir}/reports/`

Use these universal paths for reading toolkit data and saving results to maintain project isolation.
"""

# You can add more specialized prompt templates here as needed,
# like the COMBINED_SEARCHER_REASONER_SYNTHESIZER_PROMPT from your old prompts.py
# if you plan to use such specific agent patterns. For now, keeping it minimal.

# Example of a more complex prompt if you had a specific agent needing it:
# RESEARCH_SYNTHESIS_PROMPT = """
# Original Research Question: {input_goal}
#
# Provided Information Snippets:
# {context_str} # context_str would be formatted to list research findings
#
# Your Task: Synthesize the provided information snippets into a coherent answer
# for the original research question. Focus on accuracy and conciseness.
# """
