"""Two-stage trust transfer with bounded return and explicit payoffs."""

from edsl.sharedstate import Command, Machine, T, choose, constant, field, input_, map_of, set_once, state_field

available = field("sent") * constant("multiplier")
SPEC = Machine(
    name="SharedTrustGame", constants={"endowment": 100, "multiplier": 3},
    fields={name: state_field(T.optional(type_), None) for name, type_ in {"sender": T.text(), "receiver": T.text(), "sent": T.number(), "returned": T.number()}.items()},
    commands={
        "send": Command(inputs={"player": T.text(), "amount": T.number(minimum=0, maximum=constant("endowment"))}, effects=(set_once("sender", input_("player")), set_once("sent", input_("amount")))),
        "return_funds": Command(inputs={"player": T.text(), "amount": T.number(minimum=0)}, require=(field("sent") != None) & (input_("amount") <= available), effects=(set_once("receiver", input_("player")), set_once("returned", input_("amount")))),  # noqa: E711
    },
    view={"sender": field("sender"), "receiver": field("receiver"), "sent": field("sent"), "returned": field("returned"), "endowment": constant("endowment"), "multiplier": constant("multiplier"), "receiver_available": choose(field("sent") != None, available, None), "payoffs": choose(field("returned") != None, map_of((field("sender"), constant("endowment") - field("sent") + field("returned")), (field("receiver"), available - field("returned"))), None)},  # noqa: E711
    complete_when=field("returned") != None,  # noqa: E711
)
