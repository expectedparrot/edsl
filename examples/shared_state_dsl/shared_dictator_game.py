"""Unilateral bounded transfer with an explicit payoff expression."""

from edsl.sharedstate import Command, Machine, StateType, choose, constant, field, arg, map_of, set_once, state_field

SPEC = Machine(
    name="SharedDictatorGame", constants={"endowment": 100},
    fields={"dictator": state_field(StateType.optional(StateType.text()), None), "recipient": state_field(StateType.optional(StateType.text()), None), "transfer": state_field(StateType.optional(StateType.number()), None)},
    commands={"allocate": Command(inputs={"dictator": StateType.text(), "recipient": StateType.text(), "transfer": StateType.number(minimum=0, maximum=constant("endowment"))}, effects=(set_once("dictator", arg("dictator")), set_once("recipient", arg("recipient")), set_once("transfer", arg("transfer"))))},
    view={"dictator": field("dictator"), "recipient": field("recipient"), "transfer": field("transfer"), "endowment": constant("endowment"), "payoffs": choose(field("transfer") != None, map_of((field("dictator"), constant("endowment") - field("transfer")), (field("recipient"), field("transfer"))), None)},  # noqa: E711
    complete_when=field("transfer") != None,  # noqa: E711
)
