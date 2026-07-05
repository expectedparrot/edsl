"""AgentList creation commands for the EDSL CLI."""

from __future__ import annotations

from pathlib import Path

import click

from edsl.cli_shared import EXIT_ERROR, EXIT_USAGE, error, output, raw_output_written, save_edsl_object


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
        """Create an AgentList from a tabular data source."""
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
