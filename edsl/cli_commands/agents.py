"""AgentList creation commands for the EDSL CLI."""

from __future__ import annotations

import json
from pathlib import Path

import click

from edsl.cli_shared import EXIT_ERROR, EXIT_USAGE, error, load_any_object, output, raw_output_written, save_edsl_object


def register(agents_group: click.Group) -> None:
    @agents_group.command("create")
    @click.option("--from-csv", "csv_path", default=None, type=click.Path(exists=True), help="Create from a CSV file.")
    @click.option("--from-xlsx", "xlsx_path", default=None, type=click.Path(exists=True), help="Create from an Excel file.")
    @click.option("--sheet", default=None, help="Excel sheet name.")
    @click.option("--name-field", default=None, help="Column to use as Agent.name instead of a trait.")
    @click.option("--instructions", default=None, help="Shared instruction string or path to a text file.")
    @click.option("--codebook", default=None, help="Codebook dict JSON string or path supported by AgentList.from_source.")
    @click.option("--output", "-o", "output_path", required=True, help="Output .ep package or serialized file.")
    def create_agents(
        csv_path: str | None,
        xlsx_path: str | None,
        sheet: str | None,
        name_field: str | None,
        instructions: str | None,
        codebook: str | None,
        output_path: str,
    ):
        """Create an AgentList from a tabular data source.

        \b
        Examples:
          ep agents create --from-csv people.csv --output agents.ep
          ep agents create --from-csv people.csv --name-field name --output agents.ep
          ep agents create --from-csv people.csv --instructions instructions.txt --output agents.ep
          ep agents create --from-csv people.csv --instructions "Answer as this respondent." --output agents.ep
          ep agents create --from-csv people.csv --codebook '{"age":"Age in years","role":"Current role"}' --output agents.ep
          ep agents create --from-xlsx people.xlsx --sheet Sheet1 --name-field respondent_id --output agents.ep
          ep agents create --from-csv people.csv --output agents.json
          ep agents create --from-csv people.csv --output - > agents.json

        \b
        Next:
          ep inspect agents.ep
          ep run --survey survey.ep --agent_list agents.ep --model gpt-4o
        """
        source_count = sum(bool(value) for value in (csv_path, xlsx_path))
        if source_count != 1:
            error(
                "USAGE_ERROR",
                "Provide exactly one source: --from-csv or --from-xlsx.",
                exit_code=EXIT_USAGE,
            )

        try:
            from edsl import AgentList

            kwargs = {}
            if name_field:
                kwargs["name_field"] = name_field
            if instructions:
                kwargs["instructions"] = _read_text_or_value(instructions)
            if codebook:
                kwargs["codebook"] = codebook

            if csv_path:
                agents = AgentList.from_source("csv", csv_path, **kwargs)
                source = csv_path
            else:
                if sheet:
                    kwargs["sheet_name"] = sheet
                agents = AgentList.from_source("excel", xlsx_path, **kwargs)
                source = xlsx_path

            saved = save_edsl_object(agents, output_path, object_type="AgentList")
            if raw_output_written(saved):
                return
            output(
                {
                    "object_type": "AgentList",
                    "source": source,
                    "agent_count": len(agents),
                    "trait_keys": sorted(_trait_keys(agents)),
                    "saved": saved,
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error(
                "AGENTS_CREATE_ERROR",
                str(e),
                suggestion="Check the input data, column names, and output path.",
                exit_code=EXIT_ERROR,
            )

    @agents_group.command("transform")
    @click.argument("agents_path")
    @click.option("--select", "select_traits", multiple=True, help="Trait to keep. Repeat for multiple traits.")
    @click.option("--drop", "drop_traits", multiple=True, help="Trait to drop. Repeat for multiple traits.")
    @click.option("--rename", "renames", multiple=True, help="Rename trait as OLD=NEW. Repeat for multiple traits.")
    @click.option("--filter", "filter_expression", default=None, help="Filter expression evaluated against agent traits.")
    @click.option("--sample", "sample_n", default=None, type=int, help="Sample N agents.")
    @click.option("--shuffle", is_flag=True, default=False, help="Shuffle agents.")
    @click.option("--seed", default=None, help="Seed for sample/shuffle.")
    @click.option("--add-trait", "add_traits", multiple=True, help="Add trait as NAME=JSON. JSON may be a scalar or list.")
    @click.option("--remove-trait", "remove_traits", multiple=True, help="Trait to remove. Repeat for multiple traits.")
    @click.option("--output", "-o", "output_path", default=None, help="Output .ep package, serialized file, or '-' for raw JSON stdout. Defaults to AGENTS_PATH.")
    def transform_agents(
        agents_path: str,
        select_traits: tuple[str, ...],
        drop_traits: tuple[str, ...],
        renames: tuple[str, ...],
        filter_expression: str | None,
        sample_n: int | None,
        shuffle: bool,
        seed: str | None,
        add_traits: tuple[str, ...],
        remove_traits: tuple[str, ...],
        output_path: str | None,
    ):
        """Transform an existing AgentList.

        \b
        Examples:
          ep agents transform agents.ep --select age --select role --output slim_agents.ep
          ep agents transform agents.ep --filter "age >= 30" --sample 10 --seed demo
          ep agents transform agents.ep --rename role=occupation --add-trait cohort='"A"'
        """
        try:
            from edsl import AgentList

            agents = load_any_object(agents_path)
            if not isinstance(agents, AgentList):
                error("UNSUPPORTED_OBJECT", f"Expected an AgentList object, got {type(agents).__name__}.", exit_code=EXIT_USAGE)

            if filter_expression:
                agents = agents.filter(filter_expression)
            if select_traits:
                agents = agents.select(*select_traits)
            if drop_traits:
                agents = agents.drop(*drop_traits)
            for old_name, new_name in _parse_renames(renames).items():
                agents = agents.rename(old_name, new_name)
            for trait_name, value in _parse_json_assignments(add_traits).items():
                agents = agents.add_trait(trait_name, value if isinstance(value, list) else [value] * len(agents))
            for trait_name in remove_traits:
                agents = agents.remove_trait(trait_name)
            if shuffle:
                agents = agents.shuffle(seed=seed)
            if sample_n is not None:
                agents = agents.sample(sample_n, seed=seed)

            saved = save_edsl_object(agents, output_path or agents_path, object_type="AgentList")
            if raw_output_written(saved):
                return
            output(
                {
                    "object_type": "AgentList",
                    "agent_count": len(agents),
                    "trait_keys": sorted(_trait_keys(agents)),
                    "saved": saved,
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error(
                "AGENTS_TRANSFORM_ERROR",
                str(e),
                suggestion="Check the AgentList path, trait names, filter expression, and output path.",
                exit_code=EXIT_ERROR,
            )


def _read_text_or_value(value: str) -> str:
    path = Path(value)
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8")
    return value


def _trait_keys(agents) -> set[str]:
    keys = set()
    for agent in agents:
        keys.update((getattr(agent, "traits", None) or {}).keys())
    return keys


def _parse_renames(items: tuple[str, ...]) -> dict[str, str]:
    renames = {}
    for item in items:
        if "=" not in item:
            error("USAGE_ERROR", f"Invalid rename {item!r}; expected OLD=NEW.", exit_code=EXIT_USAGE)
        old_name, new_name = item.split("=", 1)
        renames[old_name] = new_name
    return renames


def _parse_json_assignments(items: tuple[str, ...]) -> dict[str, object]:
    assignments = {}
    for item in items:
        if "=" not in item:
            error("USAGE_ERROR", f"Invalid assignment {item!r}; expected NAME=JSON.", exit_code=EXIT_USAGE)
        key, raw_value = item.split("=", 1)
        try:
            assignments[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            assignments[key] = raw_value
    return assignments
