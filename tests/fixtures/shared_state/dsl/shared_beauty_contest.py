"""Numeric submissions with generic close-time aggregates."""

from edsl.sharedstate import Command, Machine, StateType, choose, constant, current, field, arg, put, reduce, assign, state_field

mean = reduce("mean", field("choices").values())
target = constant("factor") * mean
SPEC = Machine(
    name="SharedBeautyContest", constants={"player_count": 3, "factor": 2 / 3},
    fields={"choices": state_field(StateType.map(StateType.text(), StateType.number(minimum=0, maximum=100)), {}), "mean": state_field(StateType.optional(StateType.number()), None), "target": state_field(StateType.optional(StateType.number()), None), "winners": state_field(StateType.sequence(StateType.text()), [])},
    commands={"submit": Command(inputs={"player": StateType.text(), "choice": StateType.number(minimum=0, maximum=100)}, effects=(put("choices", arg("player"), arg("choice")),))},
    view={"factor": constant("factor"), "player_count": constant("player_count"), "submission_count": field("choices").length(), "choices": choose(current("closed"), field("choices"), {}), "mean": choose(current("closed"), field("mean"), None), "target": choose(current("closed"), field("target"), None), "winners": choose(current("closed"), field("winners"), [])},
    complete_when=field("choices").length() == constant("player_count"),
    close_effects=(assign("mean", mean), assign("target", target), assign("winners", reduce("keys_min_distance", field("choices"), target=target, tolerance=1e-9))),
)
