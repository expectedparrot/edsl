"""Success-bonus contract followed by a private effort choice."""

from edsl.sharedstate import Command, Machine, StateType, choose, constant, current, field, arg, map_of, set_, state_field

probability = choose(field("effort") == "high", constant("high_probability"), constant("low_probability"))
cost = choose(field("effort") == "high", constant("high_cost"), 0)
expected = map_of(
    (field("principal"), probability * (constant("output_value") - field("bonus"))),
    (field("worker"), probability * field("bonus") - cost),
)
SPEC = Machine(
    name="SharedPrincipalAgentGame",
    constants={"output_value": 100, "high_probability": 0.8, "low_probability": 0.2, "high_cost": 20},
    fields={name: state_field(StateType.optional(type_), None) for name, type_ in {
        "principal": StateType.text(), "worker": StateType.text(), "bonus": StateType.number(), "effort": StateType.text(),
    }.items()},
    commands={
        "contract": Command(inputs={"principal": StateType.text(), "bonus": StateType.number(minimum=0, maximum=constant("output_value"))}, effects=(set_("principal", arg("principal")), set_("bonus", arg("bonus")))),
        "effort": Command(inputs={"worker": StateType.text(), "effort": StateType.choice(("high", "low"))}, require=field("bonus") != None, effects=(set_("worker", arg("worker")), set_("effort", arg("effort")))),  # noqa: E711
    },
    view={
        "principal": field("principal"), "worker": field("worker"), "bonus": field("bonus"),
        "effort_chosen": field("effort") != None,  # noqa: E711
        "effort": choose(field("effort") != None, choose(current("closed"), field("effort"), "private"), None),  # noqa: E711
        "success_probability": choose(field("effort") != None, probability, None),  # noqa: E711
        "expected_payoffs": choose(field("effort") != None, expected, None),  # noqa: E711
    },
    complete_when=field("effort") != None,  # noqa: E711
)
