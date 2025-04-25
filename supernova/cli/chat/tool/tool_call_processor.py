"""
Tool call processor for chat sessions.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from rich.console import Console
from supernova.cli.ui_utils import theme_color, display_tool_execution
from supernova.cli.chat.message.message_models import ToolResult

console = Console()

class ToolCallProcessor:
    """
    Processes tool calls from the LLM.
    """
    def __init__(self, tool_manager, llm_provider, config=None):
        """
        Initialize the tool call processor.
        
        Args:
            tool_manager: Tool manager
            llm_provider: LLM provider
            config: Configuration object
        """
        self.tool_manager = tool_manager
        self.llm_provider = llm_provider
        self.config = config
        self.logger = logging.getLogger("supernova.tool_call_processor")
        
    def process_llm_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the raw response from the LLM.
        
        Args:
            response: Raw response from the LLM
            
        Returns:
            Processed response
        """
        # Initialize variables
        processed_response = {}
        
        # Ensure response is a dictionary
        if not isinstance(response, dict):
            self.logger.warning(f"Expected dict response, got {type(response)}")
            if hasattr(response, 'content'):
                processed_response["content"] = response.content
            elif hasattr(response, 'choices') and response.choices:
                processed_response["content"] = response.choices[0].message.content or ""
            else:
                processed_response["content"] = str(response)
        else:
            # Copy the response
            processed_response = response.copy()
            
        # Ensure content is a string
        if "content" in processed_response and processed_response["content"] is None:
            processed_response["content"] = ""
            
        # Ensure tool_calls is a list
        if "tool_calls" in processed_response:
            tc = processed_response["tool_calls"]
            if not isinstance(tc, list):
                processed_response["tool_calls"] = [tc]
                
        return processed_response
        
    def process_tool_call_loop(
        self, 
        llm_response: Dict[str, Any], 
        session_state: Dict[str, Any],
        message_manager,
        prompt_generator
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
            message_manager: Message manager
            prompt_generator: Prompt generator
            
        Returns:
            A dictionary containing the final response after all tool calls
        """
        # Initialize variables
        processed_response = self.process_llm_response(llm_response)
        tool_calls = processed_response.get("tool_calls", []) if isinstance(processed_response, dict) else []
        
        # Get max iterations from config with a default of 5
        max_iterations = 5  # Default value
        try:
            # Try to get from config if available
            if hasattr(self.config, "max_tool_iterations"):
                max_iterations = self.config.max_tool_iterations
        except Exception:
            # If there's an error, use the default
            pass
            
        iteration_count = 0
        response = llm_response
        processed_next = None  # Initialize processed_next
        
        # Track processed call IDs to avoid duplicates
        processed_call_ids = set()
        
        # Process tool calls in a loop until there are no more or we hit the limit
        while tool_calls and iteration_count < max_iterations:
            iteration_count += 1
            self.logger.debug(f"Tool call iteration {iteration_count}/{max_iterations}")
            self.logger.debug(f"Processing {len(tool_calls)} tool calls")
            
            # Display iteration info if verbose
            debug_show_tool_iterations = False
            try:
                if hasattr(self.config, "debug") and hasattr(self.config.debug, "show_tool_iterations"):
                    debug_show_tool_iterations = self.config.debug.show_tool_iterations
            except Exception:
                # If there's an error, use the default
                pass
                
            if debug_show_tool_iterations:
                console.print(f"\n[dim][Tool step {iteration_count}/{max_iterations}][/dim]")
            
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
                    continue
                    
                # Check if the tool exists
                if tool_name and not self.tool_manager.has_tool(tool_name):
                    invalid_tool_names.append(tool_name)
                    continue
                    
                # Add to filtered list
                filtered_tool_calls.append(tc)
                
                # Add to processed call IDs
                if call_id:
                    processed_call_ids.add(call_id)
            
            # If there are invalid tools, report them
            if invalid_tool_names:
                invalid_tools_str = ", ".join(invalid_tool_names)
                console.print(f"[{theme_color('warning')}]⚠️ LLM attempted to use invalid tools: {invalid_tools_str}[/{theme_color('warning')}]")
                
                # Add a system message about invalid tools
                message_manager.add_message(
                    role="system",
                    content=f"⚠️ Invalid tool(s) requested: {invalid_tools_str}. These tools are not available."
                )
            
            # If no valid tool calls, break the loop
            if not filtered_tool_calls:
                break
                
            # Process each valid tool call
            for tc in filtered_tool_calls:
                # Extract tool details
                tool_name = None
                tool_args = {}
                call_id = None
                
                if isinstance(tc, dict):
                    if 'function' in tc:
                        if 'name' in tc['function']:
                            tool_name = tc['function']['name']
                        if 'arguments' in tc['function']:
                            args = tc['function']['arguments']
                            if isinstance(args, str):
                                try:
                                    import json
                                    tool_args = json.loads(args)
                                except Exception as e:
                                    self.logger.error(f"Failed to parse tool arguments: {e}")
                                    tool_args = {"raw_args": args}
                            else:
                                tool_args = args
                    call_id = tc.get('id', '')
                elif hasattr(tc, 'function'):
                    if hasattr(tc.function, 'name'):
                        tool_name = tc.function.name
                    if hasattr(tc.function, 'arguments'):
                        args = tc.function.arguments
                        if isinstance(args, str):
                            try:
                                import json
                                tool_args = json.loads(args)
                            except Exception as e:
                                self.logger.error(f"Failed to parse tool arguments: {e}")
                                tool_args = {"raw_args": args}
                        else:
                            tool_args = args
                    call_id = tc.id if hasattr(tc, 'id') else ''
                
                # Skip if no tool name
                if not tool_name:
                    continue
                    
                # Execute the tool
                display_tool_execution(tool_name, tool_args)
                try:
                    # Execute the tool
                    result = self.tool_manager.execute_tool(
                        tool_name, 
                        tool_args,
                        session_state=session_state
                    )
                    
                    # Create tool result
                    tool_result = ToolResult(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        success=True,
                        result=result,
                        tool_call_id=call_id
                    )
                        
                    # Special handling for terminal_command tool
                    if tool_name == "terminal_command" and isinstance(tool_args, dict):
                        command = tool_args.get("command", "")
                        if command.startswith("cd "):
                            # Update session state with new working directory
                            new_dir = result.get("new_directory")
                            if new_dir:
                                session_state["cwd"] = new_dir
                                
                                # Add to path history if not already there
                                if new_dir not in session_state["path_history"]:
                                    session_state["path_history"].append(new_dir)
                except Exception as e:
                    # Create error tool result
                    tool_result = ToolResult(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        success=False,
                        error=str(e),
                        tool_call_id=call_id
                    )
                        
                # Add tool result to list
                tool_results.append(tool_result)
                
                # Add tool result message
                message = message_manager.add_tool_result_message(tool_result)
                tool_messages.append(message.to_dict())
                
                # Add to session state
                session_state["used_tools"].append({
                    "name": tool_name,
                    "args": tool_args,
                    "success": tool_result.success,
                    "timestamp": tool_result.timestamp
                })
                
                # Add to executed commands if it's a terminal command
                if tool_name == "terminal_command" and isinstance(tool_args, dict):
                    command = tool_args.get("command", "")
                    if command:
                        session_state["executed_commands"].append({
                            "command": command,
                            "success": tool_result.success,
                            "timestamp": tool_result.timestamp
                        })
            
            # If no tool results, break the loop
            if not tool_results:
                break
                
            # Generate context message with updated state
            context_msg = prompt_generator.generate_context_message(session_state)
            
            # Generate system prompt
            system_prompt = prompt_generator.generate_system_prompt(session_state)
            
            # Format messages for the LLM
            formatted_messages, tools, tool_choice = prompt_generator.format_messages_for_llm(
                content="", 
                system_prompt=system_prompt,
                context_msg=context_msg,
                previous_messages=message_manager.get_messages(),
                include_tools=True,
                session_state=session_state
            )
            
            # Add a message to indicate tool results are being processed
            formatted_messages.append({
                "role": "system",
                "content": f"I've executed {len(tool_results)} tool(s) based on your request. Please continue helping the user based on these results."
            })
            
            # Get next response from LLM
            next_response = self.llm_provider.get_completion(
                messages=formatted_messages,
                tools=tools,
                stream=False
            )
            
            # Process the next response
            processed_next = self.process_llm_response(next_response)
            
            # Update response and tool calls for next iteration
            response = next_response
            tool_calls = processed_next.get("tool_calls", []) if isinstance(processed_next, dict) else []
            
        # Return the final response
        return response