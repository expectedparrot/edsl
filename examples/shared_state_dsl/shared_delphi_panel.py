"""Repeated estimates with generic grouped summaries and convergence."""

from edsl.sharedstate import Command, Machine, T, append, constant, field, input_, record, reduce_, state_field

summaries = reduce_("group_numeric_summary", field("responses"), group="round", value="estimate")

SPEC = Machine(
    name="SharedDelphiPanel",
    constants={"panel_size": 3, "min_rounds": 2, "range_threshold": 15, "median_shift_threshold": 3},
    fields={"responses": state_field(T.sequence(), [])},
    commands={
        "submit": Command(
            inputs={"expert": T.text(), "round": T.number(minimum=1), "estimate": T.number(), "confidence": T.number(), "rationale": T.text()},
            effects=(append("responses", record(expert=input_("expert"), round=input_("round"), estimate=input_("estimate"), confidence=input_("confidence"), rationale=input_("rationale"))),),
        )
    },
    view={"responses": field("responses"), "summaries": summaries},
    complete_when=reduce_("series_converged", summaries, min_groups=constant("min_rounds"), min_group_size=constant("panel_size"), range_threshold=constant("range_threshold"), shift_threshold=constant("median_shift_threshold")),
)
