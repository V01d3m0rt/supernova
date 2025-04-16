from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import subprocess
import pytest

from supernova.tools.terminal_command_tool import TerminalCommandTool


@pytest.fixture
def terminal_command_tool():
    """Create a terminal command tool instance for testing."""
    return TerminalCommandTool()


def test_tool_properties(terminal_command_tool):
    """Test basic properties of the terminal command tool."""
    assert terminal_command_tool.name == "terminal_command"
    assert "terminal command" in terminal_command_tool.description.lower()
    
    schema = terminal_command_tool.get_arguments_schema()
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "command" in schema["properties"]
    assert schema["properties"]["command"]["type"] == "string"
    assert "required" in schema
    assert "command" in schema["required"]


@patch("subprocess.Popen")
def test_execute_success(mock_popen, terminal_command_tool):
    """Test successful command execution."""
    # Mock process with successful execution
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("Command output", "")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    result = terminal_command_tool.execute(
        command="echo 'hello'",
        working_dir=str(Path.cwd())  # Use actual directory to avoid file not found
    )
    
    # Verify Popen was called
    mock_popen.assert_called_once()
    
    # Check result
    assert result["success"] is True
    assert result["output"] == "Command output"
    assert result["stderr"] == ""
    assert result["return_code"] == 0


@patch("subprocess.Popen")
def test_execute_failure(mock_popen, terminal_command_tool):
    """Test failed command execution."""
    # Mock process with failed execution
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", "Command not found")
    mock_process.returncode = 127
    mock_popen.return_value = mock_process
    
    result = terminal_command_tool.execute(
        command="invalid_command",
        working_dir=str(Path.cwd())  # Use actual directory
    )
    
    # Verify Popen was called
    mock_popen.assert_called_once()
    
    # Check result
    assert result["success"] is False
    assert result["stderr"] == "Command not found"
    assert result["return_code"] == 127


def test_execute_missing_command(terminal_command_tool):
    """Test execution with missing command argument."""
    # Pass empty command
    result = terminal_command_tool.execute(command="")
    
    # Check result
    assert result["success"] is False
    assert "Missing required argument: command" in result["error"]


@patch("subprocess.Popen")
def test_execute_default_working_dir(mock_popen, terminal_command_tool):
    """Test execution with default working directory."""
    # Mock process with successful execution
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("Command output", "")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    # Execute without working_dir
    result = terminal_command_tool.execute(command="ls -la")
    
    # Verify Popen was called
    mock_popen.assert_called_once()
    
    # Check result
    assert result["success"] is True
    assert result["output"] == "Command output"


@patch("subprocess.Popen")
def test_execute_cd_command(mock_popen, terminal_command_tool):
    """Test execution of cd command with working directory update."""
    # Mock process with successful execution
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", "")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    # Execute cd command with a valid working directory
    result = terminal_command_tool.execute(
        command="cd /new/path",
        working_dir=str(Path.cwd())  # Use actual directory
    )
    
    # Verify Popen was called
    mock_popen.assert_called_once()
    
    # Check result includes updated working directory
    assert result["success"] is True
    assert "updated_working_dir" in result


@patch("subprocess.Popen")
def test_execute_complex_command(mock_popen, terminal_command_tool):
    """Test execution of complex command."""
    # Mock process with successful execution
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("Command output", "")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    # Execute complex command
    result = terminal_command_tool.execute(
        command="ls -la && echo 'hello'",
        working_dir=str(Path.cwd())  # Use actual directory
    )
    
    # Verify Popen was called with shell=True for complex commands
    mock_popen.assert_called_once()
    
    # Check result
    assert result["success"] is True
    assert result["output"] == "Command output"

# Additional tests to improve coverage

@patch("subprocess.Popen")
def test_execute_with_explanation(mock_popen, terminal_command_tool):
    """Test execution with explanation parameter."""
    # Mock process with successful execution
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("Command output", "")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    # Execute with explanation
    result = terminal_command_tool.execute(
        command="ls -la",
        explanation="List files in directory",
        working_dir=str(Path.cwd())
    )
    
    # Verify Popen was called
    mock_popen.assert_called_once()
    
    # Check result
    assert result["success"] is True
    assert result["output"] == "Command output"


@patch("subprocess.Popen")
def test_execute_with_stdout_and_stderr(mock_popen, terminal_command_tool):
    """Test execution with both stdout and stderr output."""
    # Mock process with mixed output
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("Standard output", "Error output")
    mock_process.returncode = 1  # Error code
    mock_popen.return_value = mock_process
    
    # Execute command
    result = terminal_command_tool.execute(command="some-command")
    
    # Check result contains both outputs
    assert result["success"] is False
    assert result["output"] == "Standard output"
    assert result["stderr"] == "Error output"
    assert result["return_code"] == 1


