"""
EDSL CLI — agent-friendly interface. All output is JSON on stdout.

Entry point: ep = "edsl.__main__:main" (pyproject.toml)
"""

import sys

import click

from edsl.cli_commands import account as account_commands
from edsl.cli_commands import agents as agents_commands
from edsl.cli_commands import auth as auth_commands
from edsl.cli_commands import costs as costs_commands
from edsl.cli_commands import humanize as humanize_commands
from edsl.cli_commands import inspect as inspect_commands
from edsl.cli_commands import jobs as jobs_commands
from edsl.cli_commands import models as models_commands
from edsl.cli_commands import objects as objects_commands
from edsl.cli_commands import open as open_commands
from edsl.cli_commands import profiles as profiles_commands
from edsl.cli_commands import results as results_commands
from edsl.cli_commands import run as run_commands
from edsl.cli_commands import schema as schema_commands
from edsl.cli_commands import scenarios as scenarios_commands
from edsl.cli_commands import surveys as surveys_commands
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
                "check",
                "inspect",
                "info",
                "validate",
                "objects",
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
                "profiles",
                "settings",
                "humanize",
                "schema",
                "agents",
                "scenarios",
                "auth",
                "results",
                "jobs",
                "surveys",
                "costs",
            ],
            "help": "Use 'ep <command> --help' for details on each command.",
            "pipe_contract": {
                "durable_objects": "Use .ep paths for durable git-backed object packages.",
                "pipeable_objects": "Use '-' for raw obj.to_dict() JSON on stdin/stdout.",
                "envelopes": "Normal command output is a status envelope; --output - emits raw object JSON for piping.",
            },
        })


