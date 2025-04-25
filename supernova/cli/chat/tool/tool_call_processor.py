"""
Tool call processor for chat sessions.

This module contains the ToolCallProcessor class for processing tool calls.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from supernova.cli.chat.domain.models import ToolCall, ToolResult


class ToolCallProcessor:
    """
    Processes tool calls from the LLM.
    
    Handles extracting, validating, and executing tool calls.
    """
    
    def __init__(self, tool_manager=None, config=None):
        """
        Initialize the tool call processor.
        
        Args:
            tool_manager: Tool manager for executing tools
            config: Configuration object
        """
        self.logger = logging.getLogger("supernova.chat.tool_processor")
        self.tool_manager = tool_manager
        self.config = config
        self.max_iterations = 5  # Default value
        
        if config and hasattr(config, "max_tool_iterations"):
            try:
                self.max_iterations = config.max_tool_iterations
            except Exception:
                pass
    
    def process_llm_response(self, response: Any) -> Dict[str, Any]:
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
                
                # Try to get tool_calls directly
                if "tool_calls" in response:
                    tool_calls = response["tool_calls"]
                # Try to get tool_calls from choices[0].message.tool_calls
                elif "choices" in response and len(response["choices"]) > 0:
                    choice = response["choices"][0]
                    if isinstance(choice, dict) and "message" in choice:
                        message = choice["message"]
                        if isinstance(message, dict) and "tool_calls" in message:
                            tool_calls = message["tool_calls"]
                
                # Ensure tool_calls is a list
                if tool_calls:
                    if not isinstance(tool_calls, list):
                        tool_calls = [tool_calls]
                    processed["tool_calls"] = tool_calls
            
            # Handle object-style responses (e.g., OpenAI's response objects)
            elif hasattr(response, "choices") and hasattr(response.choices, "__getitem__"):
                try:
                    # Get the first choice
                    choice = response.choices[0]
                    
                    # Extract message content
                    if hasattr(choice, "message"):
                        if hasattr(choice.message, "content") and choice.message.content:
                            processed["content"] = choice.message.content
                        
                        # Extract tool calls if available
                        if hasattr(choice.message, "tool_calls"):
                            tool_calls = choice.message.tool_calls
                            if tool_calls:
                                # Keep original tool_calls objects (ChatCompletionMessageToolCall)
                                # Do not convert them to dictionaries
                                if not isinstance(tool_calls, list):
                                    tool_calls = [tool_calls]
                                processed["tool_calls"] = tool_calls
                except (IndexError, AttributeError) as e:
                    self.logger.warning(f"Error extracting from choices: {e}")
            
            # Handle simpler response objects
            elif hasattr(response, "content"):
                processed["content"] = response.content
                
                # Extract tool calls if available
                if hasattr(response, "tool_calls"):
                    tool_calls = response.tool_calls
                    if tool_calls:
                        # Keep original tool_calls objects
                        if not isinstance(tool_calls, list):
                            tool_calls = [tool_calls]
                        processed["tool_calls"] = tool_calls
        
            # Note: No regex-based extraction of tool calls from content 
            # Only using standard tool calling API
        
        except Exception as e:
            self.logger.error(f"Error processing LLM response: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            processed["error"] = str(e)
        
        # Ensure content is a string
        if processed["content"] is None:
            processed["content"] = ""
        elif not isinstance(processed["content"], str):
            processed["content"] = str(processed["content"])
            
        # Log the processed response for debugging (without tool calls details which might be large)
        self.logger.debug(f"Processed response content: {processed['content'][:50]}{'...' if len(processed['content']) > 50 else ''}")
        self.logger.debug(f"Found {len(processed['tool_calls'])} tool calls")
        
        return processed
    
    def convert_tool_call_to_dict(self, tool_call: Any) -> Dict[str, Any]:
        """
        Convert a tool call object to a dictionary for consistent processing.
        
        Args:
            tool_call: The tool call object, which might be a dict or another type
            
        Returns:
            A dictionary representing the tool call
        """
        # If already a dict, use it directly
        if isinstance(tool_call, dict):
            return tool_call
            
        # Otherwise, try to convert to dict based on common formats
        result = {}
        
        # Handle OpenAI style tool calls
        if hasattr(tool_call, 'function'):
            function_info = {}
            if hasattr(tool_call.function, 'name'):
                function_info['name'] = tool_call.function.name
            if hasattr(tool_call.function, 'arguments'):
                try:
                    # Try to parse JSON arguments
                    function_info['arguments'] = json.loads(tool_call.function.arguments)
                except:
                    # Fall back to string if can't parse
                    function_info['arguments'] = tool_call.function.arguments
                    
            result['function'] = function_info
            
        # Include ID if available
        if hasattr(tool_call, 'id'):
            result['id'] = tool_call.id
            
        return result
    
    def verify_tool_exists(self, tool_name: str) -> bool:
        """
        Verify that a tool exists and is available for use.
        
        Args:
            tool_name: Name of the tool to verify
            
        Returns:
            True if the tool exists, False otherwise
        """
        if not self.tool_manager:
            return False
            
        return self.tool_manager.has_tool(tool_name)
    
    def handle_tool_call(
        self, 
        tool_call: Dict[str, Any], 
        session_state: Dict[str, Any],
        seen_call_ids: Optional[Set[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Handle a tool call.
        
        Args:
            tool_call: The tool call dict from the LLM
            session_state: Current session state
            seen_call_ids: Set of tool call IDs that have already been processed
            
        Returns:
            Optional[Dict]: The result of the tool call or None if the tool is not found
        """
        # Initialize seen_call_ids if not provided
        if seen_call_ids is None:
            seen_call_ids = set()
            
        # Skip if we've already processed this tool call
        call_id = tool_call.get('id')
        if call_id and call_id in seen_call_ids:
            self.logger.debug(f"Skipping already processed tool call: {call_id}")
            return None
            
        # Add to seen calls if ID exists
        if call_id:
            seen_call_ids.add(call_id)
        
        # Check if function data is present
        if 'function' not in tool_call:
            self.logger.warning(f"Missing function data in tool call: {json.dumps(tool_call)}")
            return {
                "error": "incomplete_tool_call",
                "message": "No function data provided in tool call"
            }
        
        # Get function details
        function_data = tool_call['function']
        
        # Check if function has a name
        if 'name' not in function_data or not function_data['name']:
            self.logger.warning(f"No tool name provided in tool call: {json.dumps(tool_call)}")
            return {
                "error": "incomplete_tool_call",
                "message": "No tool name provided in tool call"
            }
        
        tool_name = function_data['name']
        
        # Verify the tool exists
        if not self.verify_tool_exists(tool_name):
            self.logger.warning(f"Unknown tool: {tool_name}")
            return {
                "error": "unknown_tool",
                "message": f"Unknown tool: {tool_name}",
                "tool_name": tool_name
            }
        
        # Parse function arguments
        function_args = '{}'
        if 'arguments' in function_data:
            function_args = function_data['arguments']
            
        # Parse function arguments as JSON if they're a string
        parsed_args = {}
        if isinstance(function_args, str):
            try:
                # Try to parse potentially incomplete JSON
                function_args = function_args.strip()
                
                # If it's completely empty, use empty dict
                if not function_args:
                    parsed_args = {}
                else:
                    # Handle common streaming artifacts
                    if function_args.endswith(','):
                        function_args = function_args[:-1]
                        
                    # Try to parse as JSON
                    parsed_args = json.loads(function_args)
            except json.JSONDecodeError as e:
                self.logger.warning(f"Failed to parse tool arguments as JSON: {function_args}. Error: {str(e)}")
                return {
                    "error": "invalid_arguments",
                    "message": f"Invalid arguments format: {str(e)}",
                    "tool_name": tool_name
                }
        else:
            # Already a dict
            parsed_args = function_args
        
        # Get the tool function
        tool_function = self.tool_manager.get_tool_handler(tool_name)
        
        if not tool_function:
            self.logger.warning(f"Unknown tool: {tool_name}")
            return {
                "error": "unknown_tool",
                "message": f"Unknown tool: {tool_name}",
                "tool_name": tool_name
            }
        
        try:
            # Execute the tool function
            self.logger.debug(f"Executing tool {tool_name} with args: {parsed_args}")
            
            # Add session_state to kwargs - the tool handler expects named arguments only
            kwargs = parsed_args.copy()
            kwargs['session_state'] = session_state
            
            # Call the function with kwargs only, no positional args
            result = tool_function(**kwargs)
            
            return {
                "result": result,
                "tool_name": tool_name,
                "success": result.get("success", False) if isinstance(result, dict) else False,
                "tool_call_id": call_id,
                "command": parsed_args.get("command")
            }
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {
                "error": "execution_error",
                "message": f"Error executing {tool_name}: {str(e)}",
                "tool_name": tool_name,
                "success": False
            }
    
    def handle_terminal_command(
        self, 
        args: Dict[str, Any], 
        session_state_manager
    ) -> Dict[str, Any]:
        """
        Handle a terminal command with special handling for directory changes.
        
        Args:
            args: Arguments for the terminal command
            session_state_manager: Session state manager
            
        Returns:
            Dictionary with result information
        """
        if "command" not in args:
            return {
                "success": False,
                "error": "No command provided"
            }
            
        command = args.get("command", "").strip()
        
        # Handle cd command specially
        if command.startswith("cd "):
            try:
                # Extract the target directory
                target_dir = command[3:].strip()
                
                # Get current working directory
                current_dir = session_state_manager.current_directory
                
                # Handle special cases
                if target_dir == "..":
                    # Go up one level
                    new_dir = current_dir.parent
                elif target_dir == "~":
                    # Go to home directory
                    new_dir = Path.home()
                elif target_dir.startswith("~/"):
                    # Go to path relative to home
                    new_dir = Path.home() / target_dir[2:]
                elif target_dir == "-":
                    # Go to previous directory (if available)
                    if len(session_state_manager._state.path_history) > 1:
                        # Get the previous directory from history
                        new_dir = Path(session_state_manager._state.path_history[-2])
                    else:
                        return {
                            "success": False,
                            "error": "No previous directory in history",
                            "current_dir": str(current_dir)
                        }
                elif target_dir.startswith("/"):
                    # Absolute path
                    new_dir = Path(target_dir)
                else:
                    # Relative path
                    new_dir = current_dir / target_dir
                
                # Update the directory using the session state manager
                return session_state_manager.update_current_directory(new_dir)
                
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error changing directory: {str(e)}"
                }
        else:
            # For other commands, use the command_runner
            try:
                from supernova.core import command_runner
                result = command_runner.run_command(command, cwd=session_state_manager._state.cwd)
                
                # Check if the command succeeded
                success = result.get("exit_code", 1) == 0
                
                # Format result for return
                return {
                    "success": success,
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "exit_code": result.get("exit_code", 1),
                    "command": command
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error executing command: {str(e)}",
                    "command": command
                }
    
    def process_tool_call_loop(
        self, 
        llm_response: Dict[str, Any], 
        session_state: Dict[str, Any],
        session_state_manager,
        message_manager,
        get_llm_response_callback
    ) -> Dict[str, Any]:
        """
        Process a continuous loop of tool calls from the LLM.
        
        This method executes a loop where:
        1. Tool calls are extracted from the LLM response
        2. Tools are executed
        3. Results are fed back to the LLM
        4. This continues until there are no more tool calls
        
        Args:
            llm_response: The raw response from the LLM
            session_state: Current session state
            session_state_manager: Session state manager
            message_manager: Message manager
            get_llm_response_callback: Callback to get the next LLM response
            
        Returns:
            A dictionary containing the final response after all tool calls
        """
        # Extract tool calls from initial response
        processed_response = self.process_llm_response(llm_response)
        tool_calls = processed_response.get("tool_calls", []) if isinstance(processed_response, dict) else []
        
        # Initialize variables
        iteration_count = 0
        response = llm_response
        processed_next = None  # Initialize processed_next
        
        # Track processed call IDs to avoid duplicates
        processed_call_ids = set()
        
        # Process tool calls in a loop until there are no more or we hit the limit
        while tool_calls and iteration_count < self.max_iterations:
            iteration_count += 1
            self.logger.debug(f"Tool call iteration {iteration_count}/{self.max_iterations}")
            self.logger.debug(f"Processing {len(tool_calls)} tool calls")
            
            # Process each tool call
            tool_results = []
            tool_messages = []
            invalid_tool_names = []
            
            # Pre-filter tool calls to check for invalid tools
            filtered_tool_calls = []
            for tc in tool_calls:
                # Extract the tool name and call ID
                tool_name = None
                call_id = None
                
                if isinstance(tc, dict):
                    if 'function' in tc and 'name' in tc['function']:
                        tool_name = tc['function']['name']
                    call_id = tc.get('id')
                elif hasattr(tc, 'function') and hasattr(tc.function, 'name'):
                    tool_name = tc.function.name
                    call_id = tc.id if hasattr(tc, 'id') else None
                
                # Skip if we've already processed this call ID
                if call_id and call_id in processed_call_ids:
                    self.logger.debug(f"Skipping already processed tool call: {call_id}")
                    continue
                
                # Record tool call in the message manager
                if tool_name and call_id:
                    # Extract arguments
                    args = None
                    if isinstance(tc, dict) and 'function' in tc and 'arguments' in tc['function']:
                        args = tc['function']['arguments']
                    elif hasattr(tc, 'function') and hasattr(tc.function, 'arguments'):
                        args = tc.function.arguments
                    
                    message_manager.add_tool_call_message(tool_name, args, call_id)
                
                # Verify the tool exists
                if tool_name and not self.verify_tool_exists(tool_name):
                    invalid_tool_names.append(tool_name)
                    # Add an error message for this invalid tool
                    tool_results.append({
                        "tool_name": tool_name,
                        "success": False,
                        "error": "unknown_tool",
                        "tool_call_id": call_id
                    })
                    # Add tool message with error
                    tool_messages.append({
                        "role": "tool",
                        "content": f"Error executing tool {tool_name}: unknown_tool",
                        "name": tool_name,
                        "tool_call_id": call_id
                    })
                    
                    # Mark as processed
                    if call_id:
                        processed_call_ids.add(call_id)
                else:
                    # Tool exists or we couldn't determine its name, let handle_tool_call deal with it
                    filtered_tool_calls.append(tc)
            
            # Log invalid tools
            if invalid_tool_names:
                self.logger.warning(f"Found {len(invalid_tool_names)} invalid tool calls: {', '.join(invalid_tool_names)}")
            
            # Process the filtered tool calls
            for tc in filtered_tool_calls:
                # Convert to standardized dictionary format
                tc_dict = self.convert_tool_call_to_dict(tc)
                
                # Handle different types of tool call objects
                if 'function' not in tc_dict:
                    self.logger.warning(f"Invalid tool call missing function: {tc_dict}")
                    continue
                
                tc_function = tc_dict.get('function', {})
                if 'name' not in tc_function:
                    self.logger.warning(f"Invalid tool call missing function name: {tc_dict}")
                    continue
                
                tool_name = tc_function.get('name', '')
                args = tc_function.get('arguments', {})
                call_id = tc_dict.get('id', 'unknown')
                
                # Skip if we've already processed this call ID
                if call_id in processed_call_ids:
                    self.logger.debug(f"Skipping already processed tool call: {call_id}")
                    continue
                
                # Mark this call ID as processed
                processed_call_ids.add(call_id)
                
                # Show info about the tool call
                self.logger.debug(f"Processing tool call: {tool_name} with ID {call_id}")
                
                # For cd commands, we need to update the directory
                if tool_name == "terminal_command" or tool_name == "run_terminal_cmd":
                    # Handle terminal command (with special handling for cd)
                    command = args.get("command", "")
                    
                    # Check if this is a cd command
                    if command.strip().startswith("cd "):
                        # Handle cd command by updating the working directory
                        result = self.handle_terminal_command(args, session_state_manager)
                        
                        # Update the session state with the command result
                        session_state["LAST_ACTION"] = "terminal_command"
                        session_state["LAST_ACTION_ARGS"] = args
                        session_state["LAST_ACTION_RESULT"] = result
                        
                        # Create a summary of the command result for the LLM
                        if isinstance(result, dict) and result.get("success"):
                            if "current_dir" in result:
                                tool_msg = f"Current directory is now: {result['current_dir']}"
                            else:
                                tool_msg = f"Command executed successfully: {command}"
                        else:
                            err = result.get("error", "unknown error") if isinstance(result, dict) else "unknown error"
                            tool_msg = f"Error executing command: {err}"
                        
                        # Add to tool messages
                        tool_messages.append({
                            "role": "tool",
                            "content": tool_msg,
                            "tool_call_id": call_id,
                            "name": tool_name
                        })
                        
                        # Add to tool results
                        tool_results.append({
                            "tool_name": tool_name,
                            "success": result.get("success", False) if isinstance(result, dict) else False,
                            "result": result,
                            "tool_call_id": call_id
                        })
                    else:
                        # Handle other terminal commands normally
                        result = self.handle_tool_call(tc_dict, session_state)
                        
                        if result:
                            # Add to tool results
                            tool_results.append(result)
                            
                            # Create tool message
                            success = result.get("success", False) if isinstance(result, dict) else False
                            if success:
                                content = f"Command executed successfully: {command}"
                                if "stdout" in result and result["stdout"]:
                                    content += f"\nOutput:\n{result['stdout']}"
                            else:
                                error = result.get("result", str(result)).get("stderr",str(result)) if isinstance(result, dict) else "unknown error"
                                content = f"Error executing command: {error}"
                                
                            tool_messages.append({
                                "role": "tool",
                                "content": content,
                                "tool_call_id": call_id,
                                "name": tool_name
                            })
                else:
                    # Handle other types of tools
                    result = self.handle_tool_call(tc_dict, session_state)
                    
                    if result:
                        # Add to tool results
                        tool_results.append(result)
                        
                        # Create tool message
                        if isinstance(result, dict):
                            success = result.get("success", False)
                            error = result.get("error", None)
                            
                            if success:
                                content = f"Tool {tool_name} executed successfully"
                                if "result" in result:
                                    # For complex results, format them nicely
                                    try:
                                        if isinstance(result['result'], dict):
                                            formatted_result = json.dumps(result['result'], indent=2)
                                        elif isinstance(result['result'], list):
                                            formatted_result = json.dumps(result['result'], indent=2)
                                        else:
                                            formatted_result = str(result['result'])
                                        content += f"\nResult: {formatted_result}"
                                    except Exception:
                                        content += f"\nResult: {str(result['result'])}"
                            else:
                                content = f"Error executing tool {tool_name}: {error or 'unknown error'}"
                        else:
                            content = f"Tool {tool_name} returned: {result}"
                            
                        tool_messages.append({
                            "role": "tool",
                            "content": content,
                            "tool_call_id": call_id,
                            "name": tool_name
                        })
            
            # Add tool results to message manager
            if tool_results:
                message_manager.add_tool_summary_message(tool_results)
                
                # If we have tool messages, send them back to LLM
                if tool_messages:
                    # Get the LLM response using the callback
                    next_response = get_llm_response_callback()
                    
                    # Process the response
                    processed_next = self.process_llm_response(next_response)
                    
                    # Update the main content if there is any
                    if isinstance(processed_next, dict) and "content" in processed_next:
                        processed_response["content"] = processed_next["content"]
                    
                    # Update response for next iteration
                    response = next_response
            
            # Get the tool calls for the next iteration
            tool_calls = []  # Default to empty list
            if processed_next is not None and isinstance(processed_next, dict) and "tool_calls" in processed_next:
                tool_calls = processed_next.get("tool_calls", [])
                # Ensure tool_calls is a list
                if tool_calls is None:
                    tool_calls = []
                elif not isinstance(tool_calls, list):
                    tool_calls = [tool_calls]
        
        # Create a complete response
        final_response = processed_response
        final_response["iteration_count"] = iteration_count
        
        return final_response 