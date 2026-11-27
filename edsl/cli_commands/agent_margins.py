"""Build a synthetic panel from separate, exact trait counts."""

import csv
from pathlib import Path

import click
from edsl.cli_shared import (
    EXIT_VALIDATION,
    error,
    output,
    raw_output_written,
    save_edsl_object,
)


@click.command("from-margins")
@click.argument(
    "csv_file", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    "--seed",
    required=True,
    type=int,
    help="Seed for assigning traits to synthetic respondents.",
)
@click.option(
    "--id-field",
    default="agent_id",
    show_default=True,
    help="Name of the generated unique ID trait.",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    required=True,
    help="AgentList package or serialized file.",
)
def from_margins(csv_file, seed, id_field, output_path):
    """Read a CSV with field, category and count columns. Category labels stay strings."""
    from edsl import AgentList
    from edsl.agents.exceptions import AgentErrors

    try:
        if (
            output_path != "-"
            and Path(output_path).exists()
            and csv_file.samefile(output_path)
        ):
            raise ValueError("Choose an output separate from the source CSV.")
        margins = {}
        with csv_file.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not {"field", "category", "count"}.issubset(reader.fieldnames or ()):
                raise ValueError("Expected CSV columns field, category and count.")
            for line, row in enumerate(reader, start=2):
                field, category = row["field"], row["category"]
                if not field or not category or row["count"] is None:
                    raise ValueError(f"Missing field, category or count on row {line}.")
                counts = margins.setdefault(field, {})
                if category in counts:
                    raise ValueError(
                        f"Duplicate {field!r}, {category!r} on row {line}."
                    )
                counts[category] = int(row["count"])
        agents = AgentList.from_margins(margins, seed=seed, id_field=id_field)
        saved = save_edsl_object(
            agents, output_path, object_type="AgentList", sync_coop=False
        )
    except (ValueError, OSError, csv.Error, AgentErrors) as exc:
        error(
            "AGENT_MARGINS_ERROR",
            str(exc),
            suggestion="Supply one row per trait/category and equal total counts per trait.",
            exit_code=EXIT_VALIDATION,
        )
    if not raw_output_written(saved):
        output(
            {
                "agent_count": len(agents),
                "margins": margins,
                "seed": seed,
                "id_field": id_field,
                "saved": saved,
            },
            warnings=[
                "Trait totals match the input. Joint counts in the generated panel are synthetic."
            ],
        )
