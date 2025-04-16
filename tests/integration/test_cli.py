from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from supernova.cli.main import cli


@pytest.fixture
def mock_chat_session():
    """Create a mock ChatSession for testing."""
    chat_session = MagicMock()
    chat_session.run.return_value = None
    return chat_session


@pytest.fixture
def runner():
    """Return a CliRunner for testing the CLI."""
    return CliRunner()


def test_cli_base_help(runner):
    """Test the base CLI help command."""
    result = runner.invoke(cli, ["--help"])
    
    assert result.exit_code == 0
    assert "SuperNova" in result.output
    assert "chat" in result.output
    assert "init" in result.output
    assert "config" in result.output


def test_cli_chat_help(runner):
    """Test the chat command help."""
    result = runner.invoke(cli, ["chat", "--help"])
    
    assert result.exit_code == 0
    assert "Start a chat session" in result.output
    assert "--directory" in result.output or "-d" in result.output


def test_cli_init_help(runner):
    """Test the init command help."""
    result = runner.invoke(cli, ["init", "--help"])
    
    assert result.exit_code == 0
    assert "Initialize SuperNova" in result.output


@patch("supernova.cli.main.Path.exists", return_value=True)
@patch("supernova.cli.main.Path.is_dir", return_value=True)
@patch("supernova.cli.main.ChatSession")
def test_chat_command(mock_chat_session_class, mock_is_dir, mock_exists, runner, mock_chat_session):
    """Test the chat command execution."""
    # Set up the mock
    mock_chat_session_class.return_value = mock_chat_session
    
    # Run the chat command
    result = runner.invoke(cli, ["chat", "-d", "/test/dir"])
    
    # Check the result
    assert result.exit_code == 0
    
    # Verify ChatSession was created with the right directory
    mock_chat_session_class.assert_called_once()
    call_args = mock_chat_session_class.call_args[1]
    assert str(call_args["cwd"]) == "/test/dir"
    
    # Verify run was called
    mock_chat_session.run.assert_called_once()


@patch("supernova.cli.main.Path.exists", return_value=False)
def test_chat_command_invalid_directory(mock_exists, runner):
    """Test the chat command with an invalid directory."""
    # Run the chat command with a non-existent directory
    result = runner.invoke(cli, ["chat", "-d", "/nonexistent/dir"])
    
    # Check that the command failed
    assert result.exit_code != 0
    assert "does not exist" in result.output or "Invalid directory" in result.output


@patch("supernova.cli.main.Path.exists", return_value=True)
@patch("supernova.cli.main.Path.is_dir", return_value=False)
def test_chat_command_not_a_directory(mock_is_dir, mock_exists, runner):
    """Test the chat command with a path that is not a directory."""
    # Run the chat command with a file path instead of a directory
    result = runner.invoke(cli, ["chat", "-d", "/path/to/file.txt"])
    
    # Check that the command failed
    assert result.exit_code != 0
    assert "is not a directory" in result.output or "Invalid directory" in result.output


@patch("supernova.cli.main.Path.exists", return_value=True)
@patch("supernova.cli.main.Path.is_dir", return_value=True)
@patch("supernova.cli.main.initialize_supernova")
def test_init_command(mock_init, mock_is_dir, mock_exists, runner):
    """Test the init command execution."""
    # Set up the mock
    mock_init.return_value = {"success": True, "message": "Initialization complete"}
    
    # Run the init command
    result = runner.invoke(cli, ["init", "/test/dir"])
    
    # Check the result
    assert result.exit_code == 0
    assert "Initialization complete" in result.output
    
    # Verify initialize_supernova was called with the right directory
    mock_init.assert_called_once_with(Path("/test/dir"))


@patch("supernova.cli.main.Path.exists", return_value=True)
@patch("supernova.cli.main.Path.is_dir", return_value=True)
@patch("supernova.cli.main.initialize_supernova")
def test_init_command_failure(mock_init, mock_is_dir, mock_exists, runner):
    """Test the init command when initialization fails."""
    # Set up the mock to return a failure
    mock_init.return_value = {"success": False, "error": "Initialization failed"}
    
    # Run the init command
    result = runner.invoke(cli, ["init", "/test/dir"])
    
    # Check the result
    assert result.exit_code != 0
    assert "Initialization failed" in result.output 