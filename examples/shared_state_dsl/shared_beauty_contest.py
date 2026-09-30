"""Numeric submissions with generic close-time aggregates."""

from edsl.sharedstate import Command, Machine, T, choose, constant, current, field, input_, put, reduce_, set_, state_field

mean = reduce_("mean", field("choices").values())
target = constant("factor") * mean
SPEC = Machine(
    name="SharedBeautyContest", constants={"player_count": 3, "factor": 2 / 3},
    fields={"choices": state_field(T.map(T.text(), T.number(minimum=0, maximum=100)), {}), "mean": state_field(T.optional(T.number()), None), "target": state_field(T.optional(T.number()), None), "winners": state_field(T.sequence(T.text()), [])},
    commands={"submit": Command(inputs={"player": T.text(), "choice": T.number(minimum=0, maximum=100)}, effects=(put("choices", input_("player"), input_("choice")),))},
    view={"factor": constant("factor"), "player_count": constant("player_count"), "submission_count": field("choices").length(), "choices": choose(current("closed"), field("choices"), {}), "mean": choose(current("closed"), field("mean"), None), "target": choose(current("closed"), field("target"), None), "winners": choose(current("closed"), field("winners"), [])},
    complete_when=field("choices").length() == constant("player_count"),
    close_effects=(set_("mean", mean), set_("target", target), set_("winners", reduce_("keys_min_distance", field("choices"), target=target, tolerance=1e-9))),
)
