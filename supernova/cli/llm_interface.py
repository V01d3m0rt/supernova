"""
SuperNova - AI-powered development assistant within the terminal.

LLM interface for managing interactions with the language model.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union, Callable

import openai
from openai import OpenAI

from rich.console import Console

from supernova.core import llm_provider
from supernova.config import loader

console = Console()

class LLMInterface:
    """
    Interface for communicating with large language models.
    
    Responsibilities:
    - Managing API connections
    - Formatting messages for LLM
    - Handling LLM responses
    - Processing tool calls
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: Optional[Union[int, str]] = None,
        logger = None
    ):
        """
        Initialize the LLM interface.
        
        Args:
            api_key: OpenAI API key
            model: LLM model to use
            temperature: Temperature for sampling
            max_tokens: Maximum tokens to generate in the response
            logger: Logger to use
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        
        # Convert max_tokens to int if it's a string, or leave as None
        if max_tokens is not None:
            try:
                self.max_tokens = int(max_tokens)
            except (ValueError, TypeError):
                logger.warning(f"Invalid max_tokens value: {max_tokens}, using default")
                self.max_tokens = None
        else:
            self.max_tokens = None
            
        self.logger = logger or logging.getLogger(__name__)
        
        # Set up client for OpenAI
        try:
            self.client = OpenAI(api_key=self.api_key)
        except Exception as e:
            self.logger.error(f"Error initializing OpenAI client: {str(e)}")
            raise
            
        # Initialize streaming state variables
        self.streaming_accumulated_content = ""
        self.streaming_accumulated_tool_calls = {}
    
    def format_messages(
        self,
        content: str,
        previous_messages: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        system_message: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
        """
        Format messages for the LLM.
        
        Args:
            content: User message content
            previous_messages: Previous messages to include
            tool_results: Results from tool calls
            system_message: Custom system message
            
        Returns:
            Tuple of (messages, tools_list, tool_choice)
        """
        messages = []
        
        # Add system message
        if system_message:
            messages.append({
                "role": "system",
                "content": system_message
            })
        else:
            # Default system message
            messages.append({
                "role": "system",
                "content": (
                    "You are SuperNova, an AI assistant specialized in helping developers. "
                    "You have access to terminal commands and file operations. "
                    "Always provide clear, concise help focused on the user's needs."
                )
            })
        
        # Add previous messages if provided
        if previous_messages:
            messages.extend(previous_messages)
        
        # Add current user message if not empty
        if content:
            messages.append({
                "role": "user",
                "content": content
            })
        
        # Add tool results if provided
        tool_choice = None
        if tool_results:
            for result in tool_results:
                # Format the tool result as a message
                tool_message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [result]
                }
                messages.append(tool_message)
                
                # Format the tool response
                tool_response = {
                    "role": "tool",
                    "tool_call_id": result["id"],
                    "name": result["function"]["name"],
                    "content": result["function"]["response"]
                }
                messages.append(tool_response)
        
        # Return formatted messages and empty tools list (will be filled by caller)
        return messages, [], tool_choice
    
    def get_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a completion from the LLM.
        
        Args:
            messages: List of messages
            tools: List of tools available to the LLM
            tool_choice: Tool choice strategy
            
        Returns:
            LLM response
        """
        try:
            self.logger.debug(f"Sending request to LLM ({self.model})")
            
            # Create request parameters
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
            }
            
            # Add max_tokens if specified
            if self.max_tokens:
                try:
                    params["max_tokens"] = int(self.max_tokens)
                except (ValueError, TypeError):
                    self.logger.warning(f"Invalid max_tokens value: {self.max_tokens}, using default")
                    # Omit max_tokens parameter to use API default
            
            # Add tools if provided
            if tools:
                params["tools"] = tools
                
                # Add tool_choice if specified
                if tool_choice:
                    params["tool_choice"] = tool_choice
            
            # Get completion
            response = self.client.chat.completions.create(**params)
            
            # Convert to dict for easier processing
            response_dict = self._convert_response_to_dict(response)
            
            return response_dict
        except Exception as e:
            self.logger.error(f"Error getting completion: {str(e)}")
            return {
                "error": str(e),
                "content": f"Error getting completion: {str(e)}"
            }
    
    def process_response(self, response) -> Dict[str, Any]:
        """
        Process a response from the LLM.
        
        Args:
            response: The raw response from the LLM
            
        Returns:
            Processed response with content and tool calls
        """
        processed = {
            "content": "",
            "tool_calls": []
        }
        
        self.logger.debug(f"Processing LLM response of type: {type(response)}")
        
        try:
            # Handle different response formats
            if isinstance(response, dict):
                # Extract content if available
                if "content" in response:
                    processed["content"] = response["content"]
                elif "assistant_response" in response:
                    processed["content"] = response["assistant_response"]
                elif "choices" in response and len(response["choices"]) > 0:
                    choice = response["choices"][0]
                    if isinstance(choice, dict) and "message" in choice:
                        message = choice["message"]
                        if isinstance(message, dict) and "content" in message:
                            processed["content"] = message["content"]
                
                # Extract tool calls if available
                tool_calls = []
                
                # Check for tool_calls in various locations
                if "tool_calls" in response:
                    tool_calls = response["tool_calls"]
                elif "choices" in response and len(response["choices"]) > 0:
                    choice = response["choices"][0]
                    if isinstance(choice, dict):
                        if "message" in choice:
                            message = choice["message"]
                            if isinstance(message, dict) and "tool_calls" in message:
                                tool_calls = message["tool_calls"]
                                
                # Ensure tool_calls is a list
                if tool_calls and not isinstance(tool_calls, list):
                    tool_calls = [tool_calls]
                    
                processed["tool_calls"] = tool_calls
                
                # Add any additional fields we need
                if "finish_reason" in response:
                    processed["finish_reason"] = response["finish_reason"]
                elif "choices" in response and len(response["choices"]) > 0:
                    choice = response["choices"][0]
                    if isinstance(choice, dict) and "finish_reason" in choice:
                        processed["finish_reason"] = choice["finish_reason"]
            
            # If response is some other format, try to extract content
            elif hasattr(response, "content"):
                processed["content"] = response.content
            elif hasattr(response, "choices") and response.choices:
                if hasattr(response.choices[0], "message") and hasattr(response.choices[0].message, "content"):
                    processed["content"] = response.choices[0].message.content
                elif hasattr(response.choices[0], "text"):
                    processed["content"] = response.choices[0].text
            else:
                # Last resort, convert to string
                processed["content"] = str(response)
                
            return processed
        except Exception as e:
            self.logger.error(f"Error processing LLM response: {e}")
            return {
                "content": f"Error processing response: {str(e)}",
                "tool_calls": []
            }
    
    def _convert_response_to_dict(self, response) -> Dict[str, Any]:
        """
        Convert OpenAI response object to dictionary.
        
        Args:
            response: OpenAI response object
            
        Returns:
            Dictionary representation
        """
        try:
            # Convert to dictionary
            return response.model_dump()
        except AttributeError:
            # Fallback for older OpenAI SDK versions
            try:
                return response.to_dict()
            except AttributeError:
                # Last resort - manual conversion
                return {
                    "choices": [
                        {
                            "message": {
                                "content": response.choices[0].message.content,
                                "role": response.choices[0].message.role,
                                "tool_calls": getattr(response.choices[0].message, "tool_calls", None)
                            },
                            "finish_reason": response.choices[0].finish_reason
                        }
                    ],
                    "id": response.id,
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
    
    def format_messages_for_llm(
        self, 
        content: str = "", 
        system_prompt: str = "", 
        context_message: str = "",
        previous_messages: List[Dict[str, Any]] = None,
        include_tools: bool = True,
        tools: List[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Format messages for the LLM including tools and context.
        
        Args:
            content: User message content
            system_prompt: System prompt to use
            context_message: Context message to add to user message
            previous_messages: Previous messages to include
            include_tools: Whether to include tools
            tools: List of tools to include
            
        Returns:
            Tuple of (messages, tools_list, tool_choice)
        """
        # Initialize previous_messages if not provided
        if previous_messages is None:
            previous_messages = []
            
        # Format messages for the LLM
        formatted_messages = []
        
        # Add system message
        if system_prompt:
            formatted_messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Add previous messages
        for msg in previous_messages:
            if msg["role"] in ["user", "assistant", "system", "tool"]:
                formatted_msg = {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                formatted_messages.append(formatted_msg)
        
        # Add context message as a system message if provided
        if context_message:
            formatted_messages.append({
                "role": "system",
                "content": f"Current session state:\n{context_message}"
            })
        
        # Add current message if provided
        if content:
            formatted_messages.append({
                "role": "user",
                "content": content
            })
        
        # Prepare tools if required
        formatted_tools = []
        tool_choice = None
        
        if include_tools:
            if tools:
                formatted_tools = tools
            # Let the model choose which tool to use
            tool_choice = {"type": "auto"}
        
        return formatted_messages, formatted_tools, tool_choice
    
    def generate_system_prompt(
        self, 
        available_tools: List[str] = None,
        available_tools_text: str = None,
        cli_args: Dict[str, Any] = None, 
        is_initial_prompt: bool = False
    ) -> str:
        """
        Generate the system prompt for the LLM.
        
        Args:
            available_tools: List of available tool names
            available_tools_text: Text describing available tools
            cli_args: Optional CLI arguments
            is_initial_prompt: Whether this is the initial prompt
            
        Returns:
            The system prompt
        """
        # Use empty dict if cli_args is None
        if cli_args is None:
            cli_args = {}
        
        # Define token allocation constants if not already defined
        self.token_allocation_constants = getattr(self, "token_allocation_constants", {
            "PROMPT_OVERHEAD": 0.1,
            "SYSTEM_MESSAGE": 0.2
        })
            
        # Calculate token allocation - handle cases when max_tokens might be None or a string
        try:
            if self.max_tokens is None:
                max_token_allocation = 4000  # Default value
            else:
                max_token_allocation = int(self.max_tokens) - (
                    int(self.max_tokens) * self.token_allocation_constants["PROMPT_OVERHEAD"]
                )
            
            system_token_allocation_percentage = (
                self.token_allocation_constants["SYSTEM_MESSAGE"]
            )
            system_token_allocation = max_token_allocation * system_token_allocation_percentage
        except (ValueError, TypeError):
            # If conversion fails, use default values
            self.logger.warning(f"Invalid max_tokens value: {self.max_tokens}, using default")
            max_token_allocation = 4000
            system_token_allocation = 800
        
        # If no available_tools_text provided but we have available_tools, format them
        if not available_tools_text and available_tools:
            available_tools_text = "\n".join([f"- `{tool}`" for tool in available_tools]) 
        
        # If no available_tools_text, use empty message
        if not available_tools_text:
            available_tools_text = "No tools are currently available."
        
        # Format guidance for tool calling
        tool_call_guidance = f"""
⚠️ ⚠️ ⚠️ CRITICAL INSTRUCTION: TOOL CALLING FORMAT ⚠️ ⚠️ ⚠️

You MUST use ONLY the native tool calling API for ALL tool usage. ANY other format WILL FAIL and result in TASK FAILURE.

❌ NEVER use these incorrect formats:
  1. NEVER output tool calls as raw JSON
  2. NEVER use a ```tool_request ... [END_TOOL_REQUEST]```
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

{getattr(self, "config", {}).get("system_prompt_override", "")}

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

9. IMPORTANT: You should perform all the operations wither in the initial directory or in the currect direct.
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
            estimated_tokens = len(text.split())
            return estimated_tokens

        # Calculate tokens for the base prompt
        base_prompt_tokens = calculate_tokens_for_text(system_prompt)

        # Calculate how many tokens we have left for memory
        memory_token_allocation = system_token_allocation - base_prompt_tokens

        # If we have memory items and memory tokens available, include memory content
        memory_content = self.get_memory_content_for_prompt(
            memory_token_allocation, cli_args, is_initial_prompt
        )

        # Assemble the final system prompt
        final_system_prompt = system_prompt

        if memory_content:
            final_system_prompt += f"\n\nHere is relevant information from your Memory Bank:\n\n{memory_content}"

        return final_system_prompt
    
    def get_memory_content_for_prompt(
        self, token_allocation: int, cli_args: Dict[str, Any] = None, is_initial_prompt: bool = False
    ) -> str:
        """
        Get memory content for the system prompt within token allocation.
        
        Args:
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
        return "\n".join(memory_content) if memory_content else ""
