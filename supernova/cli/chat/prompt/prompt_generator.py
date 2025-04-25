"""
Prompt generator for chat sessions.
"""

from typing import Any, Dict, List, Optional

class PromptGenerator:
    """
    Generates prompts for the LLM.
    """
    def __init__(self, config, tool_manager, token_allocation_constants, max_tokens):
        """
        Initialize the prompt generator.
        
        Args:
            config: Configuration object
            tool_manager: Tool manager
            token_allocation_constants: Token allocation constants
            max_tokens: Maximum tokens
        """
        self.config = config
        self.tool_manager = tool_manager
        self.token_allocation_constants = token_allocation_constants
        self.max_tokens = max_tokens
        
    def generate_system_prompt(
        self, 
        session_state: Dict[str, Any], 
        cli_args: Dict[str, Any] = None, 
        is_initial_prompt: bool = False
    ) -> str:
        """
        Generate the system prompt for the LLM.
        
        Args:
            session_state: Current session state
            cli_args: Optional CLI arguments
            is_initial_prompt: Whether this is the initial prompt
            
        Returns:
            The system prompt
        """
        # Use empty dict if cli_args is None
        if cli_args is None:
            cli_args = {}
            
        max_token_allocation = self.max_tokens - (
            self.max_tokens * self.token_allocation_constants["PROMPT_OVERHEAD"]
        )
        system_token_allocation_percentage = (
            self.token_allocation_constants["SYSTEM_MESSAGE"]
        )
        system_token_allocation = max_token_allocation * system_token_allocation_percentage
        
        # Get the list of actually available tools
        available_tools = []
        if self.tool_manager:
            tools = self.tool_manager.get_available_tools_for_llm(session_state)
            for tool in tools:
                if isinstance(tool, dict) and "function" in tool:
                    func = tool["function"]
                    name = func.get("name", "unknown")
                    description = func.get("description", "No description")
                    available_tools.append(f"- `{name}`: {description}")
        
        available_tools_text = "\n".join(available_tools) if available_tools else "No tools are currently available."
        
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

        # Base system prompt with critical tool guidance first
        system_prompt = f"""You are SuperNova, a powerful AI-powered development assistant, built by ex-OpenAI engineers. You are both skilled at software engineering and effective at helping users plan and execute complex creative and analytical projects.

{tool_call_guidance}

{getattr(self.config, "system_prompt_override", "")}

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

3. I'll use the terminal_command tool to explore the Memory Bank and understand the project context. For example:
   - `ls memory-bank/` to see what files are available
   - `cat memory-bank/activeContext.md` to read about the current work focus
   - `cat memory-bank/projectbrief.md` to understand the project overview

4. After understanding the context, I'll help the user with their specific request by:
   - Breaking down complex problems into manageable steps
   - Using tools to explore code, run commands, or create/edit files as needed
   - Providing clear explanations and guidance
   - Suggesting best practices and improvements

5. I'll maintain a helpful, professional tone throughout our conversation.

⚠️ IMPORTANT DIRECTORY RESTRICTION ⚠️
All operations MUST remain within the initial directory: {session_state.get('initial_directory', '')}
DO NOT attempt to access or modify files outside this directory.

Current working directory: {session_state.get('cwd', '')}
"""

        # Add directory restriction reminder
        system_prompt += """
⚠️ DIRECTORY RESTRICTION REMINDER ⚠️
- You MUST respect the initial directory boundary
- All file operations must be within this directory
- Use relative paths when possible
- DO NOT attempt to access parent directories beyond the initial directory
"""

        return system_prompt
        
    def generate_context_message(self, session_state: Dict[str, Any]) -> str:
        """
        Generate a context message with information about the current state.
        
        Args:
            session_state: Current session state
            
        Returns:
            Context message
        """
        # Get current working directory and initial directory
        cwd = session_state.get("cwd", "")
        initial_directory = session_state.get("initial_directory", "")
        
        # Get path history
        path_history = session_state.get("path_history", [])
        path_history_str = ", ".join(path_history[-5:])  # Show last 5 paths
        
        # Get project summary if available
        project_summary = session_state.get("project_summary", "No project analysis available")
        
        # Format context message
        context_message = f"""
## Current Context Information

### Working Directory
- Current: {cwd}
- Initial: {initial_directory} (operations restricted to this directory)
- Recent paths: {path_history_str}

### Project Information
{project_summary}
"""

        # Add information about created files if any
        created_files = session_state.get("created_files", [])
        if created_files:
            files_str = "\n".join([f"- {file}" for file in created_files[-5:]])  # Show last 5 files
            context_message += f"""
### Recently Created/Modified Files
{files_str}
"""

        # Add information about executed commands if any
        executed_commands = session_state.get("executed_commands", [])
        if executed_commands:
            # Extract just the command strings from the last 5 commands
            recent_commands = []
            for cmd_entry in executed_commands[-5:]:
                if isinstance(cmd_entry, dict) and "command" in cmd_entry:
                    recent_commands.append(cmd_entry["command"])
                elif isinstance(cmd_entry, str):
                    recent_commands.append(cmd_entry)
                    
            commands_str = "\n".join([f"- `{cmd}`" for cmd in recent_commands])
            context_message += f"""
### Recently Executed Commands
{commands_str}
"""

        return context_message
        
    def format_messages_for_llm(
        self,
        content: str,
        system_prompt: str,
        context_msg: str,
        previous_messages: List[Dict[str, Any]],
        include_tools: bool = True,
        session_state: Optional[Dict[str, Any]] = None
    ) -> tuple:
        """
        Format messages for the LLM.
        
        Args:
            content: Content to add to the messages
            system_prompt: System prompt
            context_msg: Context message
            previous_messages: Previous messages
            include_tools: Whether to include tools
            session_state: Current session state
            
        Returns:
            Tuple of (formatted_messages, tools, tool_choice)
        """
        # Start with system message
        formatted_messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add context message as system message
        if context_msg:
            formatted_messages.append(
                {"role": "system", "content": context_msg}
            )
            
        # Add previous messages
        for msg in previous_messages:
            # Skip system messages as we've already added our own
            if msg.get("role") == "system":
                continue
                
            # Create a new message dict with just the required fields
            new_msg = {"role": msg["role"], "content": msg["content"]}
            
            # Add name if present
            if "name" in msg:
                new_msg["name"] = msg["name"]
                
            # Add tool_call_id if present
            if "tool_call_id" in msg:
                new_msg["tool_call_id"] = msg["tool_call_id"]
                
            formatted_messages.append(new_msg)
            
        # Add the new content if provided
        if content:
            formatted_messages.append({"role": "user", "content": content})
            
        # Get tools if requested
        tools = None
        tool_choice = None
        
        if include_tools and self.tool_manager and session_state:
            tools = self.tool_manager.get_available_tools_for_llm(session_state)
            
        return formatted_messages, tools, tool_choice