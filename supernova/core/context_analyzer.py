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


async def analyze_project(project_path: Path) -> str:
    """
    Analyze a project directory to provide context for the AI assistant.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        A summary string describing the project
    """
    if not project_path.exists() or not project_path.is_dir():
        raise ValueError(f"Invalid project path: {project_path}")
    
    # Load configuration
    config = loader.load_config()
    
    # Get project structure info
    is_git_repo, git_info = await _check_git_repository(project_path)
    key_files = await _find_key_files(project_path, config.project_context.key_files)
    
    # TODO: VS Code Integration - If running in VS Code, enhance project analysis with:
    # 1. Workspace information (multi-root workspaces, settings)
    # 2. Open editors and their state
    # 3. VS Code extension-specific project metadata
    
    # Determine project type
    project_type = _determine_project_type(key_files)
    
    # Generate summary
    summary = f"{project_type} project"
    
    if is_git_repo:
        branch = git_info.get("branch", "unknown")
        summary += f", Git repository (branch: {branch})"
    
    # Add key files info
    if key_files:
        key_files_str = ", ".join([f.name for f in key_files[:3]])
        if len(key_files) > 3:
            key_files_str += f" and {len(key_files) - 3} more"
        summary += f", key files: {key_files_str}"
    
    return summary


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