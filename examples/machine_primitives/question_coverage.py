"""Fixed per-agent assignments, counting validated answers toward question coverage.

Run whole interviews sequentially. Assignments are not capacity reservations.
"""

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
    set_,
    state_field,
    take,
    when,
)

DEFAULT_QUESTIONS = tuple(f"q{i:02d}" for i in range(1, 21))


def build_machine(question_ids=DEFAULT_QUESTIONS, target=10, per_agent=3):
    if isinstance(question_ids, str):
        raise ValueError("question_ids must be a sequence of unique identifiers")
    questions = list(question_ids)
    if (
        not questions
        or any(
            not isinstance(q, str) or not q.isidentifier() or q.startswith("coverage_")
            for q in questions
        )
        or len(set(questions)) != len(questions)
    ):
        raise ValueError(
            "question IDs must be unique identifiers outside the coverage_ namespace"
        )
    for value in (target, per_agent):
        if type(value) is not int or value < 1:
            raise ValueError("target and per_agent must be positive integers")
    counts = field("counts")
    respondent, question = input_("respondent_id"), input_("question")
    available = filter_items(
        constant("questions"),
        item="q",
        predicate=counts.get(local("q")) < constant("target"),
    )
    ranked = reduce_(
        "sort_records",
        map_sequence(
            available,
            item="q",
            value_expr=record(question=local("q"), count=counts.get(local("q"))),
        ),
        fields=["count", "question"],
    )
    assigned = map_sequence(
        take(ranked, constant("per_agent")),
        item="row",
        value_expr=local("row").get("question"),
    )
    previous = field("answers").get(respondent, {})
    answered = previous.contains(question)
    total = reduce_("sum", counts.values())
    complete = total == constant("required_answers")
    you = current_value("respondent_id", "")
    your_assignment = field("assignments").get(you, [])
    your_answers = field("answers").get(you, {})
    pending = filter_items(
        your_assignment,
        item="q",
        predicate=(~your_answers.contains(local("q")))
        & (counts.get(local("q")) < constant("target"))
        & ~field("closed"),
    )
    return Machine(
        name="QuestionCoverage",
        constants={
            "questions": questions,
            "target": target,
            "per_agent": per_agent,
            "required_answers": len(questions) * target,
        },
        fields={
            "counts": state_field(
                T.record({q: T.integer(minimum=0, maximum=target) for q in questions}),
                {q: 0 for q in questions},
            ),
            "assignments": state_field(
                T.map(T.text(), T.sequence(T.choice(questions))), {}
            ),
            "answers": state_field(
                T.map(
                    T.text(),
                    T.map(T.choice(questions), T.integer(minimum=1, maximum=5)),
                ),
                {},
            ),
            "closed": state_field(T.boolean(), False),
        },
        commands={
            "assign": Command(
                inputs={"respondent_id": T.text()},
                timing="before_question",
                effects=(
                    assert_(
                        respondent.stripped().length() > 0, code="missing_respondent_id"
                    ),
                    when(
                        ~field("assignments").contains(respondent),
                        assert_(~field("closed"), code="coverage_closed"),
                    ),
                    put("assignments", respondent, assigned, once=True),
                ),
            ),
            "record_answer": Command(
                inputs={
                    "respondent_id": T.text(),
                    "question": T.choice(questions),
                    "answer": T.integer(minimum=1, maximum=5),
                },
                effects=(
                    assert_(
                        field("assignments").get(respondent, []).contains(question),
                        code="question_not_assigned",
                    ),
                    assert_(
                        ~answered | (previous.get(question) == input_("answer")),
                        code="answer_changed",
                    ),
                    when(~answered, assert_(~field("closed"), code="coverage_closed")),
                    when(
                        ~answered,
                        assert_(
                            counts.get(question) < constant("target"),
                            code="question_full",
                        ),
                    ),
                    when(
                        ~answered,
                        set_(
                            "counts",
                            counts.with_item(question, counts.get(question) + 1),
                        ),
                    ),
                    put(
                        "answers",
                        respondent,
                        previous.with_item(question, input_("answer")),
                    ),
                ),
            ),
        },
        complete_when=complete,
        close_effects=(set_("closed", True),),
        view={
            "counts": counts,
            "assigned": your_assignment,
            "pending": pending,
            "total_answers": total,
            "complete": complete,
        },
    )


DEMO = (
    [("assign", {"respondent_id": "R0"})]
    + [
        ("record_answer", {"respondent_id": "R0", "question": q, "answer": 3})
        for q in DEFAULT_QUESTIONS[:3]
    ]
    + [("assign", {"respondent_id": "R1"})]
    + [
        ("record_answer", {"respondent_id": "R1", "question": q, "answer": 4})
        for q in DEFAULT_QUESTIONS[3:6]
    ]
)
