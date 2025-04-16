# Contributing to SuperNova

Thank you for your interest in contributing to SuperNova! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

### Development Setup

1. **Fork the repository** on GitHub.

2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/supernova.git
   cd supernova
   ```

3. **Set up your development environment**:
   ```bash
   # Create a virtual environment (recommended)
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install in development mode
   pip install -e .
   
   # Install development dependencies
   pip install pytest pytest-cov black mypy isort pylint
   ```

4. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

1. **Make your changes** in your feature branch.

2. **Follow code style guidelines** (see below).

3. **Write or update tests** as needed.

4. **Run tests** to ensure everything works:
   ```bash
   pytest
   ```

5. **Format your code**:
   ```bash
   black supernova tests
   isort supernova tests
   ```

6. **Run static analysis**:
   ```bash
   mypy supernova
   pylint supernova
   ```

7. **Commit your changes** with clear, descriptive commit messages:
   ```bash
   git commit -m "Add feature: clear description of the changes"
   ```

8. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

9. **Create a pull request** from your fork to the main repository.

## Pull Request Process

1. Ensure your PR addresses a specific issue. If no issue exists, create one first.
2. Update documentation as needed.
3. Include tests that cover your changes.
4. Ensure all tests pass, and code quality checks pass.
5. Request review from maintainers.
6. Be responsive to feedback and be prepared to make changes to your PR if requested.

## Coding Standards

SuperNova follows these coding standards:

### Python Specific

- Code formatting with **Black** using a line length of 88 characters
- Import sorting with **isort** (profile=black)
- Type hints for all function parameters and return values
- Docstrings for all modules, classes, and functions (Google style)
- Follow PEP 8 conventions for naming:
  - `snake_case` for functions and variables
  - `PascalCase` for classes
  - `UPPER_CASE` for constants

### Example Function

```python
def process_file(file_path: str, max_lines: int = 100) -> Dict[str, Any]:
    """
    Process a file and extract relevant information.
    
    Args:
        file_path: Path to the file to process
        max_lines: Maximum number of lines to process
        
    Returns:
        Dictionary containing the processed information
        
    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    # Implementation
    pass
```

## Testing Guidelines

- All new features should include tests
- Aim for at least 80% code coverage
- Use pytest for running tests
- Structure tests in the `tests/` directory mirroring the package structure
- Name test files with `test_` prefix and test functions with `test_` prefix

## Documentation Guidelines

- Update documentation when adding or changing features
- README.md should contain user-facing documentation
- Code should be self-documenting with clear function and variable names
- Add comments only when necessary to explain "why", not "what" or "how"

## Adding New Tools

When adding a new tool to SuperNova:

1. Create a new file in `supernova/tools/` or `supernova/extensions/`
2. Implement the tool by extending `SupernovaTool` base class
3. Add comprehensive docstrings and type hints
4. Write tests for the tool in `tests/tools/` or `tests/extensions/`
5. Update any relevant documentation

Example tool implementation:

```python
from supernova.core.tool_base import SupernovaTool

class NewTool(SupernovaTool):
    name = "new_tool"
    description = "Description of what this tool does"
    
    def get_arguments_schema(self):
        return {
            "type": "object",
            "properties": {
                "arg1": {"type": "string", "description": "Description of arg1"}
            },
            "required": ["arg1"]
        }
    
    def get_usage_examples(self):
        return [{
            "description": "Example usage of new_tool",
            "arguments": {"arg1": "example_value"}
        }]
    
    def execute(self, **kwargs):
        # Implementation
        return {"success": True, "result": "Tool execution result"}
```

## Issue Reporting

When reporting issues, please include:

1. The exact steps to reproduce the issue
2. What you expected to happen
3. What actually happened
4. Your environment (OS, Python version, etc.)
5. Any logs or error messages

You can use this template for bug reports:

```
## Description
A clear description of the issue

## Steps to Reproduce
1. Step 1
2. Step 2
3. ...

## Expected Behavior
What you expected to happen

## Actual Behavior
What actually happened

## Environment
- OS: [e.g., Ubuntu 22.04, macOS 13.0]
- Python version: [e.g., 3.10.4]
- SuperNova version: [e.g., 0.0.48-alpha]

## Additional Context
Any other information that might be relevant
```

## Feature Requests

For feature requests, please describe:

1. What problem the feature would solve
2. How you envision the feature working
3. Why it would be valuable to the project

## Questions?

If you have any questions about contributing, feel free to open an issue labeled as "question" in the GitHub repository.

Thank you for contributing to SuperNova! 
