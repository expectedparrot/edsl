"""Student-proposing deferred acceptance using bounded, atomic iteration.

The proposal queue, tentative matches, and next-choice cursors are local values
inside one close effect. No intermediate matching is committed or observable.
"""

from edsl.sharedstate import (
    Command,
    Machine,
    T,
    append,
    choose,
    constant,
    field,
    filter_items,
    fold,
    input_,
    iterate,
    let,
    local,
    map_items,
    map_sequence,
    record,
    reduce_,
    set_,
    state_field,
    take,
)


def build_machine(capacities=None, priorities=None):
    capacities = {"North": 1, "South": 1} if capacities is None else dict(capacities)
    priorities = (
        {"North": ["B", "A", "C"], "South": ["A", "B", "C"]}
        if priorities is None
        else dict(priorities)
    )
    if set(capacities) != set(priorities) or any(
        isinstance(n, bool) or not isinstance(n, int) or n < 0
        for n in capacities.values()
    ):
        raise ValueError(
            "capacities and priorities must cover the same institutions with nonnegative capacities"
        )
    if any(
        not isinstance(order, (list, tuple))
        or any(not isinstance(name, str) for name in order)
        or len(set(order)) != len(order)
        for order in priorities.values()
    ):
        raise ValueError(
            "institution priorities must be lists of distinct student names"
        )
    latest = reduce_("latest_by", field("requests"), field="student")
    queue = map_sequence(
        reduce_("sort_records", latest.values(), fields=["student"]),
        item="request",
        value_expr=local("request").get("student"),
    )
    initial = record(
        queue=queue,
        held=map_items(
            constant("capacities"),
            key="school",
            value="capacity",
            key_expr=local("school"),
            value_expr=[],
        ),
        next=map_items(
            latest,
            key="student",
            value="request",
            key_expr=local("student"),
            value_expr=0,
        ),
    )
    # Lexical bindings keep each intermediate computation in the JSON expression.
    state, student, school = local("matching"), local("student"), local("school")
    ranking = latest.get(student).get("ranking")
    cursor = state.get("next").get(student)
    priority = constant("priorities").get(school)
    ranks = fold(
        priority,
        record(index=0, ranks={}),
        item="name",
        accumulator="rank_state",
        body=record(
            index=local("rank_state").get("index") + 1,
            ranks=local("rank_state")
            .get("ranks")
            .with_item(local("name"), local("rank_state").get("index")),
        ),
    ).get("ranks")
    candidates = map_sequence(
        state.get("held").get(school).appended(student),
        item="candidate",
        value_expr=record(
            student=local("candidate"),
            priority=local("ranks").get(local("candidate"), priority.length()),
        ),
    )
    ordered = map_sequence(
        reduce_("sort_records", candidates, fields=["priority", "student"]),
        item="candidate",
        value_expr=local("candidate").get("student"),
    )
    kept = take(local("ordered"), constant("capacities").get(school))
    rejected = filter_items(
        local("ordered"),
        item="candidate",
        predicate=~local("kept").contains(local("candidate")),
    )
    updated = record(
        queue=state.get("queue").drop_first() + rejected,
        held=state.get("held").with_item(school, local("kept")),
        next=state.get("next").with_item(student, cursor + 1),
    )
    proposal = let(
        "school",
        ranking.at(cursor),
        let("ranks", ranks, let("ordered", ordered, let("kept", kept, updated))),
    )
    step = let(
        "student",
        state.get("queue").first(),
        choose(
            cursor >= ranking.length(),
            state.with_item("queue", state.get("queue").drop_first()),
            proposal,
        ),
    )
    # Each proposal consumes one ranking entry. At most one final exhausted-queue
    # visit per applicant is needed, hence sum(lengths) + number of applicants.
    bound = (
        reduce_(
            "sum",
            map_sequence(
                latest.values(),
                item="request",
                value_expr=local("request").get("ranking").length(),
            ),
        )
        + latest.length()
    )
    matching = iterate(
        initial,
        state="matching",
        until=state.get("queue").length() == 0,
        step=step,
        max_steps=bound,
    )
    school_rows = map_items(
        field("allocation").get("held"),
        key="school",
        value="students",
        key_expr=local("school"),
        value_expr=record(school=local("school"), students=local("students")),
    )
    matches = fold(
        school_rows.values(),
        {},
        item="school_row",
        accumulator="matches",
        body=fold(
            local("school_row").get("students"),
            local("matches"),
            item="student",
            accumulator="matches",
            body=local("matches").with_item(
                local("student"), local("school_row").get("school")
            ),
        ),
    )
    return Machine(
        name="PrimitiveDeferredAcceptance",
        constants={"capacities": capacities, "priorities": priorities},
        fields={
            "requests": state_field(
                T.sequence(
                    T.record(
                        {
                            "student": T.text(),
                            "ranking": T.sequence(T.choice(list(capacities))),
                        }
                    )
                ),
                [],
            ),
            "allocation": state_field(
                T.record(
                    {
                        "held": T.map(T.text(), T.sequence(T.text())),
                        "queue": T.sequence(T.text()),
                        "next": T.map(T.text(), T.integer(minimum=0)),
                    }
                ),
                {"held": {}, "queue": [], "next": {}},
            ),
        },
        commands={
            "collect": Command(
                inputs={
                    "student": T.text(),
                    "ranking": T.sequence(T.choice(list(capacities))),
                },
                require=reduce_("count_by", input_("ranking")).length()
                == input_("ranking").length(),
                effects=(
                    append(
                        "requests",
                        record(student=input_("student"), ranking=input_("ranking")),
                    ),
                ),
            )
        },
        close_effects=(set_("allocation", matching),),
        view={
            "matches": matches,
            "institution_matches": field("allocation").get("held"),
        },
    )


DEMO = [
    ("collect", {"student": "A", "ranking": ["North", "South"]}),
    ("collect", {"student": "B", "ranking": ["North", "South"]}),
    ("collect", {"student": "C", "ranking": ["South"]}),
    ("$close", {}),
]
