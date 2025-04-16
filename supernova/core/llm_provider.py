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
        "gemma-3", 
        "llama-3", 
        "claude-3", 
        "claude-3-5", 
        "grok",
        "mistral-large"
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
        
        # Parse the text for incorrectly formatted terminal command tool calls
        # Some models output terminal_command { "command": "..." } instead of using proper tool calling
        content = self._extract_tool_calls_from_text(content)
        
        # Clean up excessive whitespace and return
        return content.strip()
        
    def _extract_tool_calls_from_text(self, content: str) -> str:
        """
        Extract tool calls from text content.
        
        This handles cases where the model outputs tool calls as text instead of using
        the proper tool_calls format.
        
        Args:
            content: The content text
            
        Returns:
            Content with tool calls removed
        """
        # Check for terminal_command pattern in text (which should be a tool call)
        terminal_cmd_pattern = r'terminal_command\s*\{\s*"command"\s*:\s*"([^"]+)"(?:\s*,\s*"explanation"\s*:\s*"([^"]+)")?\s*\}'
        
        # Find all terminal command patterns in the text
        matches = re.findall(terminal_cmd_pattern, content)
        
        if matches:
            self.logger.debug(f"Found {len(matches)} terminal command patterns in text")
            console.print(f"[yellow]Warning: Found terminal command patterns in text that should be tool calls. This may indicate the LLM is not properly using tool calling.[/yellow]")
            
            # Replace each terminal command pattern with a placeholder
            for match in matches:
                cmd = match[0]
                explanation = match[1] if len(match) > 1 and match[1] else ""
                
                pattern = rf'terminal_command\s*\{{\s*"command"\s*:\s*"{re.escape(cmd)}"(?:\s*,\s*"explanation"\s*:\s*"{re.escape(explanation)}")?\s*\}}'
                replacement = f"[I would execute: `{cmd}`]"
                content = re.sub(pattern, replacement, content)
            
        # Check for other common tool calling patterns that should use proper API
        mvn_pattern = r'(?:execute|run|use)?\s*maven\s+(?:command|to)?\s*[\'"]?(mvn [^\'"\n]+)[\'"]?'
        matches = re.findall(mvn_pattern, content, re.IGNORECASE)
        
        if matches:
            for match in matches:
                cmd = match.strip()
                if cmd.startswith("mvn "):
                    replacement = f"[I would run Maven: `{cmd}`]"
                    content = content.replace(match, replacement)
                    console.print(f"[yellow]Warning: Found Maven command in text that should be a tool call: {cmd}[/yellow]")
        
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
    
    def process_streaming_response(self, chunk, accumulated_content="", accumulated_tool_calls=None):
        """
        Process a streaming response chunk from the LLM.
        
        Args:
            chunk: The response chunk from the LLM
            accumulated_content: The content accumulated so far
            accumulated_tool_calls: List of tool calls accumulated so far
            
        Returns:
            Dict with keys:
                - content: Any new content in this chunk
                - tool_calls: Any new tool calls in this chunk
        """
        # This function is kept for compatibility, but its functionality has been
        # replaced with direct use of LiteLLM's streaming callbacks
        if accumulated_tool_calls is None:
            accumulated_tool_calls = []
            
        result = {
            "content": "",
            "tool_calls": []
        }
        
        # Extract any content
        if hasattr(chunk, 'choices') and hasattr(chunk.choices[0], 'delta'):
            delta = chunk.choices[0].delta
            content = getattr(delta, 'content', '')
            if content:
                result["content"] = content
            
            # Extract any tool calls
            tool_calls = getattr(delta, 'tool_calls', [])
            if tool_calls:
                result["tool_calls"] = tool_calls
                
        return result
    
    async def get_completion(self, messages, stream=False, stream_callback=None, tools=None, tool_choice=None):
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
                # Use litellm's streaming with a custom callback
                loop = asyncio.get_event_loop()
                
                def handle_chunk(chunk):
                    nonlocal stream_callback
                    if hasattr(chunk, 'choices') and chunk.choices and hasattr(chunk.choices[0], 'delta'):
                        delta = chunk.choices[0].delta
                        content = getattr(delta, 'content', None)
                        tool_calls = getattr(delta, 'tool_calls', None)
                        
                        callback_data = {
                            "type": "content" if content else "tool_calls" if tool_calls else "unknown",
                            "content": content or "",
                            "tool_calls": tool_calls or []
                        }
                        
                        # Only call the callback if it's not a coroutine function
                        if not asyncio.iscoroutinefunction(stream_callback):
                            stream_callback(callback_data)
                
                # Create stream options
                stream_options = {"include_usage": False}
                
                # Run completion in executor to avoid blocking
                await loop.run_in_executor(
                    None,
                    partial(
                        litellm.completion,
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=True,
                        tools=tools,
                        tool_choice=tool_choice,
                        stream_options=stream_options,
                        callback=handle_chunk,
                        **api_params
                    )
                )
                
                # Return empty result - the streaming callback will handle output
                return {"content": "", "tool_calls": []}
            
            # For non-streaming responses, run in an executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(
                    litellm.completion,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False,
                    tools=tools,
                    tool_choice=tool_choice,
                    **api_params
                )
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