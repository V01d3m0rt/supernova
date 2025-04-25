"""
Prompt generators for chat sessions.

This module contains prompt generators for creating system prompts and other
prompts for the chat session.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional


class PromptGenerator:
    """
    Generates prompts for the chat session.
    
    Handles generating system prompts and other prompts for the LLM.
    """
    
    def __init__(self, config=None):
        """
        Initialize the prompt generator.
        
        Args:
            config: Configuration object
        """
        self.logger = logging.getLogger("supernova.chat.prompt_generator")
        self.config = config
        
        # Token allocation constants
        self.max_tokens = 4096  # Default max tokens
        self.llm_token_allocation_constants = {
            "PROMPT_OVERHEAD": 0.2,  # 20% reserved for overhead
            "SYSTEM_MESSAGE": 0.5,   # 50% of remaining tokens for system message
            "CONTEXT": 0.2,          # 20% of remaining tokens for context
            "HISTORY": 0.3           # 30% of remaining tokens for chat history
        }
        
        # If config has token allocation settings, use those
        if self.config and hasattr(self.config, "token_allocation"):
            if hasattr(self.config.token_allocation, "max_tokens"):
                self.max_tokens = self.config.token_allocation.max_tokens
            if hasattr(self.config.token_allocation, "constants"):
                token_constants = self.config.token_allocation.constants
                for key, value in token_constants.items():
                    if key in self.llm_token_allocation_constants:
                        self.llm_token_allocation_constants[key] = value
    
    def generate_system_prompt(
        self, 
        session_state: Dict[str, Any],
        available_tools: List[Dict[str, Any]] = None,
        cli_args: Dict[str, Any] = None, 
        is_initial_prompt: bool = False
    ) -> str:
        """
        Generate the system prompt for the LLM.
        
        Args:
            session_state: Current session state
            available_tools: Available tools for the LLM
            cli_args: Optional CLI arguments
            is_initial_prompt: Whether this is the initial prompt
            
        Returns:
            The system prompt
        """
        # Use empty dict if cli_args is None
        if cli_args is None:
            cli_args = {}
            
        # Calculate token allocations
        max_token_allocation = self.max_tokens - (
            self.max_tokens * self.llm_token_allocation_constants["PROMPT_OVERHEAD"]
        )
        system_token_allocation_percentage = (
            self.llm_token_allocation_constants["SYSTEM_MESSAGE"]
        )
        system_token_allocation = max_token_allocation * system_token_allocation_percentage
        
        # Get the list of actually available tools
        if available_tools is None:
            available_tools = []
            
        available_tool_descriptions = []
        for tool in available_tools:
            if isinstance(tool, dict) and "function" in tool:
                func = tool["function"]
                name = func.get("name", "unknown")
                description = func.get("description", "No description")
                available_tool_descriptions.append(f"- `{name}`: {description}")
        
        available_tools_text = "\n".join(available_tool_descriptions) if available_tool_descriptions else "No tools are currently available."
        
        # Format guidance for tool calling
        tool_call_guidance = f"""
⚠️ ⚠️ ⚠️ CRITICAL INSTRUCTION: TOOL CALLING FORMAT ⚠️ ⚠️ ⚠️

You MUST use ONLY the native tool calling API for ALL tool usage. ANY other format WILL FAIL and result in TASK FAILURE.

❌ NEVER use these incorrect formats:
  1. NEVER output tool calls as raw JSON
  2. NEVER use a ```tool_request ... [END_TOOL_REQUEST]``` format
  3. NEVER use <tool_name> or similar custom XML formats
  4. NEVER output tool calls as code blocks

✅ ALWAYS use the native API format for tool calls:
  - Use the built-in tool calling API that returns "finish_reason": "tool_calls"
  - Let the system handle the JSON conversion and tool execution
  - ONLY use tools that are actually provided to you in the API request
  - DO NOT attempt to use any tools that are not explicitly provided

⚠️ IMPORTANT: You MUST ONLY use the tools that are specifically provided to you in this session.
The following tools are currently available:

{available_tools_text}

DO NOT attempt to use any tools not listed above, even if they seem like they would be helpful.

Example of CORRECT tool usage (DO THIS):
  When you need to use a tool, simply declare your intent to use it normally within the API.
  The system will automatically convert your request to the appropriate JSON format.

This is an absolute requirement for successful task completion.
"""

        # Get the system prompt override from config if available
        system_prompt_override = ""
        if self.config and hasattr(self.config, "system_prompt_override"):
            system_prompt_override = getattr(self.config, "system_prompt_override", "")

        # Base system prompt with critical tool guidance first
        system_prompt = f"""You are SuperNova, a powerful AI-powered development assistant, built by ex-OpenAI engineers. You are both skilled at software engineering and effective at helping users plan and execute complex creative and analytical projects.

{tool_call_guidance}

{system_prompt_override}

For this conversation, let's break down our workflow into the following clear steps:

1. First, analyze what the user is asking for to understand their goal. Read their question carefully.

2. If this is a "fresh" conversation with a new task (i.e., this is the initial message), I should explore the Memory Bank to understand context. The Memory Bank is a collection of knowledge files about our project:
   - projectbrief.md: Overview of the project
   - activeContext.md: Current work focus
   - systemPatterns.md: Architecture and patterns
   - techContext.md: Technologies in use
   - productContext.md: Product context
   - progress.md: Current progress
   - Any additional context files that may be available

3. My source of truth for what's been asked, agreed, and done during the current task should be documented in the active_task.md file, including:
    - The initial goal stated by the user
    - The agreed plan
    - Progress made so far
    - Any important decisions
    - Future steps to be taken

4. When I analyze the results of a tool, I should:
   - Carefully look at all the output
   - Consider whether there were errors
   - Remember important file content
   - Use these findings to develop a comprehensive understanding for my next action

