"""Compose independent survey modules in their declared order."""

from copy import deepcopy

from edsl.instructions import ChangeInstruction, Instruction

from .survey import Survey


def _instruction_names(survey):
    return [
        name
        for name, item in survey._instruction_names_to_instructions.items()
        if isinstance(item, Instruction)
    ]


def _item_names(survey):
    return (
        set(survey.question_names)
        | set(survey.question_groups)
        | set(_instruction_names(survey))
    )


def compose_surveys(first: Survey, second: Survey) -> Survey:
    """Append the second module on normal completion. Explicit stops end the study."""
    collisions = _item_names(first) & _item_names(second)
    if collisions:
        raise ValueError(
            f"Names occur in both surveys: {', '.join(sorted(collisions))}. "
            "Use 'ep surveys rename-question' on a copy for question names, or "
            "give the conflicting groups or instructions distinct names."
        )

    left = deepcopy(first.to_dict())
    right = deepcopy(second.to_dict())
    # Each module's name identifies its source, not the new combined instrument.
    left.pop("name", None)
    offset = len(first.questions)
    names = first.question_names + second.question_names
    instruction_names = _instruction_names(first)
    if instruction_names and second.questions:
        left["questions"].append(ChangeInstruction(drop=instruction_names).to_dict())
    left["questions"].extend(right["questions"])
    for field in ("survey_question_names", "survey_question_texts"):
        left["memory_plan"][field].extend(right["memory_plan"][field])
    left["memory_plan"]["data"].update(right["memory_plan"]["data"])
    left["question_groups"].update(
        {
            name: (start + offset, end + offset)
            for name, (start, end) in right["question_groups"].items()
        }
    )

    rules = left["rule_collection"]
    for rule in rules["rules"]:
        if isinstance(rule["next_q"], int) and rule["next_q"] > offset:
            raise ValueError(
                "A rule in the first module jumps past its final question. "
                "Use an explicit stop rule or a destination within that module."
            )
    for rule in right["rule_collection"]["rules"]:
        rule["current_q"] += offset
        if isinstance(rule["next_q"], int):
            rule["next_q"] += offset
        rule["question_name_to_index"] = {
            name: index + offset
            for name, index in rule["question_name_to_index"].items()
        }
        rules["rules"].append(rule)
    rules.update(
        num_questions=len(names),
        question_name_to_index={name: i for i, name in enumerate(names)},
    )

    for phase, steps in right.get("state_steps", {}).items():
        left.setdefault("state_steps", {}).setdefault(phase, {}).update(steps)
    left.setdefault("questions_to_randomize", []).extend(
        right.get("questions_to_randomize", [])
    )
    left.setdefault("options_to_pin", {}).update(right.get("options_to_pin", {}))
    for field in (
        "scale_direction_randomization",
        "question_sampling",
        "question_order",
    ):
        if field in right:
            if field in left:
                raise ValueError(
                    f"Both modules define {field}. Choose a single policy for the "
                    "combined survey before composing them."
                )
            left[field] = right[field]

    combined = Survey.from_dict(left)
    if instruction_names:
        # An explicit 'keep' in an earlier module can override a subsequent 'drop'.
        actual = combined._relevant_instructions_dict
        for module in (first, second):
            expected = module._relevant_instructions_dict
            for name in module.question_names:
                if [i.name for i in actual[name]] != [i.name for i in expected[name]]:
                    raise ValueError(
                        f"Instruction scope would change at {name!r}. Review explicit "
                        "keep/drop instructions at the module boundary."
                    )
    return combined
