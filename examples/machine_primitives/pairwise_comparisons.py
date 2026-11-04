"""Adaptive pair selection and online logistic scores using Machine primitives.

One fixed, position-randomized pair per respondent; sequential interviews.
The score and selection policies are illustrative, not uncertainty estimates.
"""

from itertools import combinations
import math

from edsl.sharedstate import (
    Command,
    Machine,
    StateType,
    require,
    choose,
    constant,
    current_value,
    exp,
    expr,
    field,
    arg,
    let,
    local,
    logsumexp,
    map_sequence,
    put,
    record,
    reduce,
    seeded_order,
    assign,
    state_field,
    when,
)

DEFAULT_ITEMS = ("Atlas", "Beacon", "Cedar", "Dune", "Ember")


def build_machine(
    items=DEFAULT_ITEMS,
    budget=40,
    explore_every=5,
    learning_rate=0.5,
    seed="pairwise-2026",
):
    if isinstance(items, str):
        raise ValueError("items must be a sequence of distinct labels")
    items = list(items)
    if (
        len(items) < 2
        or any(not isinstance(x, str) or not x.strip() for x in items)
        or len(set(items)) != len(items)
    ):
        raise ValueError("at least two distinct nonempty item labels are required")
    for value in (budget, explore_every):
        if type(value) is not int or value < 1:
            raise ValueError("budget and explore_every must be positive integers")
    if (
        type(learning_rate) not in (int, float)
        or not math.isfinite(learning_rate)
        or not 0 < learning_rate <= 1
    ):
        raise ValueError("learning_rate must be finite and in (0, 1]")
    if not isinstance(seed, str) or not seed.strip():
        raise ValueError("seed must be nonempty text")
    pairs = [
        dict(pair_id=f"pair_{i:04d}", left=a, right=b)
        for i, (a, b) in enumerate(combinations(items, 2))
    ]
    pair_ids = [p["pair_id"] for p in pairs]
    ratings, counts = field("ratings"), field("pair_counts")
    total = field("comparisons")
    complete = total >= constant("budget")
    exploring = counts.values().contains(0) | (
        field("adaptive_streak") >= constant("explore_every") - 1
    )
    pair = local("pair")
    gap = expr(
        "absolute", ratings.get(pair.get("left")) - ratings.get(pair.get("right"))
    )
    candidates = map_sequence(
        constant("pairs"),
        item="pair",
        value_expr=record(
            pair_id=pair.get("pair_id"),
            left=pair.get("left"),
            right=pair.get("right"),
            priority=choose(local("exploring"), counts.get(pair.get("pair_id")), gap),
            secondary=choose(local("exploring"), gap, counts.get(pair.get("pair_id"))),
        ),
    )
    selected = reduce(
        "sort_records", candidates, fields=["priority", "secondary", "pair_id"]
    ).first()
    respondent = arg("respondent_id")
    assignment = let(
        "exploring",
        exploring,
        let(
            "selected",
            selected,
            record(
                pair_id=local("selected").get("pair_id"),
                options=seeded_order(
                    [local("selected").get("left"), local("selected").get("right")],
                    seed=constant("seed"),
                    scope=current_value("study_id", "study"),
                    key=respondent,
                ),
                mode=choose(local("exploring"), "explore", "adaptive"),
            ),
        ),
    )
    assigned = field("assignments").get(respondent, {})
    options = assigned.get("options", [])
    winner = arg("winner")
    loser = choose(winner == options.at(0), options.at(1), options.at(0))
    # Probability of the selected winner under the pre-answer scores. The
    # log-domain form stays finite even for very separated scores.
    expected = exp(logsumexp([0, ratings.get(loser) - ratings.get(winner)]) * -1)
    updated_ratings = let(
        "delta",
        constant("learning_rate") * (expected * -1 + 1),
        ratings.with_item(winner, ratings.get(winner) + local("delta")).with_item(
            loser, ratings.get(loser) - local("delta")
        ),
    )
    seen = field("responses").contains(respondent)
    fresh = ~seen
    you = current_value("respondent_id", "")
    yours = field("assignments").get(you, {})
    return Machine(
        name="AdaptivePairwiseComparisons",
        constants=dict(
            items=items,
            pairs=pairs,
            budget=budget,
            explore_every=explore_every,
            learning_rate=learning_rate,
            seed=seed,
        ),
        fields={
            "ratings": state_field(
                StateType.record({x: StateType.number(minimum=-budget, maximum=budget) for x in items}),
                dict.fromkeys(items, 0.0),
            ),
            "pair_counts": state_field(
                StateType.record({p: StateType.integer(minimum=0, maximum=budget) for p in pair_ids}),
                dict.fromkeys(pair_ids, 0),
            ),
            "comparisons": state_field(StateType.integer(minimum=0, maximum=budget), 0),
            "adaptive_streak": state_field(StateType.integer(minimum=0, maximum=budget), 0),
            "assignments": state_field(
                StateType.map(
                    StateType.text(),
                    StateType.record(
                        {
                            "pair_id": StateType.choice(pair_ids),
                            "options": StateType.sequence(StateType.choice(items)),
                            "mode": StateType.choice(["explore", "adaptive"]),
                        }
                    ),
                ),
                {},
            ),
            "responses": state_field(StateType.map(StateType.text(), StateType.choice(items)), {}),
            "closed": state_field(StateType.boolean(), False),
        },
        commands={
            "assign": Command(
                inputs={"respondent_id": StateType.text()},
                timing="before_question",
                effects=(
                    require(
                        respondent.stripped().length() > 0, code="missing_respondent_id"
                    ),
                    when(
                        ~field("assignments").contains(respondent),
                        require(
                            ~field("closed") & ~complete, code="comparisons_closed"
                        ),
                    ),
                    put("assignments", respondent, assignment, once=True),
                ),
            ),
            "compare": Command(
                inputs={"respondent_id": StateType.text(), "winner": StateType.choice(items)},
                effects=(
                    require(
                        field("assignments").contains(respondent),
                        code="pair_not_assigned",
                    ),
                    require(options.contains(winner), code="winner_not_in_pair"),
                    require(
                        fresh | (field("responses").get(respondent) == winner),
                        code="answer_changed",
                    ),
                    when(
                        fresh,
                        require(
                            ~field("closed") & ~complete, code="comparisons_closed"
                        ),
                    ),
                    when(fresh, assign("ratings", updated_ratings)),
                    when(
                        fresh,
                        assign(
                            "pair_counts",
                            counts.with_item(
                                assigned.get("pair_id"),
                                counts.get(assigned.get("pair_id")) + 1,
                            ),
                        ),
                    ),
                    when(fresh, assign("comparisons", total + 1)),
                    when(
                        fresh,
                        assign(
                            "adaptive_streak",
                            choose(
                                assigned.get("mode") == "explore",
                                0,
                                field("adaptive_streak") + 1,
                            ),
                        ),
                    ),
                    put("responses", respondent, winner),
                ),
            ),
        },
        complete_when=complete,
        close_effects=(assign("closed", True),),
        view={
            "options": yours.get("options", items[:2]),
            "accepting": field("assignments").contains(you)
            & ~field("responses").contains(you)
            & ~field("closed")
            & ~complete,
            "comparisons": total,
            "complete": complete,
        },
    )


# Ten warm-up comparisons followed by two score-driven selections.
DEMO = [
    command
    for i, winner in enumerate(
        (
            "Atlas",
            "Cedar",
            "Atlas",
            "Beacon",
            "Beacon",
            "Beacon",
            "Cedar",
            "Dune",
            "Atlas",
            "Atlas",
            "Atlas",
            "Beacon",
        )
    )
    for command in (
        ("assign", {"respondent_id": f"R{i}"}),
        ("compare", {"respondent_id": f"R{i}", "winner": winner}),
    )
]