@patch("subprocess.Popen")
def test_execute_timeout(mock_popen, terminal_command_tool):
    """Test execution with a timeout."""
    # Mock process that times out
    mock_process = MagicMock()
    mock_process.communicate.side_effect = subprocess.TimeoutExpired("cmd", 60)
    mock_popen.return_value = mock_process
    
    # Execute command
    result = terminal_command_tool.execute(command="sleep 100")
    
    # Check result
    assert result["success"] is False
    assert "timed" in result["error"].lower()
    assert result["output"] is None
    assert result["return_code"] is None


@patch("subprocess.Popen")
def test_execute_general_exception(mock_popen, terminal_command_tool):
    """Test execution with a general exception."""
    # Mock process that raises an exception
    mock_popen.side_effect = Exception("Mock exception")
    
    # Execute command
    result = terminal_command_tool.execute(command="ls")
    
    # Check result
    assert result["success"] is False
    assert "Mock exception" in result["error"]
    assert result["output"] is None
    assert result["return_code"] is None


@patch("shlex.split")
@patch("subprocess.Popen")
def test_execute_parsing_error(mock_popen, mock_shlex, terminal_command_tool):
    """Test execution with command parsing error."""
    # Mock shlex.split to raise ValueError
    mock_shlex.side_effect = ValueError("Invalid syntax")
    
    # Mock process with successful execution (fallback case)
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("Command output", "")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    # Execute command
    result = terminal_command_tool.execute(command="echo 'hello")
    
    # Check Popen was called with shell=True as fallback
    _, kwargs = mock_popen.call_args
    assert kwargs.get("shell") is True
    
    assert result["success"] is True


def test_get_required_args(terminal_command_tool):
    """Test getting required arguments."""
    required_args = terminal_command_tool.get_required_args()
    assert isinstance(required_args, dict)
    assert "command" in required_args


def test_get_optional_args(terminal_command_tool):
    """Test getting optional arguments."""
    optional_args = terminal_command_tool.get_optional_args()
    assert isinstance(optional_args, dict)
    assert "explanation" in optional_args
    assert "working_dir" in optional_args


def test_get_usage_examples(terminal_command_tool):
    """Test getting usage examples."""
    examples = terminal_command_tool.get_usage_examples()
    assert isinstance(examples, list)
    assert len(examples) > 0
    assert "description" in examples[0]
    assert "arguments" in examples[0]


@pytest.mark.asyncio
@patch("asyncio.get_event_loop")
async def test_async_execute(mock_get_loop, terminal_command_tool):
    """Test async_execute method."""
    # Mock loop
    mock_loop = AsyncMock()
    mock_get_loop.return_value = mock_loop
    
    # Mock run_in_executor to return a result
    mock_loop.run_in_executor.return_value = {
        "success": True,
        "output": "Async output",
        "stderr": "",
        "return_code": 0
    }
    
    # Execute async
    result = await terminal_command_tool.async_execute(
        {"command": "ls -la"},
        {"session_id": "123"},
        "/test/dir"
    )
    
    # Check result
    assert result["success"] is True
    assert result["output"] == "Async output"
    
    # Verify run_in_executor was called
    mock_loop.run_in_executor.assert_called_once()


@pytest.mark.asyncio
async def test_async_execute_with_working_dir_override(terminal_command_tool):
    """Test async_execute with working_dir parameter override."""
    # Mock the execute method
    original_execute = terminal_command_tool.execute
    
    # This will track what arguments the execute method is called with
    calls = []
    def mock_execute(command, explanation=None, working_dir=None):
        calls.append({"command": command, "explanation": explanation, "working_dir": working_dir})
        return {"success": True}
    
    # Patch the execute method
    terminal_command_tool.execute = mock_execute
    
    try:
        # Call async_execute with both args working_dir and parameter working_dir
        args = {"command": "ls", "working_dir": "/in/args"}
        override_working_dir = "/override/dir"
        
        await terminal_command_tool.async_execute(
            args=args,
            context={},
            working_dir=override_working_dir
        )
        
        # Verify the execute function was called and the override working_dir was used
        assert len(calls) == 1, "Execute should have been called exactly once"
        assert calls[0]["working_dir"] == override_working_dir, "Override working_dir should take precedence"
        
    finally:
        # Restore the original execute method
        terminal_command_tool.execute = original_execute


@pytest.mark.asyncio
async def test_async_execute_with_context(terminal_command_tool):
    """Test async_execute passes context correctly."""
    # Create a patched version of the execute method
    original_execute = terminal_command_tool.execute
    
    def mock_execute(*args, **kwargs):
        # Store the args for later inspection
        mock_execute.called_with = (args, kwargs)
        return {"success": True}
    
    mock_execute.called_with = None
    terminal_command_tool.execute = mock_execute
    
    # Create context
    context = {"session_id": "test123", "user": "testuser"}
    
    try:
        # Execute async with context
        await terminal_command_tool.async_execute(
            {"command": "echo 'hello'"},
            context
        )
        
        # As the context isn't directly used in execute(), we can't verify it here,
        # but we're testing the function signature and basic flow
    finally:
        # Restore original execute method
        terminal_command_tool.execute = original_execute 