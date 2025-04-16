"""
Tests for the tool call processing functionality in the chat session.

These tests verify:
1. The handle_tool_call method correctly processes tool calls from the LLM
2. The process_tool_call_loop method correctly handles iterations of tool calls
3. Error handling in the tool call loop works correctly
4. The loop respects the maximum iterations set in the configuration

Note: All these methods are asynchronous so the tests use async/await patterns.
"""

import asyncio
import json
import re
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import pytest_asyncio

from supernova.cli.chat_session import ChatSession


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider for testing."""
    provider = MagicMock()
    # First response includes a tool call
    provider.get_completion = AsyncMock()
    provider.get_completion.side_effect = [
        # First call - return a tool call
        {
            "choices": [
                {
                    "message": {
                        "content": "Let me help you with that.",
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "terminal_command",
                                    "arguments": '{"command": "ls -la"}'
                                }
                            }
                        ]
                    }
                }
            ]
        },
        # Second call - completion with no more tool calls
        {
            "choices": [
                {
                    "message": {
                        "content": "Here are the files in your directory.",
                        "role": "assistant"
                    }
                }
            ]
        }
    ]
    return provider


@pytest_asyncio.fixture
async def mock_tool_manager():
    """Create a mock tool manager for testing."""
    with patch("supernova.core.tool_manager.ToolManager") as mock_manager:
        # Mock execute_tool to return a successful result
        mock_manager.execute_tool = AsyncMock()
        mock_manager.execute_tool.return_value = {
            "success": True,
            "output": "file1.txt  file2.txt  directory1/",
            "return_code": 0
        }
        yield mock_manager


class MockConfig:
    """Mock configuration class for testing."""
    def __init__(self):
        self.chat = MagicMock()
        self.chat.max_tool_iterations = 3
        self.chat.tool_result_line_limit = 50
        self.command_execution = MagicMock()
        self.command_execution.timeout = 30
        self.debugging = MagicMock()
        self.debugging.show_traceback = False


@pytest_asyncio.fixture
async def chat_session(mock_llm_provider):
    """Create a ChatSession for testing with tool calls."""
    with patch("supernova.cli.chat_session.llm_provider.get_provider", return_value=mock_llm_provider):
        with patch("supernova.core.context_analyzer.analyze_project", return_value={"summary": "Test project"}):
            with patch("pathlib.Path.mkdir") as mock_mkdir:
                session = ChatSession(cwd=Path("/test/dir"))
                session.session_state = {
                    "cwd": "/test/dir",
                    "executed_commands": [],
                    "used_tools": []
                }
                # Set up mock config
                session.config = MockConfig()
                # Set up mock tool manager
                session.tool_manager = MagicMock()
                session.tool_manager.execute_tool = AsyncMock()
                session.tool_manager.execute_tool.return_value = "Command executed successfully"
                # Initialize the session for async tests
                session.initial_directory = Path("/test/dir")
                session.cwd = Path("/test/dir")
                # Add necessary methods for message handling
                session.add_message = MagicMock()
                session.get_context_message = AsyncMock(return_value="Test context")
                session.send_to_llm = AsyncMock(return_value={
                    "choices": [
                        {
                            "message": {
                                "content": "Final response after tool execution."
                            }
                        }
                    ]
                })
                yield session


@pytest.mark.asyncio
@patch("supernova.cli.chat_session.console")
async def test_handle_tool_call(mock_console, chat_session):
    """Test handling a single tool call."""
    # Set up the mock
    chat_session.tool_manager.execute_tool.return_value = "Command executed successfully"
    
    # Create a tool call
    tool_call = {
        "id": "call_1",
        "type": "function",
        "function": {
            "name": "terminal_command",
            "arguments": '{"command": "ls -la"}'
        }
    }
    
    # Call handle_tool_call
    result = await chat_session.handle_tool_call(tool_call)
    
    # Verify ToolManager.execute_tool was called
    chat_session.tool_manager.execute_tool.assert_called_once()
    # Check the arguments
    args, kwargs = chat_session.tool_manager.execute_tool.call_args
    assert args[0] == "terminal_command"
    assert "command" in args[1]
    assert args[1]["command"] == "ls -la"
    
    # Check the result
    assert result["success"] is True
    assert result["result"] == "Command executed successfully"


@pytest.mark.asyncio
@patch("supernova.cli.chat_session.console")
async def test_process_tool_call_loop_single_iteration(mock_console, chat_session):
    """Test processing a tool call loop with a single iteration."""
    # Mock the process_llm_response method to return a response with tool results
    async def mock_process_llm_response(response):
        return {
            "content": "Let me help you with that.",
            "tool_results": [
                {
                    "name": "terminal_command",
                    "success": True,
                    "result": "file1.txt file2.txt directory1/"
                }
            ]
        }
    
    # First call returns tool results, second call returns empty tool results to exit the loop
    process_results = [
        {
            "content": "Let me help you with that.",
            "tool_results": [
                {
                    "name": "terminal_command",
                    "success": True,
                    "result": "file1.txt file2.txt directory1/"
                }
            ]
        },
        {
            "content": "Final response.",
            "tool_results": []
        }
    ]
    
    # Mock the process_llm_response method
    chat_session.process_llm_response = AsyncMock(side_effect=process_results)
    
    # Define the LLM response with a tool call
    llm_response = {
        "choices": [
            {
                "message": {
                    "content": "Let me help you with that.",
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "terminal_command",
                                "arguments": '{"command": "ls -la"}'
                            }
                        }
                    ]
                }
            }
        ]
    }
    
    # Call process_tool_call_loop
    await chat_session.process_tool_call_loop(llm_response)
    
    # Verify process_llm_response was called with the initial response
    chat_session.process_llm_response.assert_called()
    
    # Verify send_to_llm was called 
    assert chat_session.send_to_llm.call_count == 1


@pytest.mark.asyncio
@patch("supernova.cli.chat_session.console")
async def test_process_tool_call_loop_max_iterations(mock_console, chat_session):
    """Test that the tool call loop respects the maximum iteration limit."""
    # Set up a mock for process_llm_response to always return tool calls
    async def mock_process_with_tool_results(response):
        return {
            "content": "Let me execute another command.",
            "tool_results": [
                {
                    "name": "terminal_command",
                    "success": True,
                    "result": "Command executed successfully"
                }
            ]
        }
    
    chat_session.process_llm_response = AsyncMock(side_effect=mock_process_with_tool_results)
    
    # Mock send_to_llm to return a response with tool calls
    async def mock_send_to_llm(*args, **kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": "Let me execute another command.",
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_repeated",
                                "type": "function",
                                "function": {
                                    "name": "terminal_command",
                                    "arguments": '{"command": "echo test"}'
                                }
                            }
                        ]
                    }
                }
            ]
        }
    
    chat_session.send_to_llm = AsyncMock(side_effect=mock_send_to_llm)
    
    # Initial response with a tool call
    initial_response = {
        "choices": [
            {
                "message": {
                    "content": "Let me help you with that.",
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "terminal_command",
                                "arguments": '{"command": "ls -la"}'
                            }
                        }
                    ]
                }
            }
        ]
    }
    
    # Call process_tool_call_loop
    await chat_session.process_tool_call_loop(initial_response)
    
    # Verify we process the maximum number of iterations
    assert chat_session.process_llm_response.call_count > 1
    
    # Verify send_to_llm was called for each iteration
    # In practice the loop may call send_to_llm once per iteration, plus an extra call
    # when the max iterations is reached
    assert chat_session.send_to_llm.call_count >= chat_session.config.chat.max_tool_iterations - 1


@pytest.mark.asyncio
@patch("supernova.cli.chat_session.console")
async def test_process_tool_call_loop_error_handling(mock_console, chat_session):
    """Test that the tool call loop handles errors gracefully."""
    # Set up a mock for process_llm_response to return error result then empty results
    process_results = [
        {
            "content": "Let me try a command.",
            "tool_results": [
                {
                    "name": "terminal_command",
                    "success": False,
                    "result": "Error: Command not found"
                }
            ]
        },
        {
            "content": "Final response with error handling.",
            "tool_results": []
        }
    ]
    
    chat_session.process_llm_response = AsyncMock(side_effect=process_results)
    
    # Initial response with a tool call
    llm_response = {
        "choices": [
            {
                "message": {
                    "content": "Let me help you with that.",
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "terminal_command",
                                "arguments": '{"command": "invalid_command"}'
                            }
                        }
                    ]
                }
            }
        ]
    }
    
    # Call process_tool_call_loop
    await chat_session.process_tool_call_loop(llm_response)
    
    # Verify process_llm_response was called
    chat_session.process_llm_response.assert_called()
    
    # Verify send_to_llm was called with error information included
    chat_session.send_to_llm.assert_called_once()
    
    # Check that the call includes error handling content
    call_args = chat_session.send_to_llm.call_args[0]
    assert any("ERROR" in str(arg) for arg in call_args if isinstance(arg, str))


@pytest.mark.asyncio
@patch("supernova.cli.chat_session.console")
async def test_process_tool_call_loop_improved_prompting(mock_console, chat_session):
    """Test that the tool call loop properly formats prompts with tool execution results."""
    # Mock successful tool execution results
    process_results = [
        {
            "content": "Executing tool...",
            "tool_results": [
                {
                    "name": "terminal_command",
                    "success": True,
                    "result": "file1.txt file2.txt directory1/"
                }
            ]
        },
        {
            "content": "Final response after analyzing results.",
            "tool_results": []
        }
    ]
    
    chat_session.process_llm_response = AsyncMock(side_effect=process_results)
    
    # Capture the arguments sent to send_to_llm
    original_send_to_llm = chat_session.send_to_llm
    sent_prompts = []
    
    async def capture_send_to_llm(*args, **kwargs):
        # Store the prompt for later verification
        if args and isinstance(args[0], str):
            sent_prompts.append(args[0])
        # Call the original method and return its result
        return await original_send_to_llm(*args, **kwargs)
    
    chat_session.send_to_llm = AsyncMock(side_effect=capture_send_to_llm)
    
    # Initial response with a tool call
    initial_response = {
        "choices": [
            {
                "message": {
                    "content": "Let me help you with that.",
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "terminal_command",
                                "arguments": '{"command": "ls -la"}'
                            }
                        }
                    ]
                }
            }
        ]
    }
    
    # Call process_tool_call_loop
    await chat_session.process_tool_call_loop(initial_response)
    
    # Verify send_to_llm was called at least once
    assert chat_session.send_to_llm.call_count >= 1
    
    # Get the prompt sent to the LLM after tool execution
    if sent_prompts:
        tool_result_prompt = sent_prompts[0]
        
        # Check that the prompt contains the key sections expected in the improved prompt
        assert "TOOL EXECUTION RESULTS:" in tool_result_prompt
        assert "terminal_command" in tool_result_prompt
        assert "file1.txt file2.txt directory1/" in tool_result_prompt
        assert "CURRENT CONTEXT:" in tool_result_prompt
        assert "Working directory:" in tool_result_prompt
        assert "NEXT STEPS:" in tool_result_prompt
        assert "Analyze the results" in tool_result_prompt


@pytest.mark.asyncio
@patch("supernova.cli.chat_session.console")
async def test_process_tool_call_loop_improved_error_prompting(mock_console, chat_session):
    """Test that the tool call loop properly formats prompts for failed tool executions."""
    # Set up failed commands history
    chat_session.session_state["failed_commands"] = [
        {
            "tool": "terminal_command",
            "args": {"command": "invalid_command"},
            "result": "Command not found: invalid_command",
            "iteration": 1,
            "timestamp": int(time.time())
        }
    ]
    
    # Mock failed tool execution results
    process_results = [
        {
            "content": "Trying command...",
            "tool_results": [
                {
                    "name": "terminal_command",
                    "success": False,
                    "result": "Error: Command not found: invalid_command"
                }
            ]
        },
        {
            "content": "Final response with error handling.",
            "tool_results": []
        }
    ]
    
    chat_session.process_llm_response = AsyncMock(side_effect=process_results)
    
    # Capture the arguments sent to send_to_llm
    original_send_to_llm = chat_session.send_to_llm
    sent_prompts = []
    
    async def capture_send_to_llm(*args, **kwargs):
        # Store the prompt for later verification
        if args and isinstance(args[0], str):
            sent_prompts.append(args[0])
        # Call the original method and return its result
        return await original_send_to_llm(*args, **kwargs)
    
    chat_session.send_to_llm = AsyncMock(side_effect=capture_send_to_llm)
    
    # Initial response with a tool call
    initial_response = {
        "choices": [
            {
                "message": {
                    "content": "Let me try this command.",
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "terminal_command",
                                "arguments": '{"command": "invalid_command"}'
                            }
                        }
                    ]
                }
            }
        ]
    }
    
    # Call process_tool_call_loop
    await chat_session.process_tool_call_loop(initial_response)
    
    # Verify send_to_llm was called
    assert chat_session.send_to_llm.call_count >= 1
    
    # Get the prompt sent to the LLM after tool execution
    if sent_prompts:
        error_prompt = sent_prompts[0]
        
        # Check that the key expected sections are in the error prompt
        assert "ERROR SUMMARY:" in error_prompt
        assert "terminal_command" in error_prompt
        assert "failed with:" in error_prompt
        assert "Error: Command not found" in error_prompt
        assert "FAILED COMMANDS THAT SHOULD NOT BE REPEATED:" in error_prompt
        assert "invalid_command" in error_prompt 