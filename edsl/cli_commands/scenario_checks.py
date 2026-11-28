"""Test named conditions against every row of a local ScenarioList."""

import ast
from itertools import chain

import click
from simpleeval import EvalWithCompoundTypes

from edsl.cli_shared import (
    EXIT_ERROR,
    EXIT_USAGE,
    EXIT_VALIDATION,
    error,
    load_any_object,
    output,
)


_EXPRESSION_NODES = (
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Subscript,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Set,
    ast.BoolOp,
    ast.boolop,
    ast.BinOp,
    ast.operator,
    ast.UnaryOp,
    ast.unaryop,
    ast.Compare,
    ast.cmpop,
    ast.IfExp,
)


def _expression(name, expression):
    try:
        tree = ast.parse(expression, mode="eval").body
    except SyntaxError:
        error(
            "USAGE_ERROR",
            f"Invalid expression for rule {name!r}.",
            suggestion="Use a Python-style comparison such as 'low <= high'.",
            exit_code=EXIT_USAGE,
        )
    if any(not isinstance(node, _EXPRESSION_NODES) for node in ast.walk(tree)):
        error(
            "USAGE_ERROR",
            f"Unsupported expression for rule {name!r}.",
            suggestion="Use fields, literals, arithmetic and boolean comparisons.",
            exit_code=EXIT_USAGE,
        )
    return expression, tree


def _compile_rules(requirements, conditional):
    rules = {}
    unconditional = ((name, None, test) for name, test in requirements)
    for name, when, test in chain(unconditional, conditional):
        if not name.strip() or name in rules:
            error(
                "USAGE_ERROR",
                "Give each rule a distinct, nonempty name.",
                exit_code=EXIT_USAGE,
            )
        rules[name] = (
            _expression(name, when) if when is not None else None,
            _expression(name, test),
        )
    return rules


class ExpectedBoolean(ValueError):
    """A rule or its condition returned a non-boolean value."""


def _evaluate(evaluator, expression):
    source, tree = expression
    value = evaluator.eval(source, previously_parsed=tree)
    if not isinstance(value, bool):
        raise ExpectedBoolean
    return value


@click.command("check-rows")
@click.argument("scenario_path", type=click.Path(exists=True))
@click.option(
    "--require",
    "requirements",
    nargs=2,
    multiple=True,
    metavar="NAME EXPRESSION",
    help="Named condition that must be true on every row. Repeat for multiple rules.",
)
@click.option(
    "--require-if",
    "conditional",
    nargs=3,
    multiple=True,
    metavar="NAME WHEN EXPRESSION",
    help="Check the named rule only on rows where WHEN is true. Repeat for multiple rules.",
)
@click.option(
    "--id-field", help="Include this identifier from each reported failing row."
)
@click.option(
    "--limit",
    type=click.IntRange(min=0),
    default=20,
    show_default=True,
    help="Maximum failures to list, or 0 for all. All rows are checked.",
)
def check_rows(scenario_path, requirements, conditional, id_field, limit):
    """Check typed values in a saved ScenarioList without changing the file.

    Use field names directly, or row['field.name'] for arbitrary keys. Failed
    checks exit 5 with a report in error.details[0]. Each row_index is zero-based.

    \b
    Example:
      ep scenarios check-rows plans.ep --require bounds '0 <= low <= high <= capacity'
    """
    from edsl import ScenarioList

    if not requirements and not conditional:
        error("USAGE_ERROR", "Provide --require or --require-if.", exit_code=EXIT_USAGE)
    rules = _compile_rules(requirements, conditional)
    try:
        scenarios = load_any_object(scenario_path, preview=True)
        if not isinstance(scenarios, ScenarioList):
            error(
                "UNSUPPORTED_OBJECT", "Expected a ScenarioList.", exit_code=EXIT_USAGE
            )
        report = {
            "rows": len(scenarios),
            "failed_count": 0,
            "skipped_by_rule": dict.fromkeys(rules, 0),
            "failures_by_rule": dict.fromkeys(rules, 0),
            "failed": [],
        }
        evaluator = EvalWithCompoundTypes(functions={})
        for index, scenario in enumerate(scenarios):
            fields = dict(scenario)
            if id_field and id_field not in fields:
                error(
                    "USAGE_ERROR",
                    f"Row {index} has no identifier field {id_field!r}.",
                    suggestion="Choose a field present on every row or omit --id-field.",
                    exit_code=EXIT_USAGE,
                )
            evaluator.names = {**fields, "row": fields}
            failed = []
            issues = {}
            for name, (when, test) in rules.items():
                try:
                    if when is not None and not _evaluate(evaluator, when):
                        report["skipped_by_rule"][name] += 1
                        continue
                    if _evaluate(evaluator, test):
                        continue
                except Exception as exc:
                    issues[name] = type(exc).__name__
                failed.append(name)
                report["failures_by_rule"][name] += 1
            if failed:
                report["failed_count"] += 1
                if limit == 0 or len(report["failed"]) < limit:
                    item = {"row_index": index, "rules": failed}
                    if id_field:
                        item["id"] = fields[id_field]
                    if issues:
                        item["evaluation_errors"] = issues
                    report["failed"].append(item)
        report["truncated"] = report["failed_count"] > len(report["failed"])
        if report["failed_count"]:
            error(
                "ROW_CHECK_FAILED",
                f"{report['failed_count']} of {len(scenarios)} rows failed.",
                suggestion="Check the reported rows and rules. Use --limit 0 to see every failure.",
                details=[report],
                exit_code=EXIT_VALIDATION,
            )
        output(report)
    except Exception as exc:
        error(
            "SCENARIOS_CHECK_ERROR",
            str(exc),
            suggestion="Check the local ScenarioList path.",
            exit_code=EXIT_ERROR,
        )
