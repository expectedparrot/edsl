"""Atomic abstract assignment, blinded screening, and final adjudication."""

from edsl.sharedstate import (
    Command,
    Machine,
    T,
    append,
    constant,
    current,
    field,
    filter_items,
    input_,
    local,
    put,
    record,
    set_,
    state_field,
)


DECISIONS = ("include", "exclude", "uncertain")
PAPERS = (
    {
        "id": "P1",
        "title": "Cash transfers and school attendance",
        "abstract": (
            "We randomly assigned 420 rural households to receive an unconditional "
            "cash transfer or no transfer and measured student attendance after one year."
        ),
    },
    {
        "id": "P2",
        "title": "Teachers' views of attendance incentives",
        "abstract": (
            "We interviewed 24 teachers about whether financial incentives might "
            "improve attendance; the study collected no student outcomes."
        ),
    },
    {
        "id": "P3",
        "title": "Text reminders for caregivers",
        "abstract": (
            "Six schools were assigned to send attendance reminders to caregivers. "
            "Attendance was compared with six matched schools over eight weeks."
        ),
    },
)

# Each paper appears twice so that it receives two independent initial reviews.
ASSIGNMENTS = (PAPERS[0], PAPERS[1], PAPERS[2], PAPERS[0], PAPERS[1], PAPERS[2])
can_claim = (
    ~field("claims").contains(input_("reviewer"))
    & (field("available").length() > 0)
)
relevant_reviews = filter_items(
    field("reviews"),
    item="review",
    predicate=local("review").get("paper") == current("paper_id"),
)

SPEC = Machine(
    name="SystematicReviewScreening",
    constants={"papers": PAPERS, "decisions": DECISIONS},
    fields={
        "available": state_field(T.sequence(T.map()), ASSIGNMENTS),
        "claims": state_field(T.map(T.text(), T.map()), {}),
        "reviews": state_field(T.sequence(T.map()), []),
        "final_decisions": state_field(T.map(T.text(), T.map()), {}),
    },
    commands={
        "claim": Command(
            inputs={"reviewer": T.text()},
            require=can_claim,
            effects=(
                put("claims", input_("reviewer"), field("available").first()),
                # The claim and queue removal are committed as one transition.
                # A later read, not this command's outcome, is authoritative.
                set_("available", field("available").drop_first()),
            ),
            timing="before_question",
        ),
        "review": Command(
            inputs={
                "reviewer": T.text(),
                "decision": T.choice(DECISIONS),
                "reason": T.text(),
            },
            require=field("claims").contains(input_("reviewer")),
            effects=(
                append(
                    "reviews",
                    record(
                        reviewer=input_("reviewer"),
                        paper=field("claims").get(input_("reviewer")).get("id"),
                        decision=input_("decision"),
                        reason=input_("reason"),
                    ),
                ),
            ),
        ),
        "adjudicate": Command(
            inputs={
                "paper": T.choice(tuple(paper["id"] for paper in PAPERS)),
                "adjudicator": T.text(),
                "decision": T.choice(DECISIONS),
                "reason": T.text(),
            },
            effects=(
                put(
                    "final_decisions",
                    input_("paper"),
                    record(
                        adjudicator=input_("adjudicator"),
                        decision=input_("decision"),
                        reason=input_("reason"),
                    ),
                    once=True,
                ),
            ),
        ),
    },
    view={
        "papers": constant("papers"),
        "remaining_assignment_count": field("available").length(),
        "my_claim": field("claims").get(current("name")),
        "claim_count": field("claims").length(),
        "reviews": field("reviews"),
        "relevant_reviews": relevant_reviews,
        "final_decisions": field("final_decisions"),
    },
)
