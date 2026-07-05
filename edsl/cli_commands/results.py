"""Results commands for the EDSL CLI."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from edsl.cli_shared import EXIT_ERROR, error, load_results_object, output


def register(results_group: click.Group) -> None:
    @results_group.command("columns")
    @click.option("--file", "file_path", required=True, help="Path to serialized Results .ep, JSON, or JSON.gz.")
    def results_columns(file_path):
        """List available columns in a Results file."""
        try:
            results_obj = load_results_object(file_path)
            output({"columns": sorted(results_obj.columns)})
        except Exception as e:
            error("VALIDATION_ERROR", f"Failed to load Results: {e}", exit_code=EXIT_ERROR)

    @results_group.command("select")
    @click.option("--file", "file_path", required=True, help="Path to serialized Results .ep, JSON, or JSON.gz.")
    @click.option("--column", multiple=True, help="Column to select. Repeat for multiple: --column answer.q0 --column agent.age")
    @click.option("--filter", "-f", "filter_expr", default=None, help="Filter expression.")
    @click.option("--order_by", default=None, help="Sort by column.")
    @click.option("--csv", "as_csv", is_flag=True, default=False, help="Output as CSV.")
    @click.option("--limit", default=None, type=int, help="Max rows.")
    def results_select(file_path, column, filter_expr, order_by, as_csv, limit):
        """Extract columns from a Results file with optional filtering."""
        try:
            results_obj = load_results_object(file_path)
        except Exception as e:
            error("VALIDATION_ERROR", f"Failed to load Results: {e}", exit_code=EXIT_ERROR)

        try:
            r = results_obj

            if filter_expr:
                r = r.filter(filter_expr)

            if order_by:
                r = r.order_by(order_by)

            if column:
                dataset = r.select(*column)
            else:
                dataset = r.select()

            rows = dataset.to_dicts(remove_prefix=False)

            if limit and limit > 0:
                rows = rows[:limit]

            if as_csv:
                import csv as csv_mod
                import io

                if rows:
                    buffer = io.StringIO()
                    writer = csv_mod.DictWriter(buffer, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
                    sys.stdout.write(buffer.getvalue())
                return

            output({"data": rows})

        except SystemExit:
            raise
        except Exception as e:
            error("RUN_ERROR", f"Query failed: {e}", exit_code=EXIT_ERROR)

    @results_group.command("head")
    @click.argument("file_path", type=click.Path(exists=True))
    @click.option("--column", multiple=True, help="Column to include. Repeat for multiple columns.")
    @click.option("--filter", "-f", "filter_expr", default=None, help="Filter expression.")
    @click.option("--rows", default=5, type=int, show_default=True, help="Number of rows.")
    def results_head(file_path, column, filter_expr, rows):
        """Return the first rows from a Results file."""
        try:
            results_obj = load_results_object(file_path)
            dataset = _select_dataset(results_obj, column, filter_expr, None)
            output({"data": dataset.to_dicts(remove_prefix=False)[: max(0, rows)]})
        except SystemExit:
            raise
        except Exception as e:
            error("RUN_ERROR", f"Query failed: {e}", exit_code=EXIT_ERROR)

    @results_group.command("export")
    @click.argument("file_path", type=click.Path(exists=True))
    @click.option("--column", multiple=True, help="Column to include. Repeat for multiple columns.")
    @click.option("--filter", "-f", "filter_expr", default=None, help="Filter expression.")
    @click.option("--format", "export_format", type=click.Choice(["csv", "json"]), default="csv", show_default=True)
    @click.option("--output", "-o", "output_path", required=True, help="Output CSV or JSON path.")
    def results_export(file_path, column, filter_expr, export_format, output_path):
        """Export selected Results rows to CSV or JSON."""
        try:
            results_obj = load_results_object(file_path)
            dataset = _select_dataset(results_obj, column, filter_expr, None)
            rows = dataset.to_dicts(remove_prefix=False)
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            if export_format == "csv":
                import csv as csv_mod

                fieldnames = list(rows[0].keys()) if rows else []
                with path.open("w", newline="", encoding="utf-8") as f:
                    writer = csv_mod.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
            else:
                import json

                path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
            output({"path": str(path), "format": export_format, "row_count": len(rows)})
        except SystemExit:
            raise
        except Exception as e:
            error("RUN_ERROR", f"Export failed: {e}", exit_code=EXIT_ERROR)

    @results_group.command("summary")
    @click.argument("file_path", type=click.Path(exists=True))
    def results_summary(file_path):
        """Summarize a Results file."""
        try:
            results_obj = load_results_object(file_path)
            columns = sorted(results_obj.columns)
            output(
                {
                    "result_count": len(results_obj),
                    "column_count": len(columns),
                    "columns": columns,
                    "answer_columns": [c for c in columns if c.startswith("answer.")],
                    "scenario_columns": [c for c in columns if c.startswith("scenario.")],
                    "agent_columns": [c for c in columns if c.startswith("agent.")],
                    "model_columns": [c for c in columns if c.startswith("model.")],
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error("RUN_ERROR", f"Summary failed: {e}", exit_code=EXIT_ERROR)

    @results_group.command("sample")
    @click.argument("file_path", type=click.Path(exists=True))
    @click.option("--column", multiple=True, help="Column to include. Repeat for multiple columns.")
    @click.option("--filter", "-f", "filter_expr", default=None, help="Filter expression.")
    @click.option("--rows", default=5, type=int, show_default=True, help="Number of rows.")
    @click.option("--seed", default=42, type=int, show_default=True, help="Random seed.")
    def results_sample(file_path, column, filter_expr, rows, seed):
        """Return a reproducible random sample from a Results file."""
        try:
            import random

            results_obj = load_results_object(file_path)
            dataset = _select_dataset(results_obj, column, filter_expr, None)
            data = dataset.to_dicts(remove_prefix=False)
            rng = random.Random(seed)
            sample_size = min(max(0, rows), len(data))
            output(
                {
                    "data": rng.sample(data, sample_size) if sample_size else [],
                    "seed": seed,
                    "row_count": len(data),
                    "sample_count": sample_size,
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error("RUN_ERROR", f"Sample failed: {e}", exit_code=EXIT_ERROR)

    @results_group.command("cost")
    @click.argument("file_path", type=click.Path(exists=True))
    def results_cost(file_path):
        """Compute actual job cost from a Results file."""
        try:
            from edsl.cli_shared import jsonable

            results_obj = load_results_object(file_path)
            output({"cost": jsonable(results_obj.compute_job_cost())})
        except SystemExit:
            raise
        except Exception as e:
            error("RUN_ERROR", f"Cost calculation failed: {e}", exit_code=EXIT_ERROR)


def _select_dataset(results_obj, columns, filter_expr, order_by):
    r = results_obj
    if filter_expr:
        r = r.filter(filter_expr)
    if order_by:
        r = r.order_by(order_by)
    if columns:
        return r.select(*columns)
    return r.select()
