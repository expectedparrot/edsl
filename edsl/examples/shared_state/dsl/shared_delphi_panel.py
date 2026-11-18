"""Repeated estimates with generic grouped summaries and convergence."""

from edsl.sharedstate import (
    Command,
    Machine,
    StateType,
    append,
    constant,
    expr,
    field,
    arg,
    local,
    map_items,
    record,
    reduce,
    state_field,
)

summaries = reduce("group_numeric_summary", field("responses"), group="round", value="estimate")
# Keep numeric ordering inside the convergence calculation; explicitly encode
# round keys as text at the public JSON observation boundary.
summary_view = map_items(
    summaries,
    key="round",
    value="summary",
    key_expr=expr("concat", "", local("round")),
    value_expr=local("summary"),
)

SPEC = Machine(
    name="SharedDelphiPanel",
    constants={
        "panel_size": 3,
        "min_rounds": 2,
        "range_threshold": 15,
        "median_shift_threshold": 3,
    },
    fields={"responses": state_field(StateType.sequence(), [])},
    commands={
        "submit": Command(
            inputs={
                "expert": StateType.text(),
                "round": StateType.number(minimum=1),
                "estimate": StateType.number(),
                "confidence": StateType.number(),
                "rationale": StateType.text(),
            },
            effects=(
                append(
                    "responses",
                    record(
                        expert=arg("expert"),
                        round=arg("round"),
                        estimate=arg("estimate"),
                        confidence=arg("confidence"),
                        rationale=arg("rationale"),
                    ),
                ),
            ),
        )
    },
    view={"responses": field("responses"), "summaries": summary_view},
    complete_when=reduce(
        "series_converged",
        summaries,
        min_groups=constant("min_rounds"),
        min_group_size=constant("panel_size"),
        range_threshold=constant("range_threshold"),
        shift_threshold=constant("median_shift_threshold"),
    ),
)
