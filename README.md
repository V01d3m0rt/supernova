# SuperNova

![ChatGPT Image Apr 15, 2025, 10_15_55 PM](https://github.com/user-attachments/assets/9ee57e11-1eea-409b-9fcf-e38c9d7834c2)

SuperNova is an AI-powered development assistant that operates directly within the terminal, providing contextual assistance for your codebase.

## Features

- Analyzes your project's structure and Git history
- Provides an interactive chat interface
- Executes approved commands and actions
- Extensible via custom tools and plugins
- Works with local or remote LLM providers
- Maintains chat history per project
- Secure command execution with user confirmation
- VS Code integration (coming soon)

## Installation

```bash
# Install using pip
pip install supernova

# Or clone and install with Poetry
git clone https://github.com/yourusername/supernova.git
cd supernova
poetry install
```

## Quick Start

Initialize SuperNova in your project:

```bash
cd /path/to/your/project
supernova init
```

Edit your configuration in `.supernova/config.yaml` if needed, then start chatting:

```bash
supernova chat
```

## Configuration

SuperNova can be configured via:

```bash
supernova config
```

Or by directly editing the `.supernova/config.yaml` file.

Example configuration:

```yaml
# LLM Provider
llm:
  provider: "openai"  # Options: openai, anthropic, lmstudio, ollama, etc.
  model: "gpt-4-turbo"
  api_key: "${OPENAI_API_KEY}"  # Uses environment variable
  temperature: 0.7
  
# Project Analysis
project:
  max_files_to_analyze: 100
  ignore_patterns:
    - "node_modules/"
    - "venv/"
    - "__pycache__/"
  
# User Interface
ui:
  theme: "dark"  # Options: light, dark
  
# Command Execution
commands:
  allow_execution: true
  require_confirmation: true
```

## LM Studio Integration

For local model execution, SuperNova integrates with LM Studio. To use:

1. Download and install LM Studio from [lmstudio.ai](https://lmstudio.ai)
2. Start the local server with OpenAI API compatibility
3. Configure SuperNova to use the local endpoint:

```yaml
llm:
  provider: "lmstudio"
  base_url: "http://localhost:1234/v1"
  temperature: 0.7
```

## Tool System

SuperNova features an extensible tool system that allows for custom functionality:

```bash
# List all available tools
supernova tools list

# Get info about a specific tool
supernova tools info file_stats
```

### Creating Custom Tools

You can create custom tools by extending the `SupernovaTool` base class:

```python
from supernova.core.tool_base import SupernovaTool

class MyCustomTool(SupernovaTool):
    def get_name(self) -> str:
        return "my_tool"
        
    def get_description(self) -> str:
        return "A custom tool that does something useful"
        
    def get_usage_examples(self) -> list[str]:
        return ["my_tool arg1=value1 arg2=value2"]
        
    def get_required_args(self) -> list[str]:
        return ["arg1"]
        
    def execute(self, args: dict) -> dict:
        # Implementation
        return {"result": "Success!"}
```

Place your tool in the `.supernova/custom_tools/` directory to make it available.

## Advanced Usage

### Project Context Handling

SuperNova automatically analyzes your project to provide relevant context:

```bash
# Force reanalysis of project
supernova chat --reanalyze
```

### Chat History Management

```bash
# View chat history
supernova history list

# Clear history for current project
supernova history clear
```

### Custom Prompts

```bash
# Use a custom system prompt
supernova chat --system-prompt "path/to/prompt.txt"
```

## VS Code Integration

SuperNova is designed with VS Code integration in mind. Future versions will include a dedicated VS Code extension with the following features:

- Interactive chat panel within VS Code
- Context-aware code suggestions
- File and symbol navigation
- Integrated command execution
- Custom webview UI for enhanced interactions

### Using SuperNova in VS Code

While the full VS Code extension is under development, you can use SuperNova with VS Code by:

1. Installing SuperNova globally
2. Opening a terminal within VS Code
3. Running `supernova chat` from the integrated terminal

### VS Code Extension Development

The VS Code extension is currently in development. Key integration points include:

- Editor context awareness
- VS Code settings synchronization
- Authentication API for secure credential storage
- WebView panels for enhanced UI
- Custom commands and keyboard shortcuts

If you're interested in contributing to the VS Code extension, check out the `supernova/integrations/vscode_integration.py` file for TODOs and integration points.

## Developer Documentation

### Architecture

SuperNova is built with a modular architecture:

- `core/`: Core functionality and abstractions
- `cli/`: Command-line interface implementations
- `config/`: Configuration handling
- `persistence/`: Data storage and history
- `integrations/`: Git and VS Code integrations
- `extensions/`: Built-in and custom tools

### Adding New Features

1. Fork the repository
2. Create a new feature branch
3. Implement your changes
4. Add tests
5. Submit a pull request

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run specific test module
poetry run pytest tests/core/test_tool_manager.py
```

## Troubleshooting

### Common Issues

- **API Key Issues**: Ensure your LLM provider API key is correctly set in the config or as an environment variable
- **Project Analysis Errors**: Make sure you're in a valid Git repository or use `--no-git` flag
- **Tool Loading Failures**: Check custom tool implementations for errors

## Requirements

- Python 3.10+
- Git (for repository analysis)
- Linux or macOS

## License

Apache License Version 2.0

## Author

- Gad Biran
- Nikhil Laturi
- Rachel Avrunin
- Uri Shulman
- Sara Ziada
