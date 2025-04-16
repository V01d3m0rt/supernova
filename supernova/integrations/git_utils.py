"""
SuperNova - AI-powered development assistant within the terminal.

Git utilities for interacting with Git repositories.
"""

import os
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from functools import partial

import git
from git import Repo
from rich.console import Console

console = Console()


async def get_repository_info(path: Path) -> Tuple[bool, Dict[str, str]]:
    """
    Get information about a Git repository.
    
    Args:
        path: Path to check for a Git repository
        
    Returns:
        Tuple of (is_git_repo, repo_info)
    """
    # Run the potentially blocking Git operations in a thread pool
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, partial(_get_repository_info_sync, path))
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Async Git error: {str(e)}")
        return False, {}


def _get_repository_info_sync(path: Path) -> Tuple[bool, Dict[str, str]]:
    """Synchronous implementation of get_repository_info"""
    try:
        repo = Repo(path, search_parent_directories=True)
        
        # Get repository root
        repo_root = Path(repo.working_dir)
        
        # Get current branch
        try:
            branch = repo.active_branch.name
        except TypeError:
            # Detached HEAD state
            branch = "DETACHED HEAD"
        
        # Get recent commits
        recent_commits = []
        for commit in repo.iter_commits(max_count=10):
            recent_commits.append({
                "hash": commit.hexsha[:7],
                "message": commit.message.strip().split("\n")[0],
                "author": f"{commit.author.name} <{commit.author.email}>",
                "date": commit.committed_datetime.isoformat(),
            })
        
        # Get modified files
        modified_files = []
        for item in repo.index.diff(None):
            modified_files.append(item.a_path)
        
        # Get untracked files
        untracked_files = repo.untracked_files
        
        # Prepare info dictionary
        info = {
            "root": str(repo_root),
            "branch": branch,
            "modified_files_count": len(modified_files),
            "untracked_files_count": len(untracked_files),
            "recent_commits": recent_commits,
        }
        
        return True, info
    
    except git.exc.InvalidGitRepositoryError:
        return False, {}
    except git.exc.NoSuchPathError:
        return False, {}
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Git error: {str(e)}")
        return False, {}


async def find_repository_root(path: Path) -> Optional[Path]:
    """
    Find the root directory of a Git repository.
    
    Args:
        path: Starting path to search from
        
    Returns:
        Path to the repository root or None if not in a repository
    """
    # Run the potentially blocking Git operations in a thread pool
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, partial(_find_repository_root_sync, path))
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Error finding repository root: {str(e)}")
        return None


def _find_repository_root_sync(path: Path) -> Optional[Path]:
    """Synchronous implementation of find_repository_root"""
    try:
        repo = Repo(path, search_parent_directories=True)
        return Path(repo.working_dir)
    except (git.exc.InvalidGitRepositoryError, git.exc.NoSuchPathError):
        return None
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Error finding repository root: {str(e)}")
        return None


async def get_recent_commits(path: Path, count: int = 10) -> List[Dict[str, str]]:
    """
    Get a list of recent commits from a Git repository.
    
    Args:
        path: Path to a Git repository
        count: Number of commits to retrieve
        
    Returns:
        List of commit dictionaries with hash, message, author, and date
    """
    # Run the potentially blocking Git operations in a thread pool
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, partial(_get_recent_commits_sync, path, count))
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Error getting commits: {str(e)}")
        return []


def _get_recent_commits_sync(path: Path, count: int = 10) -> List[Dict[str, str]]:
    """Synchronous implementation of get_recent_commits"""
    try:
        repo = Repo(path, search_parent_directories=True)
        
        commits = []
        for commit in repo.iter_commits(max_count=count):
            commits.append({
                "hash": commit.hexsha[:7],
                "message": commit.message.strip().split("\n")[0],
                "author": f"{commit.author.name} <{commit.author.email}>",
                "date": commit.committed_datetime.isoformat(),
            })
        
        return commits
    
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Error getting commits: {str(e)}")
        return [] 