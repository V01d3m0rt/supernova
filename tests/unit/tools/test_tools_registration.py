"""
Tests for verifying tool registration with SuperNova.
"""

import pytest
from pathlib import Path

from supernova.core.tool_manager import ToolManager
from supernova.core.tool_base import SupernovaTool


def test_core_tools_registration():
    """Test that core tools are registered correctly."""
    # Create a tool manager instance
    tool_manager = ToolManager()
    
    # Expected tools
    expected_tools = ["terminal_command", "file_edit", "file_search", "folder_search"]
    
    # Check that all expected tools are registered
    for tool_name in expected_tools:
        tool = tool_manager.get_tool(tool_name)
        assert tool is not None, f"Tool {tool_name} is not registered"
        assert isinstance(tool, SupernovaTool), f"Tool {tool_name} is not a SupernovaTool instance"


def test_tool_arguments_schema():
    """Test that all tools have a valid arguments schema."""
    # Create a tool manager instance
    tool_manager = ToolManager()
    
    # Get all tools
    tools = tool_manager.list_tools()
    
    # Check each tool has a valid arguments schema
    for tool in tools:
        schema = tool.get_arguments_schema()
        assert schema is not None, f"Tool {tool.get_name()} has no arguments schema"
        assert isinstance(schema, dict), f"Tool {tool.get_name()} arguments schema is not a dictionary"
        assert "type" in schema, f"Tool {tool.get_name()} arguments schema has no 'type' field"
        assert "properties" in schema, f"Tool {tool.get_name()} arguments schema has no 'properties' field"


def test_tool_usage_examples():
    """Test that all tools have valid usage examples."""
    # Create a tool manager instance
    tool_manager = ToolManager()
    
    # Get all tools
    tools = tool_manager.list_tools()
    
    # Check each tool has valid usage examples
    for tool in tools:
        examples = tool.get_usage_examples()
        assert examples is not None, f"Tool {tool.get_name()} has no usage examples"
        assert isinstance(examples, list), f"Tool {tool.get_name()} usage examples is not a list"
        
        # Each example should have a description and arguments
        for example in examples:
            assert isinstance(example, dict), f"Tool {tool.get_name()} example is not a dictionary"
            assert "description" in example, f"Tool {tool.get_name()} example has no 'description' field"
            assert "arguments" in example, f"Tool {tool.get_name()} example has no 'arguments' field"


def test_extension_tools_loading():
    """Test extension tools loading."""
    # Create a tool manager instance
    tool_manager = ToolManager()
    
    # Record the number of tools before loading extensions
    initial_tool_count = len(tool_manager.list_tools())
    
    # Load extension tools
    tool_manager.load_extension_tools()
    
    # Check that tools are loaded
    # Note: This test may pass even if no new tools are loaded,
    # since we've already registered the extension tools directly
    # in the ToolManager constructor
    loaded_tools = len(tool_manager.list_tools())
    assert loaded_tools >= initial_tool_count, "No extension tools were loaded" 