@app.group(invoke_without_command=True)
@click.pass_context
def objects(ctx):
    """Manage Expected Parrot objects."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": [
                "search",
                "clone",
                "push",
                "pull",
                "metadata",
                "update-metadata",
                "share",
                "shared",
                "unshare",
                "delete",
            ],
            "help": "Use 'ep objects <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def schema(ctx):
    """Introspect object schemas for construction.

    \b
    Examples:
      ep schema list
      ep schema show --class Survey
      ep schema show --class AgentList
      ep schema show --question_type multiple_choice
      ep schema error
    """
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["list", "show", "error"],
            "help": "Use 'ep schema <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def auth(ctx):
    """Authentication management."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["login", "status", "balance"],
            "help": "Use 'ep auth <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def profiles(ctx):
    """Manage local Expected Parrot environment profiles."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["list", "current", "show", "create", "update", "set", "check"],
            "help": "Use 'ep profiles <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def results(ctx):
    """Query and extract data from Results files.

    \b
    Examples:
      ep results summary results.ep
      ep results columns --file results.ep
      ep results select --file results.ep --column answer.q0 --column agent.age --limit 10
      ep results select --file results.ep --filter "agent.age > 30" --csv
      ep results export results.ep --column answer.q0 --format csv --output answers.csv
      ep results cost results.ep
    """
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["columns", "select", "head", "sample", "values", "first", "export", "summary", "cost"],
            "help": "Use 'ep results <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def jobs(ctx):
    """Inspect and manage remote jobs.

    \b
    Examples:
      ep jobs build --survey survey.ep --agents agents.ep --scenarios scenarios.ep --models models.ep --output jobs.ep
      ep run --jobs jobs.ep --background
      ep jobs list --status completed --page_size 20
      ep jobs status <job_uuid>
      ep jobs results <job_uuid> --output results.ep
      ep jobs errors <job_uuid>
    """
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["build", "list", "status", "wait", "results", "errors", "manifest", "page", "cancel", "cost"],
            "help": "Use 'ep jobs <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def agents(ctx):
    """Create and inspect AgentList objects.

    \b
    Examples:
      ep agents create --from-csv people.csv --output agents.ep
      ep agents create --from-csv people.csv --name-field name --instructions instructions.txt --output agents.ep
      ep agents create --from-xlsx people.xlsx --sheet Sheet1 --name-field respondent_id --output agents.ep
      ep agents create --from-csv people.csv --codebook '{"age":"Age in years"}' --output agents.json
      ep inspect agents.ep
      ep run --survey survey.ep --agent_list agents.ep --model gpt-4o

    \b
    Use 'ep agents create --help' for all creation options.
    """
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["create"],
            "help": "Use 'ep agents <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def scenarios(ctx):
    """Create and inspect ScenarioList objects.

    \b
    Examples:
      ep scenarios create --from-csv topics.csv --output scenarios.ep
      ep scenarios create --from-xlsx topics.xlsx --sheet Sheet1 --output scenarios.ep
      ep scenarios create --from-image image1.png --from-image image2.png --output image_scenarios.ep
      ep inspect scenarios.ep
      ep run --survey survey.ep --scenario_list scenarios.ep --model gpt-4o
    """
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["create"],
            "help": "Use 'ep scenarios <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def surveys(ctx):
    """Create and inspect Survey objects.

    \b
    Examples:
      ep surveys create --question-type free_text --question-name q0 --question-text "What do you think?" --output survey.ep
      ep surveys add-question survey.ep --question-type multiple_choice --question-name q1 --question-text "Pick one." --option A --option B
      ep surveys questions survey.ep
      ep surveys add-skip-rule survey.ep --question q1 --expression "{{ q0.answer }} == 'skip'"
      ep inspect survey.ep
    """
    if ctx.invoked_subcommand is None:
        _output({
            "commands": [
                "create", "add-question", "drop-question", "move-question",
                "show", "questions", "add-skip-rule", "add-stop-rule",
            ],
            "help": "Use 'ep surveys <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def costs(ctx):
    """Track estimated and actual job costs.

    \b
    Examples:
      ep costs log --output costs.jsonl --estimated 1.25 --model gpt-4o --agents 10 --questions 5
      ep costs log --output costs.jsonl --actual-from results.ep --note "pilot run"
      ep results cost results.ep
    """
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["log"],
            "help": "Use 'ep costs <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def humanize(ctx):
    """Create and manage human surveys.

    \b
    Examples:
      ep humanize create --survey survey.ep --name "Customer feedback"
      ep humanize list
      ep humanize status <humanize_uuid>
      ep humanize responses <humanize_uuid> --output results.ep
      ep humanize preview <humanize_uuid>
    """
    if ctx.invoked_subcommand is None:
        _output({
            "commands": [
                "list", "create", "status", "responses", "qr", "preview",
                "respondents", "schedules", "deliveries", "callbacks",
                "agent-list", "schema", "css", "prolific",
            ],
            "help": "Use 'ep humanize <command> --help' for details.",
        })




account_commands.register(app)
agents_commands.register(agents)
auth_commands.register(app, auth)
costs_commands.register(costs)
humanize_commands.register(humanize)
inspect_commands.register(app)
jobs_commands.register(jobs)
models_commands.register(app)
objects_commands.register(app)
for command_name in [
    "search",
    "clone",
    "push",
    "pull",
    "metadata",
    "update-metadata",
    "share",
    "shared",
    "unshare",
    "delete",
]:
    objects.add_command(app.commands[command_name], command_name)
open_commands.register(app)
profiles_commands.register(app, profiles)
results_commands.register(results)
run_commands.register(app)
schema_commands.register(schema)
scenarios_commands.register(scenarios)
surveys_commands.register(surveys)
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
               suggestion=f"Run 'ep {' '.join(sys.argv[1:])} --help' for usage.",
               exit_code=EXIT_USAGE)
    except click.exceptions.BadParameter as e:
        _error("USAGE_ERROR", str(e), exit_code=EXIT_USAGE)
    except click.exceptions.UsageError as e:
        _error("USAGE_ERROR", str(e), exit_code=EXIT_USAGE)
    except click.exceptions.ClickException as e:
        _error("USAGE_ERROR", e.format_message(), exit_code=EXIT_USAGE)


if __name__ == "__main__":
    main()
