"""
EDSL CLI — agent-friendly interface. All output is JSON on stdout.

Entry point: edsl = "edsl.__main__:main" (pyproject.toml)
"""

import sys

import click

from edsl.cli_commands import account as account_commands
from edsl.cli_commands import auth as auth_commands
from edsl.cli_commands import humanize as humanize_commands
from edsl.cli_commands import jobs as jobs_commands
from edsl.cli_commands import models as models_commands
from edsl.cli_commands import objects as objects_commands
from edsl.cli_commands import open as open_commands
from edsl.cli_commands import results as results_commands
from edsl.cli_commands import run as run_commands
from edsl.cli_commands import schema as schema_commands
from edsl.cli_commands import validate as validate_commands
from edsl.cli_shared import (
    EXIT_AUTH,
    EXIT_ERROR,
    EXIT_NOT_FOUND,
    EXIT_REMOTE,
    EXIT_USAGE,
    EXIT_VALIDATION,
    error as _error,
    output as _output,
)


# ---------------------------------------------------------------------------
# Click app hierarchy
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.pass_context
def app(ctx):
    """EDSL CLI — run LLM surveys. All output is JSON."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": [
                "run",
                "models",
                "info",
                "validate",
                "open",
                "clone",
                "search",
                "push",
                "pull",
                "metadata",
                "update-metadata",
                "share",
                "unshare",
                "shared",
                "delete",
                "balance",
                "profile",
                "settings",
                "humanize",
                "schema",
                "auth",
                "results",
                "jobs",
            ],
            "help": "Use 'edsl <command> --help' for details on each command.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def schema(ctx):
    """Introspect object schemas for construction."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["list", "show", "error"],
            "help": "Use 'edsl schema <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def auth(ctx):
    """Authentication management."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["login", "status", "balance"],
            "help": "Use 'edsl auth <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def results(ctx):
    """Query and extract data from Results files."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["columns", "select"],
            "help": "Use 'edsl results <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def jobs(ctx):
    """Inspect and manage remote jobs."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["list", "status", "results", "errors", "manifest", "page", "cancel", "cost"],
            "help": "Use 'edsl jobs <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def humanize(ctx):
    """Create and manage human surveys."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": [
                "list", "create", "status", "responses", "qr", "preview",
                "respondents", "schedules", "deliveries", "callbacks",
                "agent-list", "schema", "css",
            ],
            "help": "Use 'edsl humanize <command> --help' for details.",
        })




account_commands.register(app)
auth_commands.register(app, auth)
humanize_commands.register(humanize)
jobs_commands.register(jobs)
models_commands.register(app)
objects_commands.register(app)
open_commands.register(app)
results_commands.register(results)
run_commands.register(app)
schema_commands.register(schema)
validate_commands.register(app)




# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    try:
        app(standalone_mode=False)
    except click.exceptions.MissingParameter as e:
        # Use the flag name (e.g. --type) not the Python variable name
        flag = e.param.opts[0] if e.param and e.param.opts else f"--{e.param.name}"
        _error("USAGE_ERROR", f"Missing required option: {flag}",
               suggestion=f"Run 'edsl {' '.join(sys.argv[1:])} --help' for usage.",
               exit_code=EXIT_USAGE)
    except click.exceptions.BadParameter as e:
        _error("USAGE_ERROR", str(e), exit_code=EXIT_USAGE)
    except click.exceptions.UsageError as e:
        _error("USAGE_ERROR", str(e), exit_code=EXIT_USAGE)
    except click.exceptions.ClickException as e:
        _error("USAGE_ERROR", e.format_message(), exit_code=EXIT_USAGE)


if __name__ == "__main__":
    main()
