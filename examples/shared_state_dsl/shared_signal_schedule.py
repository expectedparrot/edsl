"""Configured private signals revealed once per participant and round."""

from edsl.sharedstate import Command, Machine, T, append, choose, constant, current, field, filter_items, input_, local, map_sequence, put, record, reduce_, state_field, when

participant_history = field("revealed").get(input_("participant"), [])
same_round = filter_items(participant_history, item="release", predicate=local("release").get("round") == input_("round"))
is_new = same_round.length() == 0
signal = constant("signals").get(input_("participant")).at(input_("round") - 1)
new_release = record(round=input_("round"), signal=signal)

viewer_history = field("revealed").get(current("name"), [])
rounds = map_sequence(field("events"), item="event", value_expr=local("event").get("round"))
SPEC = Machine(
    name="SharedSignalSchedule",
    constants={"signals": {"Amina": ["sunny", "windy"], "Boris": ["cloudy", "calm"]}},
    fields={"revealed": state_field(T.map(), {}), "events": state_field(T.sequence(T.map()), [])},
    commands={
        "reveal": Command(
            inputs={"participant": T.text(), "round": T.integer(minimum=1)},
            require=constant("signals").contains(input_("participant")) & (input_("round") <= constant("signals").get(input_("participant")).length()),
            effects=(
                when(is_new, put("revealed", input_("participant"), participant_history.appended(new_release))),
                when(is_new, append("events", record(participant=input_("participant"), round=input_("round")))),
            ),
            timing="before_question",
        )
    },
    view={
        "your_signal": choose(viewer_history.length() > 0, viewer_history.at(viewer_history.length() - 1).get("signal"), None),
        "your_signal_history": viewer_history,
        "release_count": field("events").length(),
        "released_by_round": reduce_("count_by", rounds),
    },
)
