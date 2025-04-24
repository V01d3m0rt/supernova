# Directory Restructure Plan for SuperNova

This document outlines a plan for reorganizing the SuperNova codebase to improve maintainability, reduce duplication, and apply SOLID principles.

## Current Structure Analysis

Current directory structure:
```
supernova/
├── __init__.py
├── cli/
├── core/
│   ├── command_executor.py (new)
│   ├── command_runner.py
│   ├── context_analyzer.py
│   ├── llm_provider.py
│   ├── tool_base.py
├── config/
├── extensions/
│   ├── example_tool.py
│   ├── file_create_tool.py
│   ├── file_info_tool.py
│   ├── file_stats.py
├── integrations/
├── persistence/
└── tools/
    └── terminal_command_tool.py
```

Issues identified:
1. File tools are split between `extensions/` and `tools/`
2. No clear organization of tools by functionality
3. `tool_base.py` contains both `SupernovaTool` base class and `FileToolMixin`
4. Some large files with multiple responsibilities

## Proposed Structure

```
supernova/
├── __init__.py
├── cli/                  # CLI interface (unchanged)
├── config/               # Configuration (unchanged)
├── core/                 # Core functionality
│   ├── command/          # Command execution related
│   │   ├── __init__.py
│   │   ├── executor.py   # Unified command execution
│   │   └── runner.py     # High-level command runner
│   ├── context/          # Context management
│   │   ├── __init__.py
│   │   └── analyzer.py
│   ├── llm/              # LLM integration
│   │   ├── __init__.py
│   │   └── provider.py
│   └── tool/             # Tool base classes
│       ├── __init__.py
│       ├── base.py       # SupernovaTool base class
│       └── mixins/       # Mixins for tools
│           ├── __init__.py
│           ├── file.py   # FileToolMixin
│           └── command.py # CommandToolMixin
├── integrations/         # External integrations (unchanged)
├── persistence/          # Data persistence (unchanged)
└── tools/                # All tools in one place, organized by category
    ├── __init__.py       # Tool registry
    ├── command/          # Command-related tools
    │   ├── __init__.py
    │   └── terminal.py   # Terminal command tool
    ├── file/             # File operation tools
    │   ├── __init__.py
    │   ├── create.py     # File creation tool
    │   ├── info.py       # File info tool
    │   └── stats.py      # File statistics tool
    └── example/          # Example tools (for development/documentation)
        ├── __init__.py
        └── demo.py       # Demo tool
```

## Migration Plan

The migration will be implemented in these steps:

1. Create the new directory structure
2. Move and refactor the core classes
   - Split `tool_base.py` into separate files
   - Update imports in all affected files
3. Reorganize tool files
   - Move file tools from `extensions/` to `tools/file/`
   - Move terminal command tool from `tools/` to `tools/command/`
4. Ensure all imports are updated correctly
5. Add tool registry in `tools/__init__.py`
6. Update tests to reflect the new structure

## Advantages of New Structure

1. **Better Organization**: Tools are grouped by functionality
2. **Reduced Coupling**: Cleaner separation of concerns
3. **Improved Discoverability**: Tools follow a logical naming and organizational pattern
4. **Easier Maintenance**: Smaller, more focused files
5. **Better Scalability**: New tool categories can be added without cluttering directories
6. **Consistent Imports**: All tools can be imported from the same package

## Implementation Details

Each file in the new structure will have a clear single responsibility:

- `core/tool/base.py`: Only the `SupernovaTool` abstract base class
- `core/tool/mixins/file.py`: Only the `FileToolMixin` class
- `core/command/executor.py`: Only the `CommandExecutor` class

When importing tools:
```python
# Old way
from supernova.tools.terminal_command_tool import TerminalCommandTool
from supernova.extensions.file_create_tool import FileCreateTool

# New way
from supernova.tools.command.terminal import TerminalCommandTool
from supernova.tools.file.create import FileCreateTool

# Or with tool registry
from supernova.tools import get_tool
terminal_tool = get_tool("terminal_command")
``` 