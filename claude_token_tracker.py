#!/usr/bin/env python3
"""
Claude Pro Token Usage Tracker

A command-line tool to track token usage for Claude Pro accounts
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

# Check for required dependencies
missing_deps = []
try:
    import requests
except ImportError:
    missing_deps.append("requests")

try:
    import anthropic

    has_anthropic = True
except ImportError:
    has_anthropic = False

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    has_rich = True
except ImportError:
    has_rich = False

# Handle missing critical dependencies
if "requests" in missing_deps:
    print("Error: Missing critical dependency:")
    print("  - requests")
    print("\nPlease install the required dependency:")
    print("pip install requests")
    sys.exit(1)

# Create simple console if rich is not available
if has_rich:
    console = Console()
else:
    # Simple console fallback
    class SimpleConsole:
        def print(self, text):
            # Remove rich formatting
            text = text.replace("[bold]", "").replace("[/bold]", "")
            text = text.replace("[bold red]", "").replace("[/bold red]", "")
            text = text.replace("[bold blue]", "").replace("[/bold blue]", "")
            text = text.replace("[bold green]", "").replace("[/bold green]", "")
            text = text.replace("[bold yellow]", "").replace("[/bold yellow]", "")
            text = text.replace("[yellow]", "").replace("[/yellow]", "")
            text = text.replace("[green]", "").replace("[/green]", "")
            text = text.replace("[cyan]", "").replace("[/cyan]", "")
            print(text)

        def status(self, text):
            class DummyContextManager:
                def __enter__(self):
                    print(text.replace("[bold green]", "").replace("[/bold green]", ""))
                    return self

                def __exit__(self, *args):
                    pass

            return DummyContextManager()

    console = SimpleConsole()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Track Claude Pro token usage and limits")
    parser.add_argument(
        "--api-key",
        help="Your Anthropic API key (can also be set via ANTHROPIC_API_KEY environment variable)",
    )
    parser.add_argument(
        "--model",
        default="claude-3-7-sonnet-20250219",
        help="Claude model to check (default: claude-3-7-sonnet-20250219)",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Run a sample message to check rate limit headers",
    )
    parser.add_argument("--verbose", action="store_true", help="Show verbose output")

    return parser.parse_args()


def get_api_key(args):
    """Get API key from args or environment variable."""
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/bold red] No API key provided.")
        console.print("Please either:")
        console.print("  1. Set the ANTHROPIC_API_KEY environment variable")
        console.print("  2. Pass the API key using the --api-key flag")
        sys.exit(1)
    return api_key


def check_api_key_validity(api_key):
    """Check if the API key is valid."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        # Using the token counting endpoint to validate the API key
        response = requests.post(
            "https://api.anthropic.com/v1/messages/count_tokens",
            headers=headers,
            json={
                "model": "claude-3-7-sonnet-20250219",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            console.print("[bold red]Error:[/bold red] Invalid API key.")
            return False
        else:
            console.print(f"[bold red]Error:[/bold red] Unexpected response: {response.status_code}")
            console.print(response.text)
            return False
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        return False


def get_rate_limit_info(api_key, model, sample=False):
    """Get rate limit information from a sample API call."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    rate_limit_info = {}

    try:
        if sample:
            # Make a real API call to get rate limit headers
            console.print("[yellow]Running a sample message to check rate limits...[/yellow]")
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json={
                    "model": model,
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Hello, what time is it?"}],
                },
            )
        else:
            # Just use the token counting endpoint which is free
            response = requests.post(
                "https://api.anthropic.com/v1/messages/count_tokens",
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )

        # Extract rate limit headers
        for key, value in response.headers.items():
            if key.lower().startswith("anthropic-ratelimit"):
                rate_limit_info[key] = value

        return rate_limit_info
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        return {}


def display_usage_info(api_key, model, rate_limit_info, verbose):
    """Display token usage and rate limit information."""
    if has_rich:
        console.print(
            Panel(
                f"[bold blue]Claude Pro Token Usage Tracker[/bold blue]",
                box=box.ROUNDED,
            )
        )
    else:
        console.print("===== Claude Pro Token Usage Tracker =====")

    console.print(f"[bold]Model:[/bold] {model}")
    console.print(f"[bold]Current time:[/bold] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Display rate limit information
    if rate_limit_info:
        if has_rich:
            table = Table(title="Rate Limit Information", box=box.MINIMAL_HEAVY_HEAD)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            for key, value in rate_limit_info.items():
                # Format the key for better readability
                formatted_key = key.replace("anthropic-ratelimit-", "").replace("-", " ").title()
                table.add_row(formatted_key, value)

            console.print(table)
        else:
            console.print("\nRate Limit Information:")
            console.print("-----------------------")
            for key, value in rate_limit_info.items():
                # Format the key for better readability
                formatted_key = key.replace("anthropic-ratelimit-", "").replace("-", " ").title()
                console.print(f"{formatted_key}: {value}")

        # Display reset times in a more user-friendly format
        for key, value in rate_limit_info.items():
            if "reset" in key:
                try:
                    reset_time = datetime.fromtimestamp(int(value))
                    time_until_reset = reset_time - datetime.now()
                    minutes, seconds = divmod(time_until_reset.seconds, 60)
                    console.print(
                        f"[bold]{key.replace('anthropic-ratelimit-', '').replace('-', ' ').title()}:[/bold] {reset_time.strftime('%Y-%m-%d %H:%M:%S')} (in {minutes}m {seconds}s)"
                    )
                except (ValueError, TypeError):
                    # Skip if we can't parse the reset time
                    pass
    else:
        console.print("[yellow]No rate limit information available.[/yellow]")

    console.print("\n[bold]Usage Notes:[/bold]")
    console.print("• Claude Pro typically has a 5-hour rolling window for rate limits")
    console.print("• The displayed limits are for the most restrictive limit currently in effect")
    console.print("• For detailed usage, visit the Anthropic Console: https://console.anthropic.com")

    if verbose:
        console.print("\n[bold]API Key Information:[/bold]")
        masked_key = api_key[:4] + "..." + api_key[-4:]
        console.print(f"Using API key: {masked_key}")


def main():
    """Main function."""
    args = parse_args()
    api_key = get_api_key(args)

    with console.status("[bold green]Checking API key validity...[/bold green]"):
        if not check_api_key_validity(api_key):
            sys.exit(1)

    with console.status("[bold green]Fetching token usage information...[/bold green]"):
        rate_limit_info = get_rate_limit_info(api_key, args.model, args.sample)

    display_usage_info(api_key, args.model, rate_limit_info, args.verbose)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Operation cancelled by user.[/bold yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)
