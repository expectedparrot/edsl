"""Results commands for the EDSL CLI."""

from __future__ import annotations

import sys

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
