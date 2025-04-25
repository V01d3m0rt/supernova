"""
SuperNova - AI-powered development assistant within the terminal.

Chat Session - Main class for interactive chat sessions.
"""

import os
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rich.console import Console
from rich.markdown import Markdown
import logging

from supernova.cli.chat.session.session_state import SessionStateManager
from supernova.core.tool_manager import get_manager
from supernova.core.llm_provider import get_provider

# Set up logging
logger = logging.getLogger(__name__)
console = Console()

class ChatSession:
    """
    Main chat session class for SuperNova.
    
    This class manages the interactive chat session, handling:
    - User input and command processing
    - Tool execution and result reporting
    - Session state management
    - Chat history
    """
    
    def __init__(self, initial_directory: Optional[Union[str, Path]] = None):
        """
        Initialize a new chat session.
        
        Args:
            initial_directory: Optional directory to start the chat in, defaults to current working directory
        """
        self.session_state = SessionStateManager(initial_directory)
        self.tool_manager = get_manager()
        self.llm_provider = get_provider()
        
        # Set up initial state
        self.is_running = False
        self.message_history = []
        
        logger.info(f"Chat session initialized in {self.session_state.current_directory}")
    
    def run_chat_loop(self):
        """
        Run the main chat loop.
        
        This method starts the interactive chat session and processes user input
        until the user exits the session.
        """
        self.is_running = True
        
        # Display welcome message
        self._display_welcome_message()
        
        try:
            # Main chat loop
            while self.is_running:
                # Get user input
                user_input = console.input("[bold blue]> [/bold blue]")
                
                # Process user input (simplified for now)
                if user_input.lower() in ("exit", "quit", ":q"):
                    self.is_running = False
                    console.print("[green]Exiting chat session...[/green]")
                    break
                
                # Process the user input
                asyncio.run(self._process_user_input_async(user_input))
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Chat session interrupted.[/yellow]")
        except Exception as e:
            logger.error(f"Error in chat loop: {str(e)}")
            console.print(f"[red]Error in chat session:[/red] {str(e)}")
        finally:
            self.is_running = False
            console.print("[green]Chat session ended.[/green]")
    
    def _display_welcome_message(self):
        """Display the welcome message for the chat session."""
        welcome_message = """
# SuperNova Chat

Welcome to SuperNova, your AI-powered development assistant!

- Type your questions or commands naturally
- Type 'exit' or ':q' to quit the session

Current working directory: {cwd}
        """.format(cwd=self.session_state.current_directory)
        
        console.print(Markdown(welcome_message))
    
    async def _process_user_input_async(self, user_input: str):
        """
        Process user input and generate a response asynchronously.
        
        Args:
            user_input: The text input from the user
        """
        # Add the user message to history
        self.message_history.append({"role": "user", "content": user_input})
        
        # Get available tools for the LLM
        tools = self.tool_manager.get_available_tools_for_llm(self.session_state.state_dict)
        
        # Format conversation history for the LLM
        formatted_messages = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in self.message_history
        ]
        
        # Add system message with context
        system_message = {
            "role": "system",
            "content": (
                "You are SuperNova, an AI assistant integrated into the terminal.\n"
                f"Current working directory: {self.session_state.current_directory}\n"
                "Help the user with their development tasks by answering questions clearly and using tools when appropriate.\n"
                "When asked to create files or execute commands, use the terminal_command tool.\n"
                "For terminal_command, you MUST provide a complete command parameter with the exact command to execute.\n"
                "For example: {\"command\": \"echo Hello World\"}\n"
                "Always provide complete tool call arguments in a single message. Never split tool calls across multiple chunks."
            )
        }
        formatted_messages.insert(0, system_message)
        
        console.print()  # Add a new line before the response
        
        try:
            # Check if this input is likely to involve tool usage
            likely_tool_usage = any(term in user_input.lower() for term in 
                ["create", "file", "write", "run", "execute", "command", "script", "delete", "install"])
                
            # For commands likely to involve tools, use non-streaming to get complete tool calls
            if likely_tool_usage:
                console.print("[dim]Processing your request...[/dim]")
                response = await asyncio.to_thread(
                    self.llm_provider.get_completion,
                    messages=formatted_messages,
                    stream=False,
                    tools=tools
                )
                
                # Once we have the complete response, print it in chunks for a streaming-like experience
                if "content" in response and response["content"]:
                    content = response["content"]
                    chunk_size = 5  # Number of characters to print at once
                    for i in range(0, len(content), chunk_size):
                        console.print(content[i:i+chunk_size], end="")
                        await asyncio.sleep(0.001)  # Small pause to simulate streaming
            else:
                # For regular responses where tool usage is less likely, use streaming
                
                # Store all chunks to reconstruct complete tool calls if needed
                all_chunks = []
                
                # Custom streaming callback that stores chunks for later processing
                def stream_callback(data):
                    # Store the chunk for later processing
                    all_chunks.append(data)
                    
                    # Display content in real-time
                    content = data.get("content", "")
                    if content:
                        console.print(content, end="")
                
                # Get streaming response
                response = await asyncio.to_thread(
                    self.llm_provider.get_completion,
                    messages=formatted_messages,
                    stream=True,
                    stream_callback=stream_callback,
                    tools=tools
                )
                
                # Check if there were any tool calls in the response
                if response.get("tool_calls"):
                    # Log that we found tool calls in a streaming response
                    logger.debug(f"Found {len(response.get('tool_calls'))} tool calls in streaming response")
                    
                    # Validate each tool call
                    for tool_call in response.get("tool_calls", []):
                        func_info = tool_call.get("function", {})
                        name = func_info.get("name", "")
                        args = func_info.get("arguments", "")
                        
                        # Log tool call details
                        logger.debug(f"Tool call: {name}, Arguments: {args}")
                        
                        # Check for JSON parsing issues in the arguments
                        try:
                            if args:
                                json.loads(args)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in tool arguments: {args}")
                            # Try to complete the JSON if it's incomplete
                            if args.strip() and not args.strip().endswith("}"):
                                args += "}"
                                func_info["arguments"] = args
                                logger.debug(f"Attempted to fix JSON: {args}")
            
            # Debug output - let's see what the LLM is returning
            logger.debug(f"LLM Response: {json.dumps(response, default=str)}")
            
            # Process the LLM response
            processed_response = await self.process_llm_response(response)
            
            # Add the assistant's response to the message history
            self.message_history.append({
                "role": "assistant",
                "content": processed_response["content"]
            })
            
            # Execute any tool calls
            for tool_result in processed_response.get("tool_results", []):
                # Add the tool result to the session state
                self.session_state.add_used_tool(tool_result)
                
                # If the tool executed a command, add it to the command history
                if tool_result.get("name") == "terminal_command":
                    command = tool_result.get("args", {}).get("command")
                    if command:
                        self.session_state.add_executed_command(command)
            
            console.print()  # Add a new line after the response
            
        except Exception as e:
            logger.error(f"Error processing input: {str(e)}")
            console.print(f"\n[red]Error processing your input:[/red] {str(e)}")
    
    def _process_user_input(self, user_input: str):
        """
        Process user input and generate a response (synchronous wrapper).
        
        Args:
            user_input: The text input from the user
        """
        asyncio.run(self._process_user_input_async(user_input))
    
    async def process_llm_response(self, response: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process the response from the LLM.
        
        Args:
            response: The response from the LLM provider
            
        Returns:
            Processed response with content and tool results
        """
        # Initialize the processed response
        processed = {
            "content": "",
            "tool_results": []
        }
        
        try:
            # Add detailed debug logging to show response type and structure
            logger.debug(f"Processing response of type: {type(response)}")
            console.print(f"[dim]Response type: {type(response)}[/dim]")
            
            # Handle string responses
            if isinstance(response, str):
                processed["content"] = self.llm_provider._sanitize_response_content(response)
                return processed
            
            # Handle dictionary responses
            if isinstance(response, dict):
                # Log the response structure for debugging
                response_dump = json.dumps(response, default=lambda x: str(x) if not isinstance(x, (dict, list, str, int, float, bool, type(None))) else x)
                logger.debug(f"Response structure: {response_dump}")
                console.print(f"[dim]Response keys: {list(response.keys())}[/dim]")
                
                # Extract content - might be directly in response or in response["choices"][0]["message"]
                content = response.get("content", "")
                
                # Check for OpenAI-style response format
                if "choices" in response and len(response["choices"]) > 0:
                    console.print(f"[dim]Found choices in response[/dim]")
                    # Handle different choices formats (list or direct object)
                    choices = response["choices"]
                    if isinstance(choices, list) and len(choices) > 0:
                        first_choice = choices[0]
                        console.print(f"[dim]First choice type: {type(first_choice)}[/dim]")
                        console.print(f"[dim]First choice keys: {list(first_choice.keys()) if isinstance(first_choice, dict) else 'not a dict'}[/dim]")
                        
                        # Extract message from the first choice
                        if isinstance(first_choice, dict):
                            message = first_choice.get("message", {})
                            console.print(f"[dim]Message type: {type(message)}[/dim]")
                            console.print(f"[dim]Message keys: {list(message.keys()) if isinstance(message, dict) else 'not a dict'}[/dim]")
                            
                            if isinstance(message, dict):
                                # Get content from the message if available
                                if "content" in message and message["content"]:
                                    content = message["content"]
                                    console.print(f"[dim]Found content in message[/dim]")
                
                if content:
                    processed["content"] = self.llm_provider._sanitize_response_content(content)
                
                # Process tool calls from direct format
                tool_calls = response.get("tool_calls", [])
                console.print(f"[dim]Direct tool_calls: {len(tool_calls) if isinstance(tool_calls, list) else 'not a list'}[/dim]")
                
                # Check for tool calls in OpenAI-style format
                if "choices" in response and isinstance(response["choices"], list) and len(response["choices"]) > 0:
                    first_choice = response["choices"][0]
                    if isinstance(first_choice, dict):
                        message = first_choice.get("message", {})
                        if isinstance(message, dict) and "tool_calls" in message:
                            # Get tool calls from the message
                            message_tool_calls = message["tool_calls"]
                            console.print(f"[dim]Found tool_calls in message: {len(message_tool_calls) if isinstance(message_tool_calls, list) else 'not a list'}[/dim]")
                            
                            # Use these tool calls instead
                            tool_calls = message_tool_calls
                
                if tool_calls:
                    console.print(f"\n[dim]Tool calls received: {len(tool_calls) if isinstance(tool_calls, list) else 'not a list'}[/dim]")
                    
                    # Debug the entire tool_calls object
                    tool_calls_dump = json.dumps(tool_calls, default=lambda x: str(x) if not isinstance(x, (dict, list, str, int, float, bool, type(None))) else x)
                    logger.debug(f"Tool calls structure: {tool_calls_dump}")
                    
                    # Check if tool_calls is a list
                    if not isinstance(tool_calls, list):
                        console.print(f"[yellow]Tool calls is not a list but a {type(tool_calls)}[/yellow]")
                        # Try to convert to list if possible
                        if hasattr(tool_calls, '__iter__') and not isinstance(tool_calls, (str, dict)):
                            tool_calls = list(tool_calls)
                        else:
                            tool_calls = [tool_calls]
                    
                    for i, tool_call in enumerate(tool_calls):
                        console.print(f"[dim]Processing tool call {i+1} of type {type(tool_call)}[/dim]")
                        
                        # Convert litellm.types.utils.ChatCompletionMessageToolCall to dictionary
                        if not isinstance(tool_call, dict) and hasattr(tool_call, 'id') and hasattr(tool_call, 'function'):
                            # This is likely a litellm.types.utils.ChatCompletionMessageToolCall
                            converted_tool_call = {
                                "id": getattr(tool_call, 'id', ''),
                                "type": getattr(tool_call, 'type', 'function'),
                                "function": {}
                            }
                            
                            # Extract function information
                            function = getattr(tool_call, 'function', None)
                            if function:
                                converted_tool_call["function"] = {
                                    "name": getattr(function, 'name', ''),
                                    "arguments": getattr(function, 'arguments', '{}')
                                }
                            
                            tool_call = converted_tool_call
                            console.print(f"[dim]Converted tool call to dictionary: {json.dumps(tool_call)}[/dim]")
                        
                        # Only process valid tool calls
                        if not tool_call or not isinstance(tool_call, dict):
                            console.print(f"[yellow]Invalid tool call format: {tool_call} (type: {type(tool_call)})[/yellow]")
                            continue
                        
                        # Debug output for tool call
                        tool_call_dump = json.dumps(tool_call, default=lambda x: str(x) if not isinstance(x, (dict, list, str, int, float, bool, type(None))) else x)
                        logger.debug(f"Tool call: {tool_call_dump}")
                        console.print(f"[dim]Tool call keys: {list(tool_call.keys())}[/dim]")
                        
                        # Try to fix any incomplete tool calls before processing
                        fixed_tool_call = self._fix_tool_call_if_needed(tool_call)
                        
                        # Execute the tool and get the result
                        tool_result = await self.handle_tool_call(fixed_tool_call)
                        if tool_result:
                            processed["tool_results"].append(tool_result)
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing LLM response: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            processed["content"] = f"Error processing the assistant's response: {str(e)}"
            return processed
    
    def _fix_tool_call_if_needed(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempt to fix incomplete tool calls.
        
        Args:
            tool_call: The original tool call
            
        Returns:
            Fixed tool call or original if no fixes needed
        """
        # Make a copy to avoid modifying the original
        fixed_call = tool_call.copy()
        
        # Check if the function object exists
        if "function" not in fixed_call or not isinstance(fixed_call["function"], dict):
            logger.warning("Tool call missing function object")
            return fixed_call
        
        function_info = fixed_call["function"]
        
        # Check if the function name exists
        if "name" not in function_info or not function_info["name"]:
            logger.warning("Tool call missing function name")
            return fixed_call
        
        # Check if arguments exist
        if "arguments" not in function_info:
            logger.warning("Tool call missing arguments")
            function_info["arguments"] = "{}"
            return fixed_call
        
        # Try to parse the arguments JSON
        arguments_str = function_info["arguments"]
        try:
            json.loads(arguments_str)
            # JSON is valid, no fixes needed
            return fixed_call
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in tool arguments: {arguments_str}")
            
            # Try to fix common JSON errors
            fixed_args = arguments_str
            
            # Check for unclosed braces
            if arguments_str.count("{") > arguments_str.count("}"):
                fixed_args = fixed_args + "}"
            
            # Check for missing commas
            fixed_args = fixed_args.replace('""', '","')
            fixed_args = fixed_args.replace('":', '":')
            
            # Try the fixed JSON
            try:
                json.loads(fixed_args)
                logger.info(f"Successfully fixed JSON arguments: {fixed_args}")
                function_info["arguments"] = fixed_args
            except json.JSONDecodeError:
                # If we still can't parse it, just log the error
                logger.error(f"Could not fix JSON arguments: {arguments_str}")
        
        return fixed_call
    
    async def handle_tool_call(self, tool_call: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Handle a tool call from the LLM.
        
        Args:
            tool_call: Tool call information from the LLM
            
        Returns:
            Tool execution result or None if execution failed
        """
        try:
            # Extract tool information
            function_info = tool_call.get("function", {})
            tool_name = function_info.get("name")
            
            console.print(f"\n[bold cyan]Using tool:[/bold cyan] {tool_name}")
            
            # Handle different tool_call formats to support various LLM response formats
            # Log the full tool call for debugging
            logger.debug(f"Full tool call structure: {json.dumps(tool_call, default=str)}")
            
            # Validate that the tool exists
            if not tool_name or not self.tool_manager.has_tool(tool_name):
                logger.warning(f"Tool {tool_name} not found")
                console.print(f"[yellow]Tool {tool_name} not found[/yellow]")
                return None
            
            # Parse the arguments
            arguments_str = function_info.get("arguments", "{}")
            try:
                # Try to parse as JSON string
                if isinstance(arguments_str, str):
                    args = json.loads(arguments_str)
                # Handle case where arguments are already a dictionary
                elif isinstance(arguments_str, dict):
                    args = arguments_str
                else:
                    logger.error(f"Unexpected arguments type: {type(arguments_str)}")
                    console.print(f"[red]Unexpected arguments type:[/red] {type(arguments_str)}")
                    return None
                
                console.print(f"[dim]Arguments: {json.dumps(args, indent=2)}[/dim]")
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in tool arguments: {arguments_str}")
                console.print(f"[red]Invalid JSON in tool arguments:[/red] {arguments_str}")
                return None
            
            # Validate required arguments for terminal_command tool
            if tool_name == "terminal_command" and not args.get("command"):
                console.print("[red]Missing required argument: command[/red]")
                return {
                    "name": tool_name,
                    "success": False,
                    "error": "Missing required argument: command"
                }
            
            # Execute the tool
            result = self.tool_manager.execute_tool(
                tool_name=tool_name,
                args=args,
                session_state=self.session_state.state_dict,
                working_dir=self.session_state.current_directory
            )
            
            # Display the tool result
            if result.get("success"):
                console.print(f"[green]Tool execution successful[/green]")
            else:
                console.print(f"[yellow]Tool execution failed:[/yellow] {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error handling tool call: {str(e)}")
            console.print(f"[red]Error handling tool call:[/red] {str(e)}")
            return {
                "name": tool_call.get("function", {}).get("name", "unknown_tool"),
                "success": False,
                "error": f"Error handling tool call: {str(e)}"
            }
    
    async def send_to_llm(self, content: str) -> Dict[str, Any]:
        """
        Send a message to the LLM.
        
        Args:
            content: Message content to send
            
        Returns:
            LLM response
        """
        # Format the message
        messages = [{"role": "user", "content": content}]
        
        # Get the response from the LLM
        response = await asyncio.to_thread(
            self.llm_provider.get_completion,
            messages=messages
        )
        
        return response 