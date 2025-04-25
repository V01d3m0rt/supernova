"""
Tests for the refactored chat session.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from supernova.cli.chat.session.chat_session import ChatSession

@pytest.fixture
def mock_db():
    """Create a mock database."""
    db = MagicMock()
    db.enabled = True
    db.get_latest_chat_for_project.return_value = None
    db.create_chat.return_value = "test-chat-id"
    return db

@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.get_completion.return_value = {
        "content": "Test response",
        "tool_calls": []
    }
    return provider

@pytest.fixture
def mock_tool_manager():
    """Create a mock tool manager."""
    manager = MagicMock()
    manager.get_available_tools_for_llm.return_value = []
    return manager

@patch("supernova.core.llm_provider.get_provider")
@patch("supernova.core.tool_manager.ToolManager")
def test_chat_session_initialization(mock_tool_manager_class, mock_get_provider, mock_db, mock_llm_provider, mock_tool_manager):
    """Test that the chat session initializes correctly."""
    # Set up mocks
    mock_get_provider.return_value = mock_llm_provider
    mock_tool_manager_class.return_value = mock_tool_manager
    
    # Create a test directory
    test_dir = Path(os.getcwd())
    
    # Initialize chat session
    session = ChatSession(db=mock_db, initial_directory=test_dir)
    
    # Check that the session was initialized correctly
    assert session.session_state.get_initial_directory() == test_dir
    assert session.session_state.get_cwd() == test_dir
    assert session.llm_provider == mock_llm_provider
    assert session.tool_manager == mock_tool_manager
    assert session.db == mock_db

@patch("supernova.core.llm_provider.get_provider")
@patch("supernova.core.tool_manager.ToolManager")
def test_load_or_create_chat_new(mock_tool_manager_class, mock_get_provider, mock_db, mock_llm_provider, mock_tool_manager):
    """Test that a new chat is created when no previous chat exists."""
    # Set up mocks
    mock_get_provider.return_value = mock_llm_provider
    mock_tool_manager_class.return_value = mock_tool_manager
    mock_db.get_latest_chat_for_project.return_value = None
    
    # Create a test directory
    test_dir = Path(os.getcwd())
    
    # Initialize chat session
    session = ChatSession(db=mock_db, initial_directory=test_dir)
    
    # Load or create chat
    session.load_or_create_chat()
    
    # Check that a new chat was created
    mock_db.create_chat.assert_called_once_with(test_dir)
    assert session.message_manager.chat_id == "test-chat-id"
    assert not session.session_state.get_state()["loaded_previous_chat"]

@patch("supernova.core.llm_provider.get_provider")
@patch("supernova.core.tool_manager.ToolManager")
def test_load_or_create_chat_existing(mock_tool_manager_class, mock_get_provider, mock_db, mock_llm_provider, mock_tool_manager):
    """Test that an existing chat is loaded when one exists."""
    # Set up mocks
    mock_get_provider.return_value = mock_llm_provider
    mock_tool_manager_class.return_value = mock_tool_manager
    mock_db.get_latest_chat_for_project.return_value = "existing-chat-id"
    mock_db.get_chat_history.return_value = [
        {
            "role": "user",
            "content": "Test message",
            "timestamp": "2021-01-01T00:00:00",
            "metadata": {}
        }
    ]
    
    # Create a test directory
    test_dir = Path(os.getcwd())
    
    # Initialize chat session
    session = ChatSession(db=mock_db, initial_directory=test_dir)
    
    # Load or create chat
    session.load_or_create_chat()
    
    # Check that an existing chat was loaded
    mock_db.get_chat_history.assert_called_once_with("existing-chat-id")
    assert session.message_manager.chat_id == "existing-chat-id"
    assert session.session_state.get_state()["loaded_previous_chat"]
    assert len(session.message_manager.get_messages()) == 1