"""
SuperNova - AI-powered development assistant within the terminal.

Configuration schema using Pydantic.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider."""
    
    provider: str = Field(..., description="Provider name (e.g., 'openai', 'anthropic')")
    api_key: Optional[str] = Field(None, description="API key for the provider")
    base_url: Optional[str] = Field(None, description="Base URL for the provider API")
    api_version: Optional[str] = Field(None, description="API version (required for Azure OpenAI)")
    model: str = Field(..., description="Model name to use")
    timeout: int = Field(60, description="Request timeout in seconds")
    is_default: bool = Field(False, description="Whether this is the default provider")
    temperature: float = Field(0.7, description="Temperature for response generation")
    max_tokens: Optional[int] = Field(None, description="Maximum number of tokens to generate")


class GitConfig(BaseModel):
    """Configuration for Git integration."""
    
    enabled: bool = Field(True, description="Whether Git integration is enabled")
    max_commits: int = Field(10, description="Maximum number of commits to fetch")
    include_diff: bool = Field(False, description="Whether to include diff information")


class FileScanConfig(BaseModel):
    """Configuration for file scanning."""
    
    max_files: int = Field(100, description="Maximum number of files to scan")
    max_file_size_kb: int = Field(500, description="Maximum file size to scan in KB")
    additional_ignore_patterns: List[str] = Field(
        default_factory=list,
        description="Additional patterns to ignore during file scanning"
    )


class ProjectContextConfig(BaseModel):
    """Configuration for project context analysis."""
    
    git: GitConfig = Field(default_factory=GitConfig)
    file_scan: FileScanConfig = Field(default_factory=FileScanConfig)
    key_files: List[str] = Field(
        default_factory=lambda: [
            "README*",
            "pyproject.toml",
            "package.json",
            "requirements.txt",
            "Makefile",
            "Dockerfile",
            "docker-compose.yml",
            "*.gradle",
            "pom.xml",
        ],
        description="Glob patterns for key files"
    )


class ChatConfig(BaseModel):
    """Configuration for chat interface."""
    
    history_limit: int = Field(50, description="Maximum number of messages to keep in history")
    syntax_highlighting: bool = Field(True, description="Whether to enable syntax highlighting")
    display_model_name: bool = Field(True, description="Whether to display the model name")
    welcome_prompt: Optional[str] = Field(None, description="Message to send to the LLM when starting a chat")
    streaming: bool = Field(True, description="Whether to enable streaming")
    streaming_tool_calls: bool = Field(True, description="Whether to stream tool calls")
    max_tool_iterations: int = Field(5, description="Maximum number of tool call iterations in a loop")
    tool_result_line_limit: int = Field(5, description="Maximum number of lines from tool results to include in LLM context")


class CommandExecutionConfig(BaseModel):
    """Configuration for command execution."""
    
    require_confirmation: bool = Field(True, description="Whether to require confirmation before execution")
    show_output: bool = Field(True, description="Whether to show command output")
    timeout: int = Field(30, description="Command execution timeout in seconds")


class ExtensionsConfig(BaseModel):
    """Configuration for extensions/tools."""
    
    enabled: bool = Field(True, description="Whether extensions are enabled")
    allowed_tools: List[str] = Field(
        default_factory=lambda: ["file", "git", "search"],
        description="List of allowed tool names"
    )


class PersistenceConfig(BaseModel):
    """Configuration for persistence."""
    
    enabled: bool = Field(True, description="Whether persistence is enabled")
    db_path: str = Field("${HOME}/.supernova/history.db", description="Path to the SQLite database")


class DebuggingConfig(BaseModel):
    """Configuration for debugging features."""
    
    show_session_state: bool = Field(False, description="Whether to show session state for debugging")
    show_traceback: bool = Field(False, description="Whether to show full traceback for errors")


class SuperNovaConfig(BaseModel):
    """Main configuration for SuperNova."""
    
    llm_providers: Dict[str, LLMProviderConfig] = Field(
        ...,
        description="Dictionary of LLM providers"
    )
    project_context: ProjectContextConfig = Field(
        default_factory=ProjectContextConfig,
        description="Project context configuration"
    )
    chat: ChatConfig = Field(
        default_factory=ChatConfig,
        description="Chat interface configuration"
    )
    command_execution: CommandExecutionConfig = Field(
        default_factory=CommandExecutionConfig,
        description="Command execution configuration"
    )
    extensions: ExtensionsConfig = Field(
        default_factory=ExtensionsConfig,
        description="Extensions configuration"
    )
    persistence: PersistenceConfig = Field(
        default_factory=PersistenceConfig,
        description="Persistence configuration"
    )
    debugging: DebuggingConfig = Field(
        default_factory=DebuggingConfig,
        description="Debugging configuration"
    ) 