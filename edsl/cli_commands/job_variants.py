"""Summarize the assignment schedule of a saved job before fieldwork."""

from collections import Counter
import json

import click

from edsl.cli_shared import EXIT_VALIDATION, error, output
from .job_prompt_preview import assigned_interviews


def field_value(interview, field):
    source, _, name = field.partition(".")
    if source == "scenario" and name in interview.scenario:
        value = interview.scenario[name]
    elif source == "agent" and name == "name":
        value = interview.agent.name
    elif source == "agent" and name in interview.agent.traits:
        value = interview.agent.traits[name]
    else:
        raise ValueError(
            f"Missing assignment field {field!r}. Use scenario.FIELD, agent.TRAIT or agent.name."
        )
    if value is None:
        raise ValueError(f"Assignment field {field!r} is null.")
    return value


@click.command("variants")
@click.argument("jobs_path", type=click.Path(exists=True))
@click.option(
    "--group-by",
    multiple=True,
    metavar="FIELD",
    help="Group by scenario.FIELD, agent.TRAIT or agent.name. Repeat for joint groups.",
)
@click.option(
    "--unique-by",
    multiple=True,
    metavar="FIELD",
    help="Require one interview per distinct key. Repeat for a composite key.",
)
@click.option(
    "--expect-interviews",
    type=click.IntRange(min=0),
    help="Require this total across the saved schedule.",
)
def variants(jobs_path, group_by, unique_by, expect_interviews):
    """Count assigned interviews and locate the first interview in each group.

    Use the returned interview indices with preview-prompt and test-case.
    Group by the fields that define the versions you wish to rehearse.
    """
    try:
        _, interviews, _ = assigned_interviews(jobs_path)
        groups = {}
        seen = Counter()
        count = 0
        available_fields = None
        for index, interview in enumerate(interviews):
            count += 1
            if not group_by:
                names = {
                    f"scenario.{k}"
                    for k, v in interview.scenario.items()
                    if v is not None
                }
                names.update(
                    f"agent.{k}"
                    for k, v in interview.agent.traits.items()
                    if v is not None and k != "name"
                )
                if interview.agent.name is not None:
                    names.add("agent.name")
                available_fields = (
                    names if available_fields is None else available_fields & names
                )
            fields = {
                key: field_value(interview, key) for key in (*group_by, *unique_by)
            }
            labels = {key: fields[key] for key in group_by}
            group_key = json.dumps(labels, sort_keys=True, allow_nan=False)
            group = groups.setdefault(
                group_key, {"values": labels, "interviews": 0, "interview_index": index}
            )
            group["interviews"] += 1
            if unique_by:
                key = json.dumps(
                    {name: fields[name] for name in unique_by},
                    sort_keys=True,
                    allow_nan=False,
                )
                seen[key] += 1
        data = {"planned_interviews": count, "groups": list(groups.values())}
        if not group_by:
            data["available_fields"] = sorted(available_fields or ())
        if unique_by:
            duplicates = {key: n for key, n in seen.items() if n > 1}
            data.update(
                unique_keys=len(seen),
                duplicate_keys=len(duplicates),
                duplicate_examples=[
                    {"values": json.loads(key), "interviews": duplicates[key]}
                    for key in list(duplicates)[:5]
                ],
            )
        wrong_count = expect_interviews is not None and count != expect_interviews
        if wrong_count or data.get("duplicate_keys"):
            error(
                "ASSIGNMENT_MISMATCH",
                "The saved interview schedule failed the requested checks.",
                suggestion="Check how agents and scenarios were combined. For aligned rows use ep jobs build --pair-agents-scenarios.",
                details=[{**data, "expected_interviews": expect_interviews}],
                exit_code=EXIT_VALIDATION,
            )
        output(data)
    except Exception as exc:
        error(
            "VALIDATION_ERROR",
            str(exc),
            suggestion="Check the saved job and the names of the assignment fields.",
            exit_code=EXIT_VALIDATION,
        )
