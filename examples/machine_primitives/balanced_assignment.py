"""Greedy marginal balance with seeded ties and immutable personal assignments."""

from edsl.sharedstate import (
    Command,
    Machine,
    T,
    assert_,
    constant,
    current_value,
    field,
    filter_items,
    input_,
    local,
    map_sequence,
    put,
    record,
    reduce_,
    seeded_order,
    set_,
    state_field,
    when,
)

ARMS = ("Control", "Treatment")
AGES = ("Younger", "Older")
EXPERIENCE = ("New", "Experienced")


def build_machine(seed="balanced-2026"):
    if not isinstance(seed, str) or not seed:
        raise ValueError("seed must be nonempty text")
    rid, age, experience = input_("respondent_id"), input_("age"), input_("experience")
    assignments = field("assignments")
    rows = assignments.values()
    old = assignments.get(rid, {})
    seen = assignments.contains(rid)
    arm = local("arm")
    # Minimizing this sum also minimizes the increase in the sum of squared
    # marginal counts (total, matching age, matching experience), with equal weights.
    in_arm = filter_items(rows, item="r", predicate=local("r").get("arm") == arm)
    score = (
        in_arm.length()
        + filter_items(
            in_arm, item="r", predicate=local("r").get("age") == age
        ).length()
        + filter_items(
            in_arm, item="r", predicate=local("r").get("experience") == experience
        ).length()
    )
    ranked = reduce_(
        "sort_records",
        map_sequence(
            constant("arms"), item="arm", value_expr=record(arm=arm, score=score)
        ),
        fields=["score", "arm"],
    )
    tied = map_sequence(
        filter_items(
            ranked,
            item="r",
            predicate=local("r").get("score") == ranked.first().get("score"),
        ),
        item="r",
        value_expr=local("r").get("arm"),
    )
    selected = seeded_order(
        tied, seed=constant("seed"), scope=current_value("study_id", "study"), key=rid
    ).first()
    return Machine(
        name="BalancedAssignment",
        constants={"arms": list(ARMS), "seed": seed},
        fields={
            "assignments": state_field(
                T.map(
                    T.text(),
                    T.record(
                        {
                            "arm": T.choice(ARMS),
                            "age": T.choice(AGES),
                            "experience": T.choice(EXPERIENCE),
                        }
                    ),
                ),
                {},
            ),
            "closed": state_field(T.boolean(), False),
        },
        commands={
            "assign": Command(
                inputs={
                    "respondent_id": T.text(),
                    "age": T.choice(AGES),
                    "experience": T.choice(EXPERIENCE),
                },
                effects=(
                    assert_(rid.stripped().length() > 0, code="missing_respondent_id"),
                    assert_(
                        ~seen
                        | (
                            (old.get("age") == age)
                            & (old.get("experience") == experience)
                        ),
                        code="characteristics_changed",
                    ),
                    when(~seen, assert_(~field("closed"), code="assignment_closed")),
                    put(
                        "assignments",
                        rid,
                        record(arm=selected, age=age, experience=experience),
                        once=True,
                    ),
                ),
            )
        },
        close_effects=(set_("closed", True),),
        view={
            "age": assignments.get(current_value("respondent_id", ""), {}).get("age"),
            "experience": assignments.get(current_value("respondent_id", ""), {}).get(
                "experience"
            ),
            "arm": assignments.get(current_value("respondent_id", ""), {}).get("arm"),
            "counts": reduce_(
                "count_by",
                map_sequence(rows, item="r", value_expr=local("r").get("arm")),
            ),
            "accepting": ~field("closed"),
        },
    )


DEMO = [
    (
        "assign",
        {
            "respondent_id": f"R{i}",
            "age": AGES[i % 2],
            "experience": EXPERIENCE[(i // 2) % 2],
        },
    )
    for i in range(12)
]
