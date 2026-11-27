"""Read tabular records from a saved ScenarioList."""

import json
from pathlib import Path

import click

from edsl.cli_shared import (
    EXIT_USAGE,
    EXIT_VALIDATION,
    error,
    load_any_object,
    output,
    private_output,
)


@click.command("show")
@click.argument("scenarios_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--offset",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="Skip this many rows.",
)
@click.option(
    "--limit",
    type=click.IntRange(min=0),
    default=10,
    show_default=True,
    help="Maximum rows. Use 0 for all remaining rows.",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write the selected rows as a JSON array instead of including them in stdout.",
)
def show(scenarios_path, offset, limit, output_path):
    """Read scenario rows in their saved order. Use --limit 0 -o rows.json for a complete export."""
    from edsl import ScenarioList

    try:
        obj = load_any_object(str(scenarios_path), preview=True)
    except Exception as exc:
        suggestion = "Pass a saved ScenarioList."
        if scenarios_path.suffix == ".ep":
            suggestion = (
                "If you have the source CSV, rebuild into a new file, for example "
                "'ep scenarios create --from-csv SOURCE.csv --output rebuilt.ep'. "
                "Run 'ep scenarios show rebuilt.ep --limit 1' and check total_rows."
            )
        error(
            "VALIDATION_ERROR", str(exc), suggestion=suggestion, exit_code=EXIT_VALIDATION
        )

    try:
        if not isinstance(obj, ScenarioList):
            raise ValueError(f"Expected ScenarioList, found {type(obj).__name__}.")
        end = min(offset + limit, len(obj)) if limit else len(obj)
        rows = [obj[i].to_dict(add_edsl_version=False) for i in range(offset, end)]
        data = {
            "object_type": "ScenarioList",
            "total_rows": len(obj),
            "offset": offset,
            "returned_rows": len(rows),
            "has_more": end < len(obj),
        }
        if output_path is None:
            output({**data, "rows": rows})
            return
        same = output_path.exists() and output_path.samefile(scenarios_path)
        inside = (
            scenarios_path.is_dir()
            and scenarios_path.resolve() in output_path.resolve().parents
        )
        if output_path.suffix.lower() != ".json" or same or inside:
            error(
                "USAGE_ERROR",
                "Choose a separate .json file for the row export.",
                exit_code=EXIT_USAGE,
            )
        with private_output(output_path) as temp:
            temp.write_text(
                json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        output({**data, "saved": {"path": str(output_path), "format": "json"}})
    except Exception as exc:
        error(
            "VALIDATION_ERROR",
            str(exc),
            suggestion="Pass a saved ScenarioList and a separate JSON output path.",
            exit_code=EXIT_VALIDATION,
        )
