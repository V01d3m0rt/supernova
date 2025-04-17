# SuperNova Wiki

## Overview

SuperNova is an AI-powered development assistant that runs directly in your terminal, providing contextual assistance for your codebase. It leverages Large Language Models (LLMs) to understand your project, answer questions, and help you accomplish tasks more efficiently.

![SuperNova Terminal Interface](https://example.com/supernova-terminal.png)

## Installation

### Prerequisites
- Python 3.10+
- Git (for repository analysis)
- Linux or macOS

### Standard Installation
```bash
# Clone the repository
git clone https://github.com/nikhil-laturi/supernova.git
cd supernova

# Install in development mode
pip install -e .
```

### Setting up your API Keys

SuperNova works with various LLM providers. Set up your preferred provider:

#### OpenAI
```bash
export OPENAI_API_KEY=your_api_key_here
```

#### Anthropic
```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

#### Google Gemini
```bash
export GOOGLE_API_KEY=your_api_key_here
```

## Getting Started

Initialize SuperNova in your project:
```bash
cd /path/to/your/project
supernova init
```

This creates a `.supernova` directory with configuration files.

Start chatting:
```bash
supernova chat
```

## Core Features

### Project Context Awareness
SuperNova analyzes your project to:
- Understand your codebase structure
- Read key files like README, package.json, etc.
- Review Git history for context
- Identify patterns and coding conventions

### Interactive Terminal UI
- Syntax-highlighted responses
- Command history
- User confirmation for safety
- Streaming responses

### Multi-Provider Support
Compatible with:
- OpenAI (GPT-4, etc.)
- Anthropic Claude
- Google Gemini
- Azure OpenAI
- LM Studio (local models)

### Command Execution
- Run terminal commands with AI assistance
- Preview commands before execution
- Capture and analyze command output

## Usage Guide

### Basic Interactions

```
> supernova chat

SuperNova: How can I help with your project today?

You: What are the main directories in this project?

SuperNova: [Lists main directories with descriptions]

You: How do I implement feature X?

SuperNova: [Provides guidance based on your codebase]
```

### Command Execution

```
You: How do I list all JavaScript files modified in the last week?

SuperNova: I can help with that. Would you like me to run:
git log --since="1 week ago" --name-only --pretty=format: | grep "\.js$" | sort | uniq

[y/N]: y

[Command output appears]
```

### Context Handling

SuperNova maintains context between messages. It remembers:
- Previous commands run
- Files examined
- Topics discussed
- Current working directory

## Configuration

Edit `.supernova/config.yaml` to customize:

### LLM Providers
```yaml
llm_providers:
  openai:
    provider: openai
    api_key: "${OPENAI_API_KEY}"
    model: gpt-4-turbo-preview
    timeout: 60
    is_default: true
```

### Local Models with LM Studio
```yaml
llm_providers:
  lm_studio:
    provider: openai  # Uses OpenAI-compatible API
    api_key: lm-studio
    base_url: http://localhost:1234/v1
    model: llama-3.2-3b-instruct
    timeout: 60
    is_default: true
```

### Project Analysis Settings
```yaml
project_context:
  git:
    enabled: true
    max_commits: 10
  file_scan:
    max_files: 100
    max_file_size_kb: 500
    additional_ignore_patterns:
      - '*.log'
      - 'node_modules/'
```

## Tools System

SuperNova uses a modular tool system. Currently available:

### Terminal Command Tool
Execute commands with confirmation:
```
You: How do I count lines of code by file type?

SuperNova: You can use the following command:
find . -name "*.py" -o -name "*.js" | xargs wc -l

[y/N]: y
```

### Developing Custom Tools
Create custom tools by extending the `SupernovaTool` base class:

```python
from supernova.core.tool_base import SupernovaTool

class MyCustomTool(SupernovaTool):
    name = "my_tool"
    description = "A custom tool that does something useful"
    
    def get_arguments_schema(self):
        return {
            "type": "object",
            "properties": {
                "arg1": {"type": "string"}
            },
            "required": ["arg1"]
        }
    
    def get_usage_examples(self):
        return [{
            "description": "Example usage",
            "arguments": {"arg1": "value1"}
        }]
    
    def execute(self, **kwargs):
        # Implementation
        return {"success": True, "result": "Success!"}
```

Place custom tools in the `.supernova/custom_tools/` directory.

## Best Practices

1. **Start in project root**: Initialize SuperNova from your project's root directory for optimal context.

2. **Be specific**: Ask clear, specific questions to get better responses.

3. **Review commands**: Always review suggested commands before approving execution.

4. **Use local models**: For sensitive codebases, configure local LLM models with LM Studio.

5. **Set up .gitignore**: Ensure `.supernova/` is in your .gitignore to avoid committing configuration files.

## Troubleshooting

### API Key Issues
Problem: "API key not valid" errors
Solution: Check environment variables or config.yaml for correct API keys

### Command Execution Problems
Problem: Commands fail silently
Solution: Try running the commands manually to see detailed errors

### Performance Issues
Problem: Slow responses
Solution: Consider using a smaller/faster model or local LLM via LM Studio

## Development & Contributing

### Project Structure
```
supernova/
├── cli/            # Command-line interface
├── config/         # Configuration handling
├── core/           # Core functionality
├── integrations/   # Git and editor integrations
├── persistence/    # History and state
├── tools/          # Built-in tools
└── extensions/     # Extension management
```

### Development Workflow
1. Fork the repository
2. Create a feature branch
3. Make changes and test locally
4. Run tests: `pytest`
5. Submit a pull request

## FAQs

**Q: Can SuperNova access the internet?**
A: No, SuperNova only operates on your local codebase and doesn't have internet access.

**Q: Are my code and prompts sent to external services?**
A: If using OpenAI/Anthropic/etc., your prompts and code snippets are sent to those services. Use local models via LM Studio for full privacy.

**Q: How does SuperNova differ from GitHub Copilot?**
A: SuperNova is terminal-based, provides project-wide context, and can execute commands. Copilot focuses on in-editor code completion.

**Q: Can I use SuperNova with private repositories?**
A: Yes, SuperNova works with any Git repository you have locally, including private ones.

---

*This wiki is for SuperNova v0.0.48-alpha. Features and capabilities may change in future releases.* 