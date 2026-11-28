"""Results commands for the EDSL CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from edsl.cli_shared import EXIT_ERROR, EXIT_USAGE, EXIT_VALIDATION, error, load_any_object, load_results_object, output


def _bounded(value, text_chars: int):
    """Return a compact JSON-safe scalar suitable for agent context."""
    from edsl.cli_shared import jsonable

    value = jsonable(value)
    if isinstance(value, str) and len(value) > text_chars:
        return value[: text_chars - 1] + "…"
    if isinstance(value, (dict, list)):
        rendered = str(value)
        return rendered[: text_chars - 1] + "…" if len(rendered) > text_chars else value
    return value


def _review(
    results_obj, *, max_rows: int, max_columns: int, max_values: int,
    text_chars: int, requested_columns=(), group_by=(),
):
    columns = sorted(results_obj.columns)
    preferred = list(requested_columns) or [
        column for prefix in ("answer.", "agent.", "scenario.", "model.")
        for column in columns if column.startswith(prefix)
    ]
    selected = preferred[:max_columns]
    rows = results_obj.select(*selected).to_dicts(remove_prefix=False) if selected else []
    missingness = []
    for column in selected:
        missing = sum(row.get(column) is None for row in rows)
        if missing:
            missingness.append({"column": column, "missing": missing, "rate": round(missing / max(1, len(rows)), 4)})

    distributions = []
    numeric_summaries = []
    text_samples = []
    for column in (column for column in selected if column.startswith("answer.")):
        counts = {}
        numeric = []
        text_values = []
        for row in rows:
            value = row.get(column)
            if value is None:
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric.append(float(value))
            elif isinstance(value, str):
                text_values.append(_bounded(value, text_chars))
            key = str(_bounded(value, text_chars))
            counts[key] = counts.get(key, 0) + 1
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        distributions.append(
            {
                "column": column,
                "unique": len(counts),
                "top_values": [
                    {"value": value, "count": count} for value, count in ranked[:max_values]
                ],
                "values_truncated": max(0, len(ranked) - max_values),
            }
        )
        if numeric:
            numeric_summaries.append({
                "column": column,
                "count": len(numeric),
                "mean": round(sum(numeric) / len(numeric), 4),
                "min": min(numeric),
                "max": max(numeric),
            })
        if text_values:
            text_samples.append({
                "column": column,
                "samples": text_values[:max_values],
                "samples_truncated": max(0, len(text_values) - max_values),
            })

    segment_summaries = []
    numeric_columns = [item["column"] for item in numeric_summaries]
    for group_column in group_by[:2]:
        if group_column not in columns:
            continue
        groups = {}
        for row in results_obj.select(group_column, *numeric_columns).to_dicts(remove_prefix=False):
            group = str(_bounded(row.get(group_column), text_chars))
            bucket = groups.setdefault(group, {column: [] for column in numeric_columns})
            for column in numeric_columns:
                value = row.get(column)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    bucket[column].append(float(value))
        segment_summaries.append({
            "group_by": group_column,
            "groups": [
                {
                    "value": group,
                    "count": max((len(values) for values in bucket.values()), default=0),
                    "means": {
                        column: round(sum(values) / len(values), 4)
                        for column, values in bucket.items() if values
                    },
                }
                for group, bucket in sorted(groups.items())[:max_values]
            ],
            "groups_truncated": max(0, len(groups) - max_values),
        })

    sample = [
        {column: _bounded(row.get(column), text_chars) for column in selected}
        for row in rows[:max_rows]
    ]
    try:
        from edsl.results.cost_reconciliation import recorded_costs

        cost = recorded_costs(results_obj)["actual_cost_usd"]
    except Exception:
        cost = None
    return {
        "result_count": len(results_obj),
        "selected_columns": selected,
        "columns_truncated": max(0, len(preferred) - len(selected)),
        "missingness": missingness,
        "answer_distributions": distributions,
        "numeric_summaries": numeric_summaries,
        "text_samples": text_samples,
        "segment_summaries": segment_summaries,
        "representative_rows": sample,
        "cost": cost,
        "bounds": {
            "max_rows": max_rows, "max_columns": max_columns,
            "max_values": max_values, "text_chars": text_chars,
        },
    }


def _survey_differences(expected, recorded):
    # Compare their JSON representation: e.g. serialized page bounds can be lists
    # or tuples depending on which file format carried the identical instrument.
    expected_data, recorded_data = (
        json.loads(json.dumps(survey.to_dict(add_edsl_version=False)))
        for survey in (expected, recorded)
    )

    # Job and Results archives may restore Pydantic model properties in different
    # orders. JSON Schema treats the list of required property names as a set.
    for data in (expected_data, recorded_data):
        for question in data["questions"]:
            schema = question.get("pydantic_model_schema")
            if isinstance(schema, dict) and isinstance(schema.get("required"), list):
                schema["required"].sort()

    def changed_fields(a, b):
        return sorted(
            key for key in a.keys() | b.keys()
            if key not in a or key not in b
            or json.dumps(a[key], sort_keys=True) != json.dumps(b[key], sort_keys=True)
        )

    sections = changed_fields(expected_data, recorded_data)
    if not sections:
        return {}
    wanted, found = (
        {q["question_name"]: q for q in data["questions"] if "question_name" in q}
        for data in (expected_data, recorded_data)
    )
    changed = []
    for name in sorted(wanted.keys() & found.keys()):
        fields = changed_fields(wanted[name], found[name])
        if fields:
            changed.append({
                "question": name,
                "differences": {
                    field: {
                        side: _bounded(question[field], 600)
                        for side, question in (("expected", wanted[name]), ("recorded", found[name]))
                        if field in question
                    }
                    for field in fields
                },
            })
    return {
        "different_survey_fields": sections,
        "missing_questions": sorted(wanted.keys() - found.keys()),
        "extra_questions": sorted(found.keys() - wanted.keys()),
        "changed_questions": changed,
    }


def register(results_group: click.Group) -> None:
    @results_group.command("check-survey")
    @click.argument("results_path", type=click.Path(exists=True))
    @click.option("--against", required=True, type=click.Path(exists=True), help="Expected local Jobs or Survey file.")
    def check_survey(results_path, against):
        """Check the survey saved in Results against the intended instrument.

        Compares the full stored definition, including questions, instructions, rules,
        and memory. Check respondent coverage and completed answers separately.
        """
        from edsl import Jobs, Results, Survey

        try:
            results = load_any_object(results_path, preview=True)
            reference = load_any_object(against, preview=True)
            expected = reference.survey if isinstance(reference, Jobs) else reference
            if not isinstance(results, Results) or not isinstance(expected, Survey):
                error("UNSUPPORTED_OBJECT", "Supply Results and an expected Jobs or Survey file.", exit_code=EXIT_USAGE)
            actual = results.survey
            if actual is None:
                error("MISSING_SURVEY", "The Results have no stored survey definition.",
                      suggestion="Inspect saved question_text columns or prompts for individual records.", exit_code=EXIT_VALIDATION)
            files = {"results_path": results_path, "expected_path": against}
            differences = _survey_differences(expected, actual)
            if differences:
                error(
                    "SURVEY_MISMATCH",
                    f"The survey in {results_path} differs from the instrument in {against}.",
                    suggestion="Review the differences before reusing these responses.",
                    details=[{**files, "survey_matches": False, **differences}],
                    exit_code=EXIT_VALIDATION,
                )
            output({**files, "survey_matches": True, "question_count": len(actual.questions)})
        except Exception as exc:
            error("VALIDATION_ERROR", str(exc), exit_code=EXIT_VALIDATION)

    @results_group.command("columns")
    @click.option("--file", "file_path", required=True, help="Path to serialized Results .ep, JSON, or JSON.gz.")
    def results_columns(file_path):
        """List available columns in a Results file.

        \b
        Examples:
          ep results columns --file results.ep
          ep results columns --file results.json
        """
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
        """Extract columns from a Results file with optional filtering.

        \b
        Examples:
          ep results select --file results.ep --column answer.q0
          ep results select --file results.ep --column answer.q0 --column agent.age --limit 10
          ep results select --file results.ep --filter "agent.age > 30" --order_by answer.q0
          ep results select --file results.ep --column answer.q0 --csv
        """
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
        """Return the first rows from a Results file.

        \b
        Examples:
          ep results head results.ep
          ep results head results.ep --rows 10
          ep results head results.ep --column answer.q0 --column model.model
          ep results head results.ep --filter "scenario.topic == 'AI'"
        """
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
        """Export selected Results rows to CSV or JSON.

        \b
        Examples:
          ep results export results.ep --output results.csv
          ep results export results.ep --column answer.q0 --column agent.age --output answers.csv
          ep results export results.ep --filter "agent.age > 30" --format json --output filtered.json
        """
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
        """Summarize a Results file.

        \b
        Examples:
          ep results summary results.ep
          ep results summary results.json
        """
        try:
            results_obj = load_results_object(file_path)
            columns = sorted(results_obj.columns)
            output(
                {
                    "result_count": len(results_obj),
                    "completion": results_obj.completion_summary(),
                    "column_count": len(columns),
                    "columns": columns,
                    "answer_columns": [c for c in columns if c.startswith("answer.")],
                    "scenario_columns": [
                        c for c in columns if c.startswith("scenario.")
                    ],
                    "agent_columns": [c for c in columns if c.startswith("agent.")],
                    "model_columns": [c for c in columns if c.startswith("model.")],
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error("RUN_ERROR", f"Summary failed: {e}", exit_code=EXIT_ERROR)

    @results_group.command("review")
    @click.argument("file_path", type=click.Path(exists=True))
    @click.option(
        "--column", "requested_columns", multiple=True,
        help="Column to review. Repeat for multiple columns.",
    )
    @click.option("--rows", "max_rows", default=3, type=click.IntRange(1, 10), show_default=True)
    @click.option(
        "--columns", "max_columns", default=24, type=click.IntRange(1, 50),
        show_default=True, help="Maximum number of columns returned.",
    )
    @click.option("--values", "max_values", default=8, type=click.IntRange(1, 20), show_default=True)
    @click.option("--text-chars", default=240, type=click.IntRange(40, 500), show_default=True)
    @click.option(
        "--group-by", multiple=True,
        help="Return numeric answer means by this column. Repeat at most twice.",
    )
    def results_review(
        file_path, requested_columns, max_rows, max_columns, max_values, text_chars,
        group_by,
    ):
        """Return bounded, agent-oriented diagnostics for a Results file.

        \b
        Includes compact schema, missingness, answer distributions, representative
        rows, and actual cost. Output limits are enforced to protect agent context.

        \b
        Examples:
          ep results review results.ep
          ep results review results.ep --column answer.q0 --column agent.age
        """
        try:
            results_obj = load_results_object(file_path)
            output(_review(
                results_obj, max_rows=max_rows, max_columns=max_columns,
                max_values=max_values, text_chars=text_chars,
                requested_columns=requested_columns,
                group_by=group_by,
            ))
        except SystemExit:
            raise
        except Exception as e:
            error("RUN_ERROR", f"Review failed: {e}", exit_code=EXIT_ERROR)

    @results_group.command("sample")
    @click.argument("file_path", type=click.Path(exists=True))
    @click.option("--column", multiple=True, help="Column to include. Repeat for multiple columns.")
    @click.option("--filter", "-f", "filter_expr", default=None, help="Filter expression.")
    @click.option("--rows", default=5, type=int, show_default=True, help="Number of rows.")
    @click.option("--seed", default=42, type=int, show_default=True, help="Random seed.")
    def results_sample(file_path, column, filter_expr, rows, seed):
        """Return a reproducible random sample from a Results file.

        \b
        Examples:
          ep results sample results.ep
          ep results sample results.ep --rows 20 --seed 123
          ep results sample results.ep --column answer.q0 --column agent.age
          ep results sample results.ep --filter "model.model == 'gpt-4o'"
        """
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

    @results_group.command("values")
    @click.argument("file_path", type=click.Path(exists=True))
    @click.option("--column", required=True, help="Column to extract, e.g. answer.q0.")
    @click.option("--filter", "-f", "filter_expr", default=None, help="Filter expression.")
    @click.option("--limit", default=None, type=int, help="Max values.")
    def results_values(file_path, column, filter_expr, limit):
        """Return values from one Results column.

        \b
        Examples:
          ep results values results.ep --column answer.q0
          ep results values results.ep --column agent.age --limit 25
          ep results values results.ep --column answer.q0 --filter "scenario.topic == 'AI'"
        """
        try:
            results_obj = load_results_object(file_path)
            dataset = _select_dataset(results_obj, (column,), filter_expr, None)
            rows = dataset.to_dicts(remove_prefix=False)
            if limit and limit > 0:
                rows = rows[:limit]
            values = [row.get(column) for row in rows]
            output({"column": column, "values": values, "count": len(values)})
        except SystemExit:
            raise
        except Exception as e:
            error("RUN_ERROR", f"Value extraction failed: {e}", exit_code=EXIT_ERROR)

    @results_group.command("first")
    @click.argument("file_path", type=click.Path(exists=True))
    @click.option("--column", required=True, help="Column to extract, e.g. answer.q0.")
    @click.option("--filter", "-f", "filter_expr", default=None, help="Filter expression.")
    def results_first(file_path, column, filter_expr):
        """Return the first value from one Results column.

        \b
        Examples:
          ep results first results.ep --column answer.q0
          ep results first results.ep --column answer.q0 --filter "agent.age > 30"
        """
        try:
            results_obj = load_results_object(file_path)
            dataset = _select_dataset(results_obj, (column,), filter_expr, None)
            rows = dataset.to_dicts(remove_prefix=False)
            row = rows[0] if rows else None
            output(
                {
                    "column": column,
                    "value": row.get(column) if row else None,
                    "row": row,
                    "found": row is not None,
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error("RUN_ERROR", f"First-value extraction failed: {e}", exit_code=EXIT_ERROR)

    @results_group.command("cost")
    @click.argument("file_path", type=click.Path(exists=True))
    def results_cost(file_path):
        """Compute actual job cost from a Results file.

        \b
        Examples:
          ep results cost results.ep
          ep costs log --output costs.jsonl --actual-from results.ep
        """
        try:
            from edsl.results.cost_reconciliation import recorded_costs

            results_obj = load_results_object(file_path, sync_coop=False)
            report = recorded_costs(results_obj)
            warnings = []
            if report["actual_cost_usd"] is None:
                message = "The saved responses establish only a subtotal. Consult the original run accounting for a total."
                if report["unknown_cache_status_calls"]:
                    message = (
                        f"{report['unknown_cache_status_calls']} responses lack a cache-hit flag. "
                        f"Their recorded prices total ${report['known_value_unknown_cache_status_usd']:.6f} "
                        f"with {report['unpriced_unknown_cache_status_calls']} unpriced. "
                        "Those amounts cannot be assigned to cache hits or new charges from this file. "
                        "Leave the actual total unknown."
                    )
                warnings.append({"code": "INCOMPLETE_COST_METADATA", "message": message})
            output({"cost": report["actual_cost_usd"], **report}, warnings=warnings)
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
