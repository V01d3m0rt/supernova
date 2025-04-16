import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from supernova.core.command_runner import run_command, sanitize_command


def test_run_command_success():
    """Test running a command that succeeds."""
    # Use echo as a simple command that will always succeed
    with patch("supernova.core.command_runner.subprocess.run") as mock_run:
        # Mock successful subprocess execution
        process_mock = MagicMock()
        process_mock.stdout = "test output"
        process_mock.stderr = ""
        process_mock.returncode = 0
        mock_run.return_value = process_mock
        
        with patch("supernova.core.command_runner.Confirm.ask", return_value=True):
            return_code, stdout, stderr = run_command("echo 'test'", require_confirmation=True)
        
        # Verify result
        assert return_code == 0
        assert stdout == "test output"
        assert stderr == ""


def test_run_command_failure():
    """Test running a command that fails."""
    # Use a command that will fail
    with patch("supernova.core.command_runner.subprocess.run") as mock_run:
        # Mock failed subprocess execution
        process_mock = MagicMock()
        process_mock.stdout = ""
        process_mock.stderr = "command not found"
        process_mock.returncode = 127
        mock_run.return_value = process_mock
        
        with patch("supernova.core.command_runner.Confirm.ask", return_value=True):
            return_code, stdout, stderr = run_command("command_that_does_not_exist", require_confirmation=True)
        
        # Verify result
        assert return_code == 127
        assert stderr == "command not found"


@patch("supernova.core.command_runner.subprocess.run")
def test_run_command_with_working_dir(mock_run):
    """Test running a command with a specific working directory."""
    # Setup mock
    process_mock = MagicMock()
    process_mock.stdout = "test output"
    process_mock.stderr = ""
    process_mock.returncode = 0
    mock_run.return_value = process_mock
    
    # Run command with cwd
    working_dir = Path("/test/dir")
    with patch("supernova.core.command_runner.Confirm.ask", return_value=True):
        return_code, stdout, stderr = run_command("ls -la", cwd=working_dir, require_confirmation=True)
    
    # Verify working_dir was passed to subprocess.run
    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args[1]
    assert call_kwargs["cwd"] == str(working_dir)
    
    # Verify result
    assert return_code == 0
    assert stdout == "test output"
    assert stderr == ""


@patch("supernova.core.command_runner.subprocess.run")
def test_run_command_with_timeout(mock_run):
    """Test running a command with a timeout."""
    # Mock subprocess.run to raise TimeoutExpired
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep 2", timeout=0.1)
    
    # Run command with timeout
    with patch("supernova.core.command_runner.Confirm.ask", return_value=True):
        return_code, stdout, stderr = run_command("sleep 2", timeout=0.1, require_confirmation=True)
    
    # Verify result
    assert return_code == 124
    assert "Command timed out" in stderr


def test_sanitize_command():
    """Test sanitizing commands to remove dangerous operators."""
    # Test various dangerous command patterns
    dangerous_commands = [
        "ls && rm -rf /",
        "echo $(cat /etc/passwd)",
        "echo `cat /etc/passwd`",
        "cat /etc/passwd > leaked.txt",
        "cat /etc/passwd | grep root",
    ]
    
    for cmd in dangerous_commands:
        sanitized = sanitize_command(cmd)
        # Check that dangerous operators were removed
        assert "&&" not in sanitized
        assert "$(" not in sanitized
        assert "`" not in sanitized
        assert ">" not in sanitized
        assert "|" not in sanitized 