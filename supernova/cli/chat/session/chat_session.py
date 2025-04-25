"""
SuperNova - AI-powered development assistant within the terminal.

Chat session for interactive AI assistance.
"""

import os
import time
import logging
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from rich.console import Console

from supernova.config import loader
from supernova.core import context_analyzer, llm_provider, tool_manager
from supernova.cli.ui_utils import theme_color
from supernova.cli.chat.message.message_manager import MessageManager
from supernova.cli.chat.session.session_state import SessionState
from supernova.cli.chat.prompt.prompt_generator import PromptGenerator
from supernova.cli.chat.tool.tool_call_processor import ToolCallProcessor
from supernova.cli.chat.ui.chat_ui import ChatUI

console = Console()

class ChatSession:
    """Interactive chat session with the AI assistant."""
    
    def __init__(self, config=None, db=None, initial_directory=None):
        """
        Initialize the chat session with the given configuration.
        
        Args:
            config: Configuration object
            db: Database manager
            initial_directory: Initial working directory
        """
        # Load configuration if not provided
        self.config = config or loader.load_config()
        
        # Initialize logger
        self.logger = logging.getLogger("supernova.chat_session")
        
        # Set up initial directory (current directory if not specified)
        self.initial_directory = Path(initial_directory or os.getcwd())
        
        # Token allocation constants
        self.max_tokens = 4096  # Default max tokens
        self.llm_token_allocation_constants = {
            "PROMPT_OVERHEAD": 0.2,  # 20% reserved for overhead
            "SYSTEM_MESSAGE": 0.5,   # 50% of remaining tokens for system message
            "CONTEXT": 0.2,          # 20% of remaining tokens for context
            "HISTORY": 0.3           # 30% of remaining tokens for chat history
        }
        
        # If config has token allocation settings, use those
        if hasattr(self.config, "token_allocation"):
            if hasattr(self.config.token_allocation, "max_tokens"):
                self.max_tokens = self.config.token_allocation.max_tokens
            if hasattr(self.config.token_allocation, "constants"):
                token_constants = self.config.token_allocation.constants
                for key, value in token_constants.items():
                    if key in self.llm_token_allocation_constants:
                        self.llm_token_allocation_constants[key] = value
        
        # Create .supernova directory in the working directory
        local_supernova_dir = self.initial_directory / ".supernova"
        local_supernova_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up database
        if db is not None:
            self.db = db
        else:
            db_path = local_supernova_dir / "history.db"
            from supernova.persistence.db_manager import DatabaseManager
            self.db = DatabaseManager(db_path)
        
        # Initialize session state
        self.session_state = SessionState(self.initial_directory)
        
        # Get the LLM provider
        self.llm_provider = llm_provider.get_provider()
        
        # Get the tool manager
        self.tool_manager = tool_manager.ToolManager()
        
        # Initialize other components
        self.tool_manager.load_extension_tools()
        
        # Initialize message manager
        self.message_manager = MessageManager(self.db)
        
        # Initialize prompt generator
        self.prompt_generator = PromptGenerator(
            self.config,
            self.tool_manager,
            self.llm_token_allocation_constants,
            self.max_tokens
        )
        
        # Initialize tool call processor
        self.tool_call_processor = ToolCallProcessor(
            self.tool_manager,
            self.llm_provider,
            self.config
        )
        
        # Setup prompt session with history
        history_file = self.initial_directory / ".supernova" / "prompt_history"
        self.prompt_session = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=WordCompleter(["exit", "quit"]),
            style=Style.from_dict({
                "prompt": "ansicyan bold",
            })
        )
        
        # Initialize UI
        self.ui = ChatUI(self.prompt_session)
        
        # Initialize streaming state variables
        self._tool_calls_reported = False
        self._streaming_started = False
        self._latest_full_content = ""
        self._latest_tool_calls = []
        
        # Reset streaming state to ensure all required variables are initialized
        self._reset_streaming_state()
        
        # Display welcome message
        self.ui.display_welcome_message(
            str(self.session_state.get_cwd()),
            str(self.session_state.get_initial_directory())
        )
    
    def _reset_streaming_state(self):
        """Reset the streaming state variables."""
        self._tool_calls_reported = False
        self._streaming_started = False
        self._latest_full_content = ""
        self._latest_tool_calls = []
        
    def analyze_project(self) -> str:
        """
        Analyze the project context with enhanced UI.
        
        Returns:
            Summary of the project
        """
        try:
            # Display progress messages sequentially to avoid nested live displays
            console.print(f"[{theme_color('primary')}]Scanning files...[/{theme_color('primary')}]")
            time.sleep(0.3)  # Simulate work
            
            console.print(f"[{theme_color('primary')}]Identifying project type...[/{theme_color('primary')}]")
            time.sleep(0.3)  # Simulate work
            
            console.print(f"[{theme_color('primary')}]Finalizing analysis...[/{theme_color('primary')}]")
            
            # Actual project analysis
            project_summary = context_analyzer.analyze_project(self.session_state.get_cwd())
            self.session_state.set_project_summary(project_summary)
            
            # Display success message with animation
            self.ui.display_project_analysis_result(project_summary)
            
            return project_summary
        except Exception as e:
            error_msg = f"Could not analyze project: {str(e)}"
            self.session_state.set_project_error(error_msg)
            
            # Display error with animation
            self.ui.display_project_analysis_error(error_msg)
            
            return "Unknown project"
    
    def load_or_create_chat(self) -> None:
        """Load the latest chat for the project or create a new one with enhanced UI."""
        if not self.db.enabled:
            return
        
        # Display progress messages sequentially to avoid nested live displays
        console.print(f"[{theme_color('secondary')}]Initializing chat session...[/{theme_color('secondary')}]")
        time.sleep(0.3)  # Brief pause for effect
        
        # Get the latest chat for this project
        self.message_manager.chat_id = self.db.get_latest_chat_for_project(self.session_state.get_cwd())
        
        if self.message_manager.chat_id:
            # Load existing chat with animation
            console.print(f"[{theme_color('secondary')}]Loading previous chat history...[/{theme_color('secondary')}]")
            
            # Load messages from database
            self.message_manager.load_messages_from_db(self.message_manager.chat_id)
            
            # Get message count
            message_count = len(self.message_manager.get_messages())
            console.print(f"[{theme_color('secondary')}]Loading {message_count} messages...[/{theme_color('secondary')}]")
            
            # Display success message with animation
            self.ui.display_chat_loaded(message_count)
            
            # Update session state
            self.session_state.set_loaded_previous_chat(True, message_count)
        else:
            # Create a new chat with animation
            console.print(f"[{theme_color('secondary')}]Creating new chat session...[/{theme_color('secondary')}]")
            
            # Create new chat
            self.message_manager.chat_id = self.db.create_chat(self.session_state.get_cwd())
            
            # Add system message
            system_prompt = self.prompt_generator.generate_system_prompt(
                self.session_state.get_state(),
                cli_args={},
                is_initial_prompt=True
            )
            self.message_manager.add_message("system", system_prompt)
            
            # Display success message with animation
            self.ui.display_new_chat_created()
            
            # Update session state
            self.session_state.set_loaded_previous_chat(False)
    
    def get_llm_response(self) -> Dict[str, Any]:
        """
        Get a response from the LLM based on the current messages.
        
        Returns:
            A dictionary containing the LLM's response and any tool calls
        """
        try:
            # Get context message
            context_msg = self.prompt_generator.generate_context_message(self.session_state.get_state())
            
            # Generate system prompt
            system_prompt = self.prompt_generator.generate_system_prompt(self.session_state.get_state())
            
            # Format messages for the LLM
            formatted_messages, tools, tool_choice = self.prompt_generator.format_messages_for_llm(
                content="", 
                system_prompt=system_prompt,
                context_msg=context_msg,
                previous_messages=self.message_manager.get_messages(),
                include_tools=True,
                session_state=self.session_state.get_state()
            )
            
            # Display thinking animation
