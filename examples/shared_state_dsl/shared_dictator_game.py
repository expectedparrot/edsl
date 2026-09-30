"""Unilateral bounded transfer with an explicit payoff expression."""

from edsl.sharedstate import Command, Machine, T, choose, constant, field, input_, map_of, set_once, state_field

SPEC = Machine(
    name="SharedDictatorGame", constants={"endowment": 100},
    fields={"dictator": state_field(T.optional(T.text()), None), "recipient": state_field(T.optional(T.text()), None), "transfer": state_field(T.optional(T.number()), None)},
    commands={"allocate": Command(inputs={"dictator": T.text(), "recipient": T.text(), "transfer": T.number(minimum=0, maximum=constant("endowment"))}, effects=(set_once("dictator", input_("dictator")), set_once("recipient", input_("recipient")), set_once("transfer", input_("transfer"))))},
    view={"dictator": field("dictator"), "recipient": field("recipient"), "transfer": field("transfer"), "endowment": constant("endowment"), "payoffs": choose(field("transfer") != None, map_of((field("dictator"), constant("endowment") - field("transfer")), (field("recipient"), field("transfer"))), None)},  # noqa: E711
    complete_when=field("transfer") != None,  # noqa: E711
)
