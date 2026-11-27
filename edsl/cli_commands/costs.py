"""Cost ledger commands for the EDSL CLI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import click

from edsl.cli_shared import EXIT_ERROR, EXIT_USAGE, error, load_results_object, output


def register(costs_group: click.Group) -> None:
    @costs_group.command("log")
    @click.option("--output", "-o", "output_path", required=True, help="JSONL ledger path.")
    @click.option("--estimated", default=None, type=float, help="Estimated cost in USD.")
    @click.option("--actual", default=None, type=float, help="Actual cost in USD.")
    @click.option("--actual-from", "actual_from", default=None, type=click.Path(exists=True), help="Results file to compute actual cost from.")
    @click.option("--model", default=None, help="Model name for the ledger record.")
    @click.option("--agents", default=None, type=int, help="Agent count for the ledger record.")
    @click.option("--questions", default=None, type=int, help="Question count for the ledger record.")
    @click.option("--scenarios", default=None, type=int, help="Scenario count for the ledger record.")
    @click.option("--note", default=None, help="Free-form note.")
    def costs_log(output_path, estimated, actual, actual_from, model, agents, questions, scenarios, note):
        """Append a cost record to a JSONL ledger."""
        if actual is not None and actual_from is not None:
            error("USAGE_ERROR", "--actual and --actual-from are mutually exclusive.", exit_code=EXIT_USAGE)

        try:
            actual_cost = actual
            cost_details = None
            if actual_from:
                results_obj = load_results_object(actual_from, sync_coop=False)
                from edsl.results.cost_reconciliation import recorded_costs

                cost_details = recorded_costs(results_obj)
                actual_cost = cost_details["actual_cost_usd"]

            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "estimated_cost_usd": estimated,
                "actual_cost_usd": actual_cost,
                "ratio": (actual_cost / estimated) if actual_cost is not None and estimated else None,
                "model": model,
                "agents": agents,
                "questions": questions,
                "scenarios": scenarios,
                "source": actual_from,
                "note": note,
            }
            if cost_details is not None:
                record["raw_actual_cost"] = actual_cost
                record["cost_details"] = cost_details

            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
            warnings = []
            if actual_from and actual_cost is None:
                warnings.append({"code": "INCOMPLETE_COST_METADATA", "message": "The ledger records the known subtotal and leaves actual_cost_usd null."})
            output({"path": str(path), "record": record}, warnings=warnings)
        except SystemExit:
            raise
        except Exception as e:
            error(
                "COST_LEDGER_ERROR",
                str(e),
                suggestion="Check cost values, Results file, and ledger output path.",
                exit_code=EXIT_ERROR,
            )
