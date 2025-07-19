# Pre-commit Hooks Setup

This document explains the pre-commit hooks configuration for the Grill Stats project.

## Overview

Pre-commit hooks help ensure code quality by running automated checks before each commit. This prevents issues from being committed to the repository.

## Installation

1. Set up a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install pre-commit and required dependencies:
   ```bash
   pip install pre-commit flake8 black isort mypy
   ```

3. Install the git hooks:
   ```bash
   pre-commit install
   ```

## Configured Hooks

The following hooks are configured in the `.pre-commit-config.yaml` file:

### General Hooks
- **trailing-whitespace**: Trims trailing whitespace from files
- **end-of-file-fixer**: Ensures files end with a newline
- **check-yaml**: Validates YAML syntax
- **check-added-large-files**: Prevents large files from being committed
- **check-json**: Validates JSON syntax
- **check-merge-conflict**: Checks for merge conflict markers
- **debug-statements**: Checks for debugger imports and statements
- **detect-private-key**: Prevents committing private keys

### Python-specific Hooks
- **flake8**: Lints Python code for errors and style issues
  - Configured to check for syntax errors, undefined names, and other critical issues
- **black**: Formats Python code according to the Black code style
- **isort**: Sorts imports alphabetically and by type
  - Configured to use the Black profile for compatibility
- **mypy**: Performs static type checking
  - Configured with additional dependencies for Pydantic and Requests

## Usage

Once installed, the hooks will run automatically on every commit. If any checks fail, the commit will be aborted with an error message.

### Running Manually

You can run the pre-commit hooks manually on all files with:

```bash
pre-commit run --all-files
```

Or on specific files:

```bash
pre-commit run --files file1.py file2.py
```

### Skipping Hooks

In rare cases, you may need to bypass pre-commit hooks (not recommended). To do so:

```bash
git commit -m "Your message" --no-verify
```

## Customization

To modify the pre-commit configuration, edit the `.pre-commit-config.yaml` file and update the hooks or their settings.

## Best Practices

- Always run pre-commit hooks before pushing code
- Fix issues identified by the hooks rather than bypassing them
- Keep hook configurations up to date with project requirements
- Consider adding additional hooks as needed for specific project requirements
