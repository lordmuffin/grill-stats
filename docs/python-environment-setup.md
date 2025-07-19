# Python Virtual Environment Setup

This document provides instructions for setting up and managing the Python virtual environment for the Grill Stats project.

## Requirements

- Python 3.11 or higher
- pip (latest version)
- virtualenv or venv module

## Setup Options

You have two ways to set up the Python environment:

### Option 1: Using venv (Standard Python)

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt  # If you need test dependencies
pip install -r requirements-bluetooth.txt  # If you need bluetooth support

# Or install with optional dependencies using pyproject.toml
pip install -e ".[test,bluetooth,dev]"
```

### Option 2: Using Poetry (Recommended)

```bash
# Install Poetry if you don't have it
# https://python-poetry.org/docs/#installation

# Create and activate environment
poetry install

# Install optional dependencies
poetry install --extras "test bluetooth dev"
```

## Development Tools

The following development tools are configured:

- **flake8**: Code linting for syntax checking
- **black**: Code formatting
- **isort**: Import sorting
- **mypy**: Static type checking

### Running Development Tools

```bash
# Run flake8 for linting
flake8 .

# Run black for code formatting
black .

# Run isort for import sorting
isort .

# Run mypy for type checking
mypy .
```

## Managing Dependencies

### Adding New Dependencies

```bash
# Using pip
pip install new-package
pip freeze > requirements.txt

# Using poetry
poetry add new-package
```

### Updating Dependencies

```bash
# Using pip
pip install --upgrade package-name
pip freeze > requirements.txt

# Using poetry
poetry update package-name
```

## Environment Variables

Copy the `.env.example` file to `.env` and update the variables as needed:

```bash
cp .env.example .env
```

## Testing the Environment

After setting up your environment, you can verify it's working correctly:

```bash
# Run the application
python app.py

# Run tests
pytest
```

## CI/CD Integration

The Python virtual environment configuration is designed to work seamlessly with the project's CI/CD pipelines. The `pyproject.toml` file defines the project dependencies and development tool configurations that are used in the Gitea Actions workflows.

## Recommended VS Code Extensions

For optimal development experience in VS Code, install these extensions:

- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Black Formatter (ms-python.black-formatter)
- isort (ms-python.isort)
- Flake8 (ms-python.flake8)
- mypy (matangover.mypy)