#            self.ui.display_thinking_animation()
            
            # Get LLM response
            response = self.llm_provider.get_completion(
                messages=formatted_messages,
                tools=tools,
                stream=False
            )
            
            # Process the response
            assistant_response = ""
            tool_calls = []
            
            # Ensure response is a dictionary
            if not isinstance(response, dict):
                self.logger.warning(f"Expected dict response from get_completion, got {type(response)}")
                if hasattr(response, 'content'):
                    assistant_response = response.content
                elif hasattr(response, 'choices') and response.choices:
                    assistant_response = response.choices[0].message.content or ""
                else:
                    assistant_response = str(response)
            else:
                # Extract assistant response and tool calls
                if "content" in response:
                    assistant_response = response["content"]
                elif "assistant_response" in response:
                    assistant_response = response["assistant_response"]
                
                # Extract tool calls if available
                if "tool_calls" in response:
                    tc = response["tool_calls"]
                    # Ensure tool_calls is a list
                    if tc:
                        if isinstance(tc, list):
                            tool_calls = tc
                        else:
                            tool_calls = [tc]
            
            # Create the response dictionary
            result = {
                "content": assistant_response,
                "tool_calls": tool_calls
            }
            
            return result
        except Exception as e:
            self.logger.error(f"Error getting LLM response: {e}")
            return {"error": str(e)}
    
    def run_chat_loop(self, initial_user_input=None, auto_run=False):
        """
        Run the chat loop with enhanced UI.
        
        Args:
            initial_user_input: Initial input from the user
            auto_run: Whether to auto-run the initial input
        """
        try:
            # Load or create chat session
            self.load_or_create_chat()
            
            # Initialize variables
            keep_running = True
            first_message = True
            
            # Run the chat loop
            while keep_running:
                try:
                    # Get user input if not provided
                    if initial_user_input and first_message:
                        user_input = initial_user_input
                        first_message = False
                    else:
                        user_input = self.ui.get_user_input()
                    
                    # Check for exit commands
                    if user_input.lower() in ["exit", "quit"]:
                        self.ui.display_exiting()
                        break
                    
                    # Add user message to chat history
                    self.message_manager.add_message("user", user_input)
                    
                    # Get response from LLM
                    response = self.get_llm_response()
                    
                    # Process the response
                    if "error" in response:
                        self.ui.display_error(response["error"])
                    else:
                        # Process content
                        content = response.get("content", "")
                        if content:
                            self.message_manager.add_message("assistant", content)
                            self.ui.display_response(content)
                        
                        # Process tool calls
                        tool_calls = response.get("tool_calls")
                        if tool_calls:
                            # Process tool calls in a loop until there are no more
                            final_response = self.tool_call_processor.process_tool_call_loop(
                                response,
                                self.session_state.get_state(),
                                self.message_manager,
                                self.prompt_generator
                            )
                            
                            # Add final response to chat history
                            if final_response.get("content"):
                                self.message_manager.add_message("assistant", final_response["content"])
                                self.ui.display_response(final_response["content"])
                
                except KeyboardInterrupt:
                    console.print(f"[{theme_color('warning')}]Operation interrupted[/{theme_color('warning')}]")
                    
                except Exception as e:
                    console.print(f"[{theme_color('error')}]Error in chat loop: {str(e)}[/{theme_color('error')}]")
                    traceback.print_exc()
        
        except Exception as e:
            console.print(f"[{theme_color('error')}]Error in chat loop: {str(e)}[/{theme_color('error')}]")
            traceback.print_exc()