5. When I need to accomplish a task:
   - ⚠️ REMEMBER: ONLY use the tools that are available to me (listed above) ⚠️
   - Use tools in a way that's appropriate to the task I'm trying to accomplish
   - I must NEVER try to use tools that aren't available to me
   - If I can't accomplish a task with available tools, I should explain what I would do if I had the appropriate tools
   - NEVER invent or assume the existence of tools that aren't explicitly provided

6. When I write code, I should:
   - Review existing patterns first
   - Match the surrounding style and conventions
   - Import all necessary dependencies
   - Add descriptive comments (but not excessively)
   - Be mindful of edge cases
   - Avoid redundant or duplicate code
   - Write complete, correct implementations

7. When given a task, I should break it down into:
   - Immediate actions
   - Later steps
   - Information that needs to be discovered
   - Potential challenges

8. IMPORTANT: I should not repeat the same actions! If I've already looked at a file and found that it doesn't contain what I'm looking for, I should focus my search elsewhere. Similarly, if I've tried to run a command and it failed, I should adapt my approach rather than just trying the same thing again.

9. IMPORTANT: You should perform all the operations wither in the initial directory or in the currect direct, the current directory is: 
 Current directory: {session_state["cwd"]}
 Initial directory: {session_state["initial_directory"]}
 you can access other files and directory in case if its required, otherwise the recommendation is to limit your access and actions to currect directory upto inital directory.
 
10. Throughout the conversation, I will:
   - Keep my responses focused and concise
   - Clearly indicate when I'm using tools to gather information
   - Summarize findings succinctly without excessive detail
   - Focus on delivering solutions rather than explaining generic concepts

11. ⚠️ Tool usage rule: I MUST ONLY use the standard tool call format built into the API, and ONLY for tools that are available (listed above). I must NEVER provide tool calls as raw code blocks or JSON, and must NEVER use any custom format like ```tool_request``` or similar. Failure to follow this rule will result in tool execution failure. ⚠️

When analyzing code, I'll look beyond just syntax to understand architecture, data flow, and potential edge cases.

I may proactively provide advice on code improvements, potential bugs, or design considerations based on my analysis.

I am here to help you build great software!
"""

        def calculate_tokens_for_text(text: str) -> int:
            """Calculate approximate token count for a text."""
            estimated_tokens = len(text.split())
            return estimated_tokens

        # Calculate tokens for the base prompt
        base_prompt_tokens = calculate_tokens_for_text(system_prompt)

        # Calculate how many tokens we have left for memory
        memory_token_allocation = system_token_allocation - base_prompt_tokens

        # If we have memory items and memory tokens available, include memory content
        memory_content = self.get_memory_content_for_prompt(
            session_state["cwd"],
            memory_token_allocation, 
            cli_args, 
            is_initial_prompt
        )

        # Assemble the final system prompt
        final_system_prompt = system_prompt

        if memory_content:
            final_system_prompt += f"\n\nHere is relevant information from your Memory Bank:\n\n{memory_content}"

        return final_system_prompt

    def get_memory_content_for_prompt(
        self, 
        cwd: str,
        token_allocation: int, 
        cli_args: Dict[str, Any] = None, 
        is_initial_prompt: bool = False
    ) -> str:
        """
        Get memory content for the system prompt within token allocation.
        
        Args:
            cwd: Current working directory
            token_allocation: Maximum tokens to allocate for memory content
            cli_args: CLI arguments that may contain memory-related options
            is_initial_prompt: Whether this is the initial prompt
            
        Returns:
            Formatted memory content string
        """
        # Simple placeholder implementation - in a real scenario, we'd read 
        # actual memory files from the .supernova directory based on token allocation
        memory_content = []
        
        # If we're in a project with a .supernova directory, try to read some basic files
        supernova_dir = Path(cwd) / ".supernova"
        memory_bank_dir = Path(cwd) / "memory-bank"  # Also check memory-bank directory
        
        # Try .supernova directory first
        if supernova_dir.exists() and supernova_dir.is_dir():
            # Priority files to include
            priority_files = [
                "project_brief.md",
                "active_task.md", 
                "progress_log.md"
            ]
            
            # Try to read each priority file
            for filename in priority_files:
                file_path = supernova_dir / filename
                if file_path.exists() and file_path.is_file():
                    try:
                        # Read the file content
                        content = file_path.read_text()
                        if content.strip():
                            # Add a header and the content
                            memory_content.append(f"## {filename}")
                            memory_content.append(content.strip())
                            memory_content.append("")  # Empty line for separation
                    except Exception as e:
                        self.logger.warning(f"Could not read memory file {filename}: {str(e)}")
        
        # Also check memory-bank directory if it exists
        if memory_bank_dir.exists() and memory_bank_dir.is_dir():
            # Priority files to include
            priority_files = [
                "projectbrief.md",
                "activeContext.md",
                "progress.md",
                "systemPatterns.md",
                "techContext.md",
                "productContext.md"
            ]
            
            # Try to read each priority file
            for filename in priority_files:
                file_path = memory_bank_dir / filename
                if file_path.exists() and file_path.is_file():
                    try:
                        # Read the file content
                        content = file_path.read_text()
                        if content.strip():
                            # Add a header and the content
                            memory_content.append(f"## {filename}")
                            # Limit the content to first 500 characters + "..."
                            if len(content) > 500:
                                content = content[:500] + "...\n[Content truncated for brevity. Use tools to read complete file.]"
                            memory_content.append(content.strip())
                            memory_content.append("")  # Empty line for separation
                    except Exception as e:
                        self.logger.warning(f"Could not read memory file {filename}: {str(e)}")
        
        # Join the memory content with newlines
        return "\n".join(memory_content) if memory_content else "" 