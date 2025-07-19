"""
Helper script to run mypy type checking with common settings.

This script helps run mypy with consistent settings across the codebase.
It provides guidance on fixing common type errors.
"""

import os
import subprocess
import sys
from typing import List, Optional


def run_mypy(files: Optional[List[str]] = None) -> int:
    """Run mypy on specified files or all Python files if not specified."""
    # Default mypy options
    mypy_options = [
        "--ignore-missing-imports",  # Ignore errors about imports without type hints
        "--disallow-untyped-defs",  # Disallow functions without type annotations
        "--disallow-incomplete-defs",  # Disallow incomplete type annotations
        "--check-untyped-defs",  # Check the body of functions without annotations
        "--disallow-untyped-decorators",  # Disallow decorators without type annotations
        "--no-implicit-optional",  # Don't treat arguments with default values as Optional
        "--warn-redundant-casts",  # Warn about casting an expression to its inferred type
        "--warn-return-any",  # Warn about returning Any from a typed function
        "--warn-unreachable",  # Warn about code that's unreachable
    ]

    mypy_cmd = ["mypy"] + mypy_options

    # If specific files are provided, use those; otherwise check all Python files
    if files:
        mypy_cmd.extend(files)
    else:
        # Find all Python files in the project
        mypy_cmd.append(".")

    print(f"Running: {' '.join(mypy_cmd)}")

    try:
        result = subprocess.run(mypy_cmd, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        # Return mypy's exit code
        return result.returncode
    except FileNotFoundError:
        print("Error: mypy not found. Install it with 'pip install mypy'", file=sys.stderr)
        return 1


def print_guidance() -> None:
    """Print guidance for fixing common mypy errors."""
    print("\n" + "=" * 80)
    print("MYPY TYPE CHECKING GUIDANCE")
    print("=" * 80)
    print(
        """
Common errors and how to fix them:

1. Function is missing a type annotation [no-untyped-def]
   def my_function(param):  # Missing return type
   Fix: def my_function(param) -> None:  # or appropriate return type

2. Function is missing a return type annotation [no-untyped-def]
   def get_value():  # Missing return type
   Fix: def get_value() -> str:  # or appropriate return type

3. Returning Any from function declared to return "X" [no-any-return]
   Fix: Add proper type conversions to ensure return value matches declared type

4. Item "None" of "X | None" has no attribute "y" [union-attr]
   Fix: Add a check for None before accessing attributes:
   if x is not None:
       x.y

5. Incompatible types in assignment [assignment]
   Fix: Ensure assigned value matches the variable's type,
   or use proper type conversion/casting

6. Library stubs not installed [import-untyped]
   Fix: Install type stubs (e.g., pip install types-redis)

7. Incompatible default for argument [assignment]
   Fix: Make the parameter type Optional or provide a default that matches the type
   def func(param: str = None)  # Wrong
   def func(param: Optional[str] = None)  # Correct

8. Function could always be true in boolean context [truthy-function]
   Fix: Use explicit comparison with None or check return value explicitly
   if function:  # Wrong
   if function is not None:  # Correct
   if function() is not None:  # Correct if checking return value
"""
    )
    print("=" * 80)


if __name__ == "__main__":
    # Get file list from command line arguments
    files_to_check = sys.argv[1:] if len(sys.argv) > 1 else None

    print_guidance()
    exit_code = run_mypy(files_to_check)

    if exit_code == 0:
        print("\nSuccess: No type errors found!")
    else:
        print("\nType errors found. Please fix them according to the guidance above.")

    sys.exit(exit_code)
