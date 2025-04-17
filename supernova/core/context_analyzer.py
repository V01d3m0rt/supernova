"""
SuperNova - AI-powered development assistant within the terminal.

Context analyzer for project awareness.
"""

import os
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pathspec
from rich.console import Console

from supernova.config import loader
from supernova.integrations import git_utils

console = Console()

# TODO: VS Code Integration - Create VSCodeProjectAnalyzer class that can:
# 1. Detect open files in VS Code workspace
# 2. Extract current file contents and cursor positions
# 3. Analyze VS Code workspace settings and extensions


def analyze_project(path: Path) -> str:
    """
    Analyze the project context.
    
    Args:
        path: The project path
        
    Returns:
        Summary of the project
    """
    # Use git to get information about the project
    try:
        # Check if it's a git repository
        git_dir = path / ".git"
        if not git_dir.is_dir():
            # Try parent directories
            parent = path.parent
            max_depth = 3
            depth = 0
            while depth < max_depth and parent != parent.parent:
                git_parent = parent / ".git"
                if git_parent.is_dir():
                    git_dir = git_parent
                    break
                parent = parent.parent
                depth += 1
        
        if git_dir.is_dir():
            # Get repository information
            repo_url = subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"], 
                cwd=path, 
                text=True
            ).strip()
            
            # Extract repo name from URL
            repo_name = repo_url.split("/")[-1].replace(".git", "")
            
            # Get current branch
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=path,
                text=True
            ).strip()
            
            return f"{repo_name} ({branch})"
    except Exception:
        pass
    
    # If git information is not available, use the directory name
    return path.name


async def _check_git_repository(project_path: Path) -> Tuple[bool, Dict[str, str]]:
    """
    Check if the directory is a Git repository and get basic Git information.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        A tuple with (is_git_repo, git_info_dict)
    """
    try:
        # This will be implemented in integrations/git_utils.py
        is_git_repo, git_info = await git_utils.get_repository_info(project_path)
        return is_git_repo, git_info
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Error getting Git info: {str(e)}")
        return False, {}


async def _find_key_files(project_path: Path, key_file_patterns: List[str]) -> List[Path]:
    """
    Find key files in the project based on the provided patterns.
    
    Args:
        project_path: Path to the project directory
        key_file_patterns: List of glob patterns for key files
        
    Returns:
        List of paths to key files
    """
    key_files = []
    
    for pattern in key_file_patterns:
        # Handle glob patterns
        matches = list(project_path.glob(pattern))
        for match in matches:
            if match.is_file() and match not in key_files:
                key_files.append(match)
    
    return key_files


def _determine_project_type(key_files: List[Path]) -> str:
    """
    Determine the type of project based on key files.
    
    Args:
        key_files: List of key file paths
        
    Returns:
        String representing the project type
    """
    # Convert to filenames for easier matching
    filenames = [f.name for f in key_files]
    
    # Check for Python
    if "pyproject.toml" in filenames or "requirements.txt" in filenames or "setup.py" in filenames:
        return "Python"
    
    # Check for JavaScript/Node.js
    if "package.json" in filenames or "package-lock.json" in filenames or "yarn.lock" in filenames:
        return "JavaScript/Node.js"
    
    # Check for Java/Maven
    if "pom.xml" in filenames:
        return "Java/Maven"
    
    # Check for Java/Gradle
    if any(f.endswith(".gradle") or f.endswith(".gradle.kts") for f in filenames):
        return "Java/Gradle"
    
    # Check for Docker
    if "Dockerfile" in filenames or "docker-compose.yml" in filenames:
        return "Docker"
    
    # Default
    return "Generic" 