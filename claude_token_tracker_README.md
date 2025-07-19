# Claude Pro Token Usage Tracker

A command-line tool to track token usage for Claude Pro accounts.

## Overview

This script helps you monitor your Claude Pro API token usage. It provides information about your current usage and rate limits, helping you manage your consumption and avoid hitting limits unexpectedly.

## Features

- Securely authenticates with your Anthropic API key
- Displays current rate limit information
- Shows when rate limits will reset
- Provides information about the 5-hour rolling window for Claude Pro
- Includes error handling for common issues like invalid API keys
- Offers a sample mode to check actual rate limit headers
- Supports verbose output for debugging

## Installation

1. Clone or download this repository
2. Install the required dependencies:

```bash
pip install -r claude_token_tracker_requirements.txt
```

### Minimal Installation

If you're having trouble with all dependencies, you can just install the minimal required dependency:

```bash
pip install requests
```

The script will run with reduced functionality but will still provide basic token usage information.

## Usage

You can run the script using:

```bash
python claude_token_tracker.py
```

The script will use the `ANTHROPIC_API_KEY` environment variable by default. You can also provide your API key as a command-line argument:

```bash
python claude_token_tracker.py --api-key "your-api-key"
```

### Command-line Options

- `--api-key`: Your Anthropic API key (optional if `ANTHROPIC_API_KEY` env var is set)
- `--model`: Claude model to check (default: claude-3-7-sonnet-20250219)
- `--sample`: Run a sample message to check actual rate limit headers
- `--verbose`: Show verbose output including masked API key

### Examples

Basic usage:
```bash
python claude_token_tracker.py
```

Check a specific model:
```bash
python claude_token_tracker.py --model claude-3-opus-20240229
```

Run a sample message to check rate limits:
```bash
python claude_token_tracker.py --sample
```

Show verbose output:
```bash
python claude_token_tracker.py --verbose
```

## Important Notes

- The script uses the free token counting endpoint to check API key validity
- To get accurate rate limit headers, use the `--sample` flag (this will use tokens)
- Claude Pro typically has a 5-hour rolling window for rate limits
- For detailed usage statistics, visit the Anthropic Console
- This script only provides information that's available via API headers

## Security

- Your API key is never stored or transmitted outside of the API requests
- When using `--verbose`, only a masked version of your API key is displayed
- The script only makes requests to official Anthropic endpoints

## Limitations

- Anthropic doesn't provide a specific endpoint to retrieve historical token usage
- The displayed limits represent the most restrictive limit currently in effect
- For complete usage statistics, you need to use the Anthropic Console

## License

This project is open-source and available under the MIT License.
