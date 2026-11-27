"""Audit the assigned interviews represented in a local Results object."""

from collections import Counter, defaultdict
import json

import click

from edsl.cli_shared import EXIT_USAGE, EXIT_VALIDATION, error, load_any_object, output


_COMPONENTS = ("agent", "scenario", "model")


def _signature(value):
    # Keep JSON types distinct (in Python True == 1) and ignore mapping order.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sample(value):
    if isinstance(value, (dict, list)):
        return {"type": type(value).__name__, "length": len(value)}
    return value[:120] + "…" if isinstance(value, str) and len(value) > 120 else value


def _expected(job, iterations):
    plan = job.assignment_plan
    policy = job.treatment_assignment
    if iterations is None:
        iterations = (
            policy.planned_iterations if policy else job.run_config.parameters.n
        )
    counts = Counter()
    if policy:
        policy.validate_for_job(job, iterations=iterations)
        # A treatment schedule chooses exactly one scenario per agent/model/wave.
        for a, agent in enumerate(job.agents):
            for m in range(len(job.models)):
                for wave in range(iterations):
                    treatment = policy.realize(a, agent, m, wave)
                    counts[a, treatment.scenario_index, m, wave] += 1
    else:
        for assignment in plan.iter_indices():
            for wave in range(iterations):
                counts[(*assignment, wave)] += 1
    return counts, iterations


def _audit(results, job, iterations, allow_test_model, limit):
    expected, iterations = _expected(job, iterations)
    definitions = {
        name: [obj.to_dict(add_edsl_version=False) for obj in getattr(job, name + "s")]
        for name in _COMPONENTS
    }
    by_content = {}
    for name, records in definitions.items():
        lookup = defaultdict(list)
        for i, record in enumerate(records):
            lookup[_signature(record)].append(i)
        by_content[name] = lookup

    def describe(key):
        a, s, m, wave = key
        scenario = definitions["scenario"][s]
        return {
            "indices": dict(zip(_COMPONENTS, (a, s, m))),
            "iteration": wave,
            "agent_name": definitions["agent"][a].get("name"),
            "scenario_sample": {k: _sample(scenario[k]) for k in sorted(scenario)[:4]},
            "model_name": definitions["model"][m].get("model"),
        }

    seen = Counter()
    problems = Counter()
    examples = defaultdict(list)

    def record(kind, detail, count=1):
        problems[kind] += count
        if len(examples[kind]) < limit:
            examples[kind].append(detail)

    for row_index, row in enumerate(results):
        wave = row.get("iteration")
        indices = {} if row.indices is None else row.indices
        if type(wave) is not int or wave < 0 or not isinstance(indices, dict):
            record(
                "unresolved_rows",
                {"row": row_index, "reason": "Invalid iteration or component indices."},
            )
            continue

        positions = []
        changes = {}
        for name in _COMPONENTS:
            actual = getattr(row, name).to_dict(add_edsl_version=False)
            signature = _signature(actual)
            substituted = (
                name == "model"
                and allow_test_model
                and actual.get("inference_service") == "test"
            )
            idx = indices.get(name)
            if idx is None:
                candidates = (
                    range(len(definitions[name]))
                    if substituted
                    else by_content[name].get(signature, [])
                )
                if len(candidates) != 1:
                    record(
                        "unresolved_rows",
                        {
                            "row": row_index,
                            "component": name,
                            "reason": "Missing index and no unique matching job component.",
                            "candidate_count": len(candidates),
                        },
                    )
                    break
                idx = candidates[0]
            if type(idx) is not int or not 0 <= idx < len(definitions[name]):
                record(
                    "unresolved_rows",
                    {
                        "row": row_index,
                        "component": name,
                        "reason": "Recorded index is outside the saved job.",
                        "index": idx,
                    },
                )
                break
            positions.append(idx)
            if substituted or idx in by_content[name].get(signature, ()):
                continue
            wanted = definitions[name][idx]
            fields = {}
            for field in sorted(wanted.keys() | actual.keys()):
                if (
                    field not in wanted
                    or field not in actual
                    or _signature(wanted[field]) != _signature(actual[field])
                ):
                    fields[field] = {
                        side: _sample(values[field])
                        for side, values in (("expected", wanted), ("recorded", actual))
                        if field in values
                    }
            changes[name] = fields
        else:
            key = (*positions, wave)
            seen[key] += 1
            if changes:
                record(
                    "changed_rows",
                    {"row": row_index, **describe(key), "fields": changes},
                )

    for key, count in (expected - seen).items():
        record(
            "missing",
            {
                **describe(key),
                "expected_count": expected[key],
                "recorded_count": seen[key],
            },
            count,
        )
    for key, count in (seen - expected).items():
        kind = "duplicate" if key in expected else "unexpected"
        record(
            kind,
            {
                **describe(key),
                "expected_count": expected[key],
                "recorded_count": seen[key],
            },
            count,
        )

    return {
        "matches": not problems,
        "iterations": iterations,
        "planned_rows": sum(expected.values()),
        "allow_test_model": allow_test_model,
        "recorded_rows": len(results),
        "counts": dict(problems),
        "examples": dict(examples),
        "example_limit_per_category": limit,
    }


@click.command("check-assignments")
@click.argument("results_path", type=click.Path(exists=True))
@click.option(
    "--against",
    required=True,
    type=click.Path(exists=True),
    help="Saved Jobs defining the intended assignments.",
)
@click.option(
    "--iterations",
    "-n",
    type=click.IntRange(min=1),
    help="Iterations in the intended run. Defaults to the saved schedule or one.",
)
@click.option(
    "--allow-test-model",
    is_flag=True,
    help="Allow the local test model in place of the assigned model for a scripted rehearsal.",
)
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=10,
    show_default=True,
    help="Maximum examples per problem category. Counts include all rows.",
)
def check_assignments(results_path, against, iterations, allow_test_model, limit):
    """Compare every saved respondent, scenario, model and iteration with the job plan.

    Row order is immaterial. Stored indices identify the job slots and the record
    must match the assigned component's content. Older rows without indices can
    be identified if their content matches a unique slot. Exit 5 for discrepancies
    or insufficient evidence. This checks coverage, independently of answer quality.
    """
    from edsl import Jobs, Results

    try:
        results = load_any_object(results_path, preview=True)
        job = load_any_object(against, preview=True)
        if not isinstance(results, Results) or not isinstance(job, Jobs):
            error(
                "USAGE_ERROR",
                "Supply a Results file and --against a Jobs file.",
                exit_code=EXIT_USAGE,
            )
        report = _audit(results, job, iterations, allow_test_model, limit)
    except Exception as exc:
        error(
            "VALIDATION_ERROR",
            str(exc),
            suggestion="Check the input packages and intended iteration count.",
            exit_code=EXIT_VALIDATION,
        )
    if not report["matches"]:
        error(
            "ASSIGNMENT_MISMATCH",
            "Saved results did not verify every planned assignment.",
            suggestion="Inspect counts and examples for missing, repeated, changed or unresolved rows.",
            details=[report],
            exit_code=EXIT_VALIDATION,
        )
    output(report)
