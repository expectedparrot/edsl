"""Two-stage trust transfer with bounded return and explicit payoffs."""

from edsl.sharedstate import Command, Machine, StateType, choose, constant, field, arg, map_of, set_once, state_field

available = field("sent") * constant("multiplier")
SPEC = Machine(
    name="SharedTrustGame", constants={"endowment": 100, "multiplier": 3},
    fields={name: state_field(StateType.optional(type_), None) for name, type_ in {"sender": StateType.text(), "receiver": StateType.text(), "sent": StateType.number(), "returned": StateType.number()}.items()},
    commands={
        "send": Command(inputs={"player": StateType.text(), "amount": StateType.number(minimum=0, maximum=constant("endowment"))}, effects=(set_once("sender", arg("player")), set_once("sent", arg("amount")))),
        "return_funds": Command(inputs={"player": StateType.text(), "amount": StateType.number(minimum=0)}, require=(field("sent") != None) & (arg("amount") <= available), effects=(set_once("receiver", arg("player")), set_once("returned", arg("amount")))),  # noqa: E711
    },
    view={"sender": field("sender"), "receiver": field("receiver"), "sent": field("sent"), "returned": field("returned"), "endowment": constant("endowment"), "multiplier": constant("multiplier"), "receiver_available": choose(field("sent") != None, available, None), "payoffs": choose(field("returned") != None, map_of((field("sender"), constant("endowment") - field("sent") + field("returned")), (field("receiver"), available - field("returned"))), None)},  # noqa: E711
    complete_when=field("returned") != None,  # noqa: E711
)
