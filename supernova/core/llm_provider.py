"""
SuperNova - AI-powered development assistant within the terminal.

LLM provider integration using LiteLLM.
"""

import json
import os
import asyncio
import logging
from typing import Dict, List, Optional, Union, Any, Callable
from functools import partial
import re
from types import SimpleNamespace

import litellm
from litellm import acompletion, completion, Timeout
from rich.console import Console

from supernova.config import loader
from supernova.config.schema import LLMProviderConfig

console = Console()

# TODO: VS Code Integration - Add VSCode-specific enhancements:
# 1. Create VSCodeLLMProvider extension of LLMProvider that integrates with VS Code API
# 2. Support displaying streaming responses in VS Code UI
# 3. Add support for VS Code-specific context in prompts


class LLMProvider:
    """LLM provider wrapper using LiteLLM."""
    
    # Class-level list of known tool-capable models
    known_tool_capable_models = [
        # Gemma models
        "gemma-3", 
        "gemma-2",
        "gemma-7b",
        "gemma-instruct",
        "gemma-2-2b-it",
        "gemma-2-9b-it",
        "gemma-2-27b-it",
        "gemma-7b-it",
        
        # Gemini models
        "gemini",
        "gemini-pro",
        "gemini-1.5",
        "gemini-1.0",
        
        # Llama models
        "llama-3", 
        "llama-3-8b",
        "llama-3-70b",
        "llama-3-405b",
        "llama-2",
        
        # Anthropic Claude models
        "claude-3", 
        "claude-3-5", 
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku",
        
        # Other models
        "grok",
        "mistral-large",
        "mistral-medium",
        "mistral-small",
        "mixtral",
        "phi-3",
        "command-r",
        "qwen2.5-7b-instruct"
    ]
    
    def __init__(self, provider_name: Optional[str] = None):
        """
        Initialize the LLM provider.
        
        Args:
            provider_name: Name of the provider to use (default: use the default provider from config)
        """
        # Set up logging
        self.logger = logging.getLogger("supernova.llm_provider")
        
        self.config = loader.load_config()
        
        if provider_name:
            # Use the specified provider
            if provider_name not in self.config.llm_providers:
                raise ValueError(f"Provider '{provider_name}' not found in configuration")
            self.provider_config = self.config.llm_providers[provider_name]
        else:
            # Find the default provider
            for name, provider in self.config.llm_providers.items():
                if provider.is_default:
                    self.provider_config = provider
                    provider_name = name
                    break
            else:
                # If no default is specified, use the first provider
                provider_name = next(iter(self.config.llm_providers))
                self.provider_config = self.config.llm_providers[provider_name]
        
        self.provider_name = provider_name
        self.logger.info(f"Initialized LLM provider: {provider_name}")
        
        # Configure LiteLLM for this provider
        self._configure_litellm()
        
        # TODO: VS Code Integration - If running in VS Code, detect and configure:
        # 1. Progressive response rendering in the editor
        # 2. VS Code Authentication API for securing API keys
        # 3. VS Code Settings API for provider configuration
    
    def _configure_litellm(self) -> None:
        """Configure LiteLLM based on the provider configuration."""
        # We'll no longer set environment variables here.
        # Configuration will be passed directly to the API calls
        pass
    
    def _get_api_params(self) -> Dict[str, Any]:
        """
        Get API parameters for LiteLLM calls.
        
        Returns:
            Dictionary of API parameters
        """
        params = {}
        
        # Add API key if provided
        if self.provider_config.api_key:
            params["api_key"] = self.provider_config.api_key
        
        # Add base URL if provided
        if self.provider_config.base_url:
            params["api_base"] = self.provider_config.base_url
            
        # Add API version if provided (required for Azure OpenAI)
        if hasattr(self.provider_config, "api_version") and self.provider_config.api_version:
            params["api_version"] = self.provider_config.api_version
            
        return params
    
    def supports_tool_calling(self) -> bool:
        """
        Check if the current model supports tool calling.
        
        Returns:
            True if tool calling is supported, False otherwise
        """
        try:
            model_name = self.provider_config.model
            
            # Check if we need to add a provider prefix to the model name
            if self.provider_config.provider == "openai" and self.provider_config.base_url:
                # For custom OpenAI-compatible APIs like LM Studio, we need to prefix the model
                if self.provider_name == "lm_studio":
                    model_name = f"openai/{model_name}"
            
            # Check if model name contains any of the known tool-capable models
            if any(model_id in model_name.lower() for model_id in self.known_tool_capable_models):
                return True
                
            # Use LiteLLM's function to check most models
            return litellm.supports_function_calling(model=model_name)
        except Exception as e:
            console.print(f"[yellow]Warning: Error checking tool calling support:[/yellow] {str(e)}")
            return False

    @classmethod
    def add_tool_capable_model(cls, model_identifier: str) -> None:
        """
        Add a model identifier to the list of known tool-capable models.
        
        Args:
            model_identifier: A string that identifies the model (e.g., "gemma-3")
                             This will match any model name containing this string.
        """
        if model_identifier and model_identifier.strip():
            # Convert to lowercase and add to the list if not already present
            model_id = model_identifier.strip().lower()
            if model_id not in cls.known_tool_capable_models:
                cls.known_tool_capable_models.append(model_id)
                console.print(f"[green]Added '{model_id}' to known tool-capable models list[/green]")

    def _sanitize_response_content(self, content: str) -> str:
        """
        Sanitize the content from LLM responses, including handling JSON responses.
        
        Args:
            content: The content to sanitize
            
        Returns:
            Sanitized content
        """
        if not content:
            return ""
        
        # Check if the content is a JSON string with a 'content' field
        if isinstance(content, str) and content.strip().startswith('{') and content.strip().endswith('}'):
            try:
                # Try to parse as JSON
                json_content = json.loads(content)
                if isinstance(json_content, dict) and "content" in json_content:
                    # Extract just the content field, ignoring other fields like tool_calls
                    content = json_content["content"]
                    self.logger.debug("Extracted content from JSON response")
            except json.JSONDecodeError:
                # Not valid JSON, try Python literal eval
                if "'content':" in content or '"content":' in content:
                    try:
                        # Simple check to avoid executing arbitrary code
                        if all(c not in content for c in ['import', 'exec', 'eval', 'os.', 'subprocess']):
                            import ast
                            try:
                                # Try to evaluate as a Python literal
                                dict_content = ast.literal_eval(content)
                                if isinstance(dict_content, dict) and "content" in dict_content:
                                    content = dict_content["content"]
                                    self.logger.debug("Extracted content using ast.literal_eval")
                            except (SyntaxError, ValueError):
                                # Not a valid Python literal, keep as is
                                self.logger.debug("Failed to parse content as Python literal")
                                pass
                    except Exception as e:
                        # Any error, keep original content
                        self.logger.debug(f"Error handling content: {str(e)}")
                        pass
        
        # Clean up excessive whitespace and return
        return content.strip()
        
    # This method is no longer used - we rely on LiteLLM's native tool call handling
    def _extract_tool_calls_from_text(self, content: str) -> str:
        """
        [DEPRECATED] This method previously used regex to extract tool calls from text content.
        We now rely exclusively on LiteLLM's native tool call handling instead.
        
        This method is kept as a stub for backward compatibility but does nothing.
        
        Args:
            content: The content text
            
        Returns:
            Unmodified content
        """
        # No longer using regex pattern matching to extract tool calls
        # Instead, we rely on LiteLLM's structured tool call data
        return content

    def is_repeating_failed_command(self, tool_name: str, args: dict, failed_commands: list) -> bool:
        """
        Check if the current tool call is repeating a command that has already failed.
        
        Args:
            tool_name: The name of the tool being called
            args: The arguments for the tool call
            failed_commands: List of previous failed commands to check against
            
        Returns:
            True if this command appears to be a repeat of a failed command
        """
        # If no failed commands yet, it can't be a repeat
        if not failed_commands:
            return False
            
        # For terminal commands, check if the command string already failed
        if tool_name == "terminal_command" and "command" in args:
            cmd = args["command"].strip()
            
            # Check if this exact command has already failed
            for failed in failed_commands:
                if failed.get("tool") == "terminal_command" and failed.get("args", {}).get("command", "").strip() == cmd:
                    console.print(f"[yellow]Warning: Detected repeated failed command: {cmd}[/yellow]")
                    return True
                    
        return False
    
    def process_streaming_response(
        self, chunk: Dict[str, Any], accumulated_content: str = "", accumulated_tool_calls: Union[List[Dict], Dict] = None
    ) -> Dict[str, Any]:
        """
        Process a streaming response chunk from the LLM.
        
        Args:
            chunk: The chunk response from the LLM
            accumulated_content: The content accumulated so far
            accumulated_tool_calls: The tool calls accumulated so far (can be list or dict)
        
        Returns:
            dict: A dictionary containing new content and tool calls.
                Example: {"type": "content", "content": "new_content", "full_content": "accumulated_content"}
                OR: {"type": "tool_calls", "tool_calls": [tool_call_dict], "content": ""}
        """
        # Initialize accumulated_tool_calls if not provided
        if accumulated_tool_calls is None:
            accumulated_tool_calls = {}
        
        # Convert list to dict if needed for backward compatibility
        if isinstance(accumulated_tool_calls, list):
            tool_calls_dict = {}
            for tc in accumulated_tool_calls:
                if isinstance(tc, dict) and 'id' in tc:
                    tool_calls_dict[tc['id']] = tc
            accumulated_tool_calls = tool_calls_dict
            
        # Function to validate and extract tool call information
        def validate_tool_call(tool_call):
            call_id = None
            function_name = None
            function_args = None
            
            # Check if it's an object with function attribute
            if hasattr(tool_call, 'function'):
                # Get the call ID if available
                call_id = getattr(tool_call, 'id', None)
                call_index = getattr(tool_call, 'index', 0)
                
                # Get function name
                if hasattr(tool_call.function, 'name'):
                    function_name = getattr(tool_call.function, 'name', '')
                
                # Get function arguments
                if hasattr(tool_call.function, 'arguments'):
                    function_args = getattr(tool_call.function, 'arguments', '')
                    
            # Check if it's a dictionary with a function key
            elif isinstance(tool_call, dict):
                # Get the call ID if available
                call_id = tool_call.get('id')
                call_index = tool_call.get('index', 0)
                
                # Get function info
                function = tool_call.get('function', {})
                if isinstance(function, dict):
                    function_name = function.get('name', '')
                    function_args = function.get('arguments', '')
            
            return call_id, call_index, function_name, function_args
        
        # Check if this is a LiteLLM streaming callback event
        if hasattr(chunk, "choices") and chunk.choices:
            # Extract LiteLLM streaming chunk (compatible with streaming callbacks)
            delta = chunk.choices[0].delta

            # Log details about the streaming chunk for debugging
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                self.logger.debug(f"LiteLLM streaming chunk contains tool calls: {delta.tool_calls}")
                
                for tc in delta.tool_calls:
                    call_id = getattr(tc, 'id', 'unknown')
                    function_name = getattr(getattr(tc, 'function', {}), 'name', 'unknown')
                    function_args = getattr(getattr(tc, 'function', {}), 'arguments', '{}')
                    self.logger.debug(f"Tool call: id={call_id}, name={function_name}")
                    self.logger.debug(f"Arguments: {function_args}")

            # Handle tool calls in the delta (if any)
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                new_tool_calls = []
                
                # Convert to list if not already
                delta_tool_calls = delta.tool_calls
                if not isinstance(delta_tool_calls, list):
                    delta_tool_calls = [delta_tool_calls]
                
                for tc in delta_tool_calls:
                    # Extract tool call info without validation
                    call_id, call_index, function_name, function_args = validate_tool_call(tc)
                    
                    # Generate a UUID if the call ID is missing
                    if call_id is None:
                        import uuid
                        call_id = str(uuid.uuid4())
                        self.logger.debug(f"Generated call ID for tool call: {call_id}")
                    
                    # Check if this call ID already exists in the accumulated tool calls
                    if call_id in accumulated_tool_calls:
                        # Update the existing tool call with new information
                        existing_tc = accumulated_tool_calls[call_id]
                        
                        # Ensure function dict exists
                        if 'function' not in existing_tc:
                            existing_tc['function'] = {}
                        
                        # Update function name if provided
                        if function_name:
                            existing_tc['function']['name'] = function_name
                        
                        # Update or append to function arguments if provided
                        if function_args:
                            if 'arguments' not in existing_tc['function']:
                                existing_tc['function']['arguments'] = function_args
                            else:
                                # Append to existing arguments - crucial for streaming
                                existing_tc['function']['arguments'] += function_args
                        
                        # Add to new tool calls list
                        new_tool_calls.append(existing_tc)
                    else:
                        # Create a new tool call
                        new_tc = {
                            "id": call_id,
                            "type": "function",
                            "index": call_index,
                            "function": {}
                        }
                        
                        # Add function name if available
                        if function_name:
                            new_tc["function"]["name"] = function_name
                        
                        # Add function arguments if available
                        if function_args:
                            new_tc["function"]["arguments"] = function_args
                        
                        # Add to accumulated tool calls
                        accumulated_tool_calls[call_id] = new_tc
                        
                        # Add to new tool calls list
                        new_tool_calls.append(new_tc)
                
                # Log the complete state of tool calls for debugging
                for tc_id, tc in accumulated_tool_calls.items():
                    has_name = 'function' in tc and 'name' in tc['function'] and tc['function']['name']
                    has_args = 'function' in tc and 'arguments' in tc['function']
                    self.logger.debug(f"Accumulated tool call {tc_id}: has_name={has_name}, has_args={has_args}")
                    if has_args:
                        self.logger.debug(f"Arguments: {tc['function'].get('arguments', '')}")
                
                if new_tool_calls:
                    self.logger.debug(f"Returning tool call chunk with {len(new_tool_calls)} calls. Total accumulated: {len(accumulated_tool_calls)}")
                    
                    # Check if any tool call is complete enough to be processed
                    complete_tool_calls = []
                    for tc in new_tool_calls:
                        # Consider a tool call complete if it has both a name and arguments
                        if ('function' in tc and 
                            'name' in tc['function'] and 
                            tc['function']['name'] and
                            'arguments' in tc['function']):
                            complete_tool_calls.append(tc)
                    
                    # If there are complete tool calls, return those
                    # Otherwise return all tool calls as they may be partial
                    tool_calls_to_return = complete_tool_calls if complete_tool_calls else new_tool_calls
                    
                    return {
                        "type": "tool_calls",
                        "tool_calls": tool_calls_to_return,
                        "content": "",
                        "full_content": accumulated_content,
                        "accumulated_tool_calls": accumulated_tool_calls
                    }
            
            # Handle delta content if it exists
            if hasattr(delta, "content") and delta.content is not None:
                new_content = delta.content
                new_full_content = accumulated_content + new_content
                
                return {
                    "type": "content",
                    "content": new_content,
                    "full_content": new_full_content,
                    "accumulated_tool_calls": accumulated_tool_calls
                }
        
        # Handle direct content in the chunk (non-LiteLLM format)
        new_content = chunk.get("content", "")
        new_full_content = accumulated_content + new_content

        # Check for tool_calls in the direct chunk format
        tool_calls = chunk.get("tool_calls", [])
        if tool_calls:
            # Process tool calls
            new_tool_calls = []
            
            # Convert to list if not already
            if not isinstance(tool_calls, list):
                tool_calls = [tool_calls]
            
            for tc in tool_calls:
                # Extract tool call info (accept partial info)
                call_id, call_index, function_name, function_args = validate_tool_call(tc)
                
                # Generate a UUID if the call ID is missing
                if call_id is None:
                    import uuid
                    call_id = str(uuid.uuid4())
                    self.logger.debug(f"Generated call ID for direct tool call: {call_id}")
                
                # Check if this call ID already exists in the accumulated tool calls
                if call_id in accumulated_tool_calls:
                    # Update the existing tool call with new information
                    existing_tc = accumulated_tool_calls[call_id]
                    
                    # Ensure function dict exists
                    if 'function' not in existing_tc:
                        existing_tc['function'] = {}
                    
                    # Update function name if provided
                    if function_name:
                        existing_tc['function']['name'] = function_name
                    
                    # Update or append to function arguments if provided
                    if function_args:
                        if 'arguments' not in existing_tc['function']:
                            existing_tc['function']['arguments'] = function_args
                        else:
                            # Append to existing arguments - crucial for streaming
                            existing_tc['function']['arguments'] += function_args
                    
                    # Add to new tool calls list
                    new_tool_calls.append(existing_tc)
                else:
                    # Create a new tool call
                    new_tc = {
                        "id": call_id,
                        "type": "function",
                        "function": {}
                    }
                    
                    # Add function name if available
                    if function_name:
                        new_tc["function"]["name"] = function_name
                    
                    # Add function arguments if available
                    if function_args:
                        new_tc["function"]["arguments"] = function_args
                    
                    # Add to accumulated tool calls
                    accumulated_tool_calls[call_id] = new_tc
                    
                    # Add to new tool calls list
                    new_tool_calls.append(new_tc)
            
            # Log the complete state of tool calls for debugging
            for tc_id, tc in accumulated_tool_calls.items():
                has_name = 'function' in tc and 'name' in tc['function'] and tc['function']['name']
                has_args = 'function' in tc and 'arguments' in tc['function']
                self.logger.debug(f"Accumulated tool call {tc_id}: has_name={has_name}, has_args={has_args}")
                if has_args:
                    self.logger.debug(f"Arguments: {tc['function'].get('arguments', '')}")
            
            if new_tool_calls:
                # Check if any tool call is complete enough to be processed
                complete_tool_calls = []
                for tc in new_tool_calls:
                    # Consider a tool call complete if it has both a name and arguments
                    if ('function' in tc and 
                        'name' in tc['function'] and 
                        tc['function']['name'] and
                        'arguments' in tc['function']):
                        complete_tool_calls.append(tc)
                
                # If there are complete tool calls, return those
                # Otherwise return all tool calls as they may be partial
                tool_calls_to_return = complete_tool_calls if complete_tool_calls else new_tool_calls
                
                return {
                    "type": "tool_calls",
                    "tool_calls": tool_calls_to_return,
                    "content": "",
                    "full_content": new_full_content,
                    "accumulated_tool_calls": accumulated_tool_calls
                }
        
        # Return content update if nothing else matched
        return {
            "type": "content",
            "content": new_content,
            "full_content": new_full_content,
            "accumulated_tool_calls": accumulated_tool_calls
        }
    
    def get_completion(
        self, 
        messages, 
        stream=False, 
        stream_callback=None, 
        tools=None, 
        tool_choice=None
    ):
        """
        Get a completion from the LLM.
        
        Args:
            messages: List of message objects to send to the LLM
            stream: Whether to stream the response
            stream_callback: Callback function for streaming responses
            tools: Optional tools to provide to the LLM
            tool_choice: Optional tool choice parameter
            
        Returns:
            Dict containing the completion response with content and tool_calls
        """
        model = self.provider_config.model
        self.logger.debug(f"Getting completion from model: {model}")
        
        # Check if we need to add a provider prefix to the model name
        if self.provider_config.provider == "openai" and self.provider_config.base_url:
            # For custom OpenAI-compatible APIs like LM Studio, we need to prefix the model
            if self.provider_name == "lm_studio":
                model = f"openai/{model}"
        
        self.logger.debug(f"Using full model identifier: {model}")
        
        # Get temperature and max_tokens with defaults
        temperature = getattr(self.provider_config, "temperature", 0.7)
        max_tokens = getattr(self.provider_config, "max_tokens", None)
        
        # If the provider doesn't support tool calls, remove the tools parameter
        if tools and not self.supports_tool_calling():
            self.logger.warning(f"Model {model} is not recognized as supporting tool calling according to LiteLLM. Ignoring tools.")
            console.print(f"[yellow]Warning: Model {model} is not recognized as supporting tool calling. Try manually adding it to the known_tool_capable_models list in llm_provider.py if you believe this is incorrect.[/yellow]")
            tools = None
            tool_choice = None
        
        try:
            # Get API parameters
            api_params = self._get_api_params()
            
            # For streaming responses
            if stream and stream_callback:
                # Create a custom callback class to avoid serialization issues
                class StreamProcessor:
                    def __init__(self, callback_fn, logger):
                        self.callback_fn = callback_fn
                        self.accumulated_content = ""
                        self.accumulated_tool_calls = {}  # Use dict with call ID as key for better tracking
                        self.logger = logger
                    
                    def _is_valid_tool_call(self, tool_call, allow_partial=True):
                        """
                        Validate if a tool call has the necessary information.
                        
                        Args:
                            tool_call: The tool call object to validate
                            allow_partial: Whether to allow partial tool calls during streaming
                            
                        Returns:
                            tuple: (is_valid, call_id, function_name, function_args)
                        """
                        call_id = None
                        function_name = None
                        function_args = None
                        
                        # Check if it's an object with function attribute
                        if hasattr(tool_call, 'function'):
                            # Get the call ID if available
                            call_id = getattr(tool_call, 'id', None)
                            
                            # Get function name
                            if hasattr(tool_call.function, 'name'):
                                function_name = getattr(tool_call.function, 'name', '')
                            
                            # Get function arguments
                            if hasattr(tool_call.function, 'arguments'):
                                function_args = getattr(tool_call.function, 'arguments', '')
                                
                        # Check if it's a dictionary with a function key
                        elif isinstance(tool_call, dict):
                            # Get the call ID if available
                            call_id = tool_call.get('id')
                            
                            # Get function info
                            function = tool_call.get('function', {})
                            if isinstance(function, dict):
                                function_name = function.get('name', '')
                                function_args = function.get('arguments', '')
                        
                        # For non-streaming, require complete data
                        if not allow_partial:
                            if not call_id or not function_name:
                                return False, None, None, None
                        
                        # For streaming, we can accumulate partial info
                        # Only completely reject if we have no usable information
                        if call_id is None and function_name is None and function_args is None:
                            return False, None, None, None
                        
                        return True, call_id, function_name, function_args
                        
                    def process_chunk(self, chunk_data):
                        try:
                            # Extract content and tool calls
                            content = None
                            tool_calls = None
                            
                            # Access the delta content
                            if hasattr(chunk_data, 'choices') and chunk_data.choices:
                                choice = chunk_data.choices[0]
                                if hasattr(choice, 'delta'):
                                    delta = choice.delta
                                    content = getattr(delta, 'content', None)
                                    tool_calls = getattr(delta, 'tool_calls', None)
                                    
                                    # Add detailed logging for tool calls to help debug
                                    if tool_calls:
                                        self.logger.debug(f"Raw tool_calls type: {type(tool_calls)}")
                                        self.logger.debug(f"Raw tool_calls: {tool_calls}")
                                        
                                        # Log each tool call individually
                                        if isinstance(tool_calls, list):
                                            for i, tc in enumerate(tool_calls):
                                                self.logger.debug(f"Tool call {i} type: {type(tc)}")
                                                self.logger.debug(f"Tool call {i} attributes: {dir(tc) if hasattr(tc, '__dict__') else 'No attributes'}")
                                                
                                                # Check for function attribute
                                                if hasattr(tc, 'function'):
                                                    self.logger.debug(f"Function name: {getattr(tc.function, 'name', 'No name')}")
                                                    self.logger.debug(f"Function arguments: {getattr(tc.function, 'arguments', 'No arguments')}")
                            
                            # If we got content, update accumulated content
                            if content:
                                self.accumulated_content += content
                            
                            # If we got new tool calls, add them to our accumulated tool calls
                            if tool_calls:
                                # Log the raw tool call for debugging
                                self.logger.debug(f"Raw tool call received: {str(tool_calls)}")
                                
                                # LiteLLM may provide tool calls in various formats, handle them properly
                                try:
                                    # Process tool calls as a list or individual item
                                    tc_list = tool_calls if isinstance(tool_calls, list) else [tool_calls]
                                    
                                    for tc in tc_list:
                                        # Validate and extract tool call info
                                        is_valid, call_id, function_name, function_args = self._is_valid_tool_call(tc, allow_partial=True)
                                        
                                        if not is_valid:
                                            self.logger.warning(f"Skipping invalid tool call: {tc}")
                                            continue
                                            
                                        # Generate a call ID if none exists
                                        if call_id is None:
                                            import uuid
                                            call_id = str(uuid.uuid4())
                                            self.logger.debug(f"Generated call_id for tool call: {call_id}")
                                        
                                        # Check if we already have this call ID
                                        if call_id in self.accumulated_tool_calls:
                                            # Update existing tool call with new info
                                            existing_tc = self.accumulated_tool_calls[call_id]
                                            
                                            # Update function name if provided
                                            if function_name and not existing_tc.get('function', {}).get('name'):
                                                if 'function' not in existing_tc:
                                                    existing_tc['function'] = {}
                                                existing_tc['function']['name'] = function_name
                                                
                                            # Append to function arguments if provided
                                            if function_args:
                                                if 'function' not in existing_tc:
                                                    existing_tc['function'] = {}
                                                
                                                existing_args = existing_tc['function'].get('arguments', '')
                                                existing_tc['function']['arguments'] = existing_args + function_args
                                        else:
                                            # Create a new tool call entry
                                            new_tc = {
                                                'id': call_id,
                                                'type': 'function',
                                                'function': {}
                                            }
                                            
                                            # Add function name if available
                                            if function_name:
                                                new_tc['function']['name'] = function_name
                                                
                                            # Add function arguments if available
                                            if function_args:
                                                new_tc['function']['arguments'] = function_args
                                                
                                            # Store the new tool call
                                            self.accumulated_tool_calls[call_id] = new_tc
                                            
                                except Exception as e:
                                    self.logger.error(f"Error accumulating tool calls: {str(e)}")
                                    import traceback
                                    self.logger.debug(traceback.format_exc())
                            
                            # Create callback data
                            complete_tool_calls = list(self.accumulated_tool_calls.values())
                            
                            # Filter for tool calls that have complete data (both name and arguments)
                            ready_tool_calls = []
                            for tc in complete_tool_calls:
                                tc_function = tc.get('function', {})
                                if tc_function.get('name') and tc_function.get('arguments', '') != '':
                                    ready_tool_calls.append(tc)
                            
                            # Determine callback type based on what's available in this chunk
                            callback_type = "unknown"
                            if content is not None:
                                callback_type = "content"
                            elif tool_calls is not None:
                                callback_type = "tool_calls"
                            
                            callback_data = {
                                "type": callback_type,
                                "content": content or "",
                                "full_content": self.accumulated_content,
                                "tool_calls": ready_tool_calls
                            }
                            
                            # Call the callback
                            self.callback_fn(callback_data)
                        except Exception as e:
                            # Log error but don't crash
                            self.logger.error(f"Error processing chunk: {str(e)}")
                            print(f"Error processing chunk: {str(e)}")
                
                # Create the processor
                processor = StreamProcessor(stream_callback, self.logger)
                
                try:
                    # Use a simpler approach without stream_options or callbacks in the API call
                    response = litellm.completion(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=True,
                        tools=tools,
                        tool_choice=tool_choice,
                        **api_params
                    )
                    
                    # Process each chunk manually
                    for chunk in response:
                        processor.process_chunk(chunk)
                    
                    # Return accumulated content and tool calls
                    return {
                        "content": processor.accumulated_content,
                        "tool_calls": list(processor.accumulated_tool_calls.values())
                    }
                    
                except Exception as e:
                    self.logger.error(f"Streaming error: {str(e)}")
                    console.print(f"[yellow]Streaming failed, falling back to non-streaming mode: {str(e)}[/yellow]")
                    
                    # Try again with non-streaming as a fallback
                    try:
                        response = litellm.completion(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            stream=False,
                            tools=tools,
                            tool_choice=tool_choice,
                            **api_params
                        )
                        
                        # Extract the content and tool calls from the response
                        content = response.choices[0].message.content or ""
                        tool_calls = getattr(response.choices[0].message, "tool_calls", [])
                        
                        # Sanitize the content to remove any raw function calls
                        sanitized_content = self._sanitize_response_content(content)
                        
                        return {
                            "content": sanitized_content,
                            "tool_calls": tool_calls
                        }
                    except Exception as fallback_error:
                        self.logger.error(f"Fallback also failed: {str(fallback_error)}")
                        return {
                            "content": f"Error: Unable to get a response from the LLM. {str(e)}",
                            "tool_calls": []
                        }
            
            # For non-streaming responses
            response = litellm.completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                tools=tools,
                tool_choice=tool_choice,
                **api_params
            )
            
            # Extract the content and tool calls from the response
            content = response.choices[0].message.content or ""
            tool_calls = getattr(response.choices[0].message, "tool_calls", [])
            
            # Sanitize the content to remove any raw function calls
            sanitized_content = self._sanitize_response_content(content)
            
            return {
                "content": sanitized_content,
                "tool_calls": tool_calls
            }
            
        except Exception as e:
            error_message = f"Error during LLM completion: {str(e)}"
            self.logger.error(error_message)
            
            # For debugging, log more details about the model and parameters
            self.logger.debug(f"Model: {model}")
            self.logger.debug(f"Provider: {self.provider_config.provider}")
            self.logger.debug(f"Base URL: {self.provider_config.base_url}")
            
            # Check if API key is set (don't log the actual key)
            if self.provider_config.api_key:
                self.logger.debug("API Key: [Set]")
            else:
                self.logger.debug("API Key: [Not Set]")
            
            return {
                "content": f"Error: Unable to get a response from the LLM. {str(e)}",
                "tool_calls": []
            }

    async def get_token_count(self, text: str) -> int:
        """
        Get an estimate of the number of tokens in the text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated token count
        """
        try:
            # Run the potentially blocking token counting in a thread pool
            loop = asyncio.get_event_loop()
            
            # Use LiteLLM's token counting function if available
            if hasattr(litellm, "token_counter"):
                return await loop.run_in_executor(
                    None, 
                    partial(
                        litellm.token_counter,
                        model=self.provider_config.model,
                        messages=[{"role": "user", "content": text}]
                    )
                )
            
            # Fallback to a simple approximation (1 token ≈ 4 characters for English text)
            return len(text) // 4
        
        except Exception as e:
            console.print(f"[yellow]Warning: Error counting tokens:[/yellow] {str(e)}")
            # Fallback to a simple approximation
            return len(text) // 4


def get_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """
    Get an LLM provider instance.
    
    Args:
        provider_name: Name of the provider to use
        
    Returns:
        LLMProvider instance
    """
    return LLMProvider(provider_name) 