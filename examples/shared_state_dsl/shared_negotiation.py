"""Append-only bilateral negotiation with terminal actions and agreement tracking."""

from edsl.sharedstate import Command, Machine, StateType, append, constant, current, field, filter_items, arg, local, map_sequence, record, set_, state_field, when

same_role = filter_items(field("turns"), item="turn", predicate=local("turn").get("role") == arg("role"))
prior_offers = filter_items(field("turns"), item="turn", predicate=local("turn").get("action") == "offer")
accepted_with_offer = (arg("action") == "accept") & (prior_offers.length() > 0)
public_turns = map_sequence(
    field("turns"), item="turn",
    value_expr=record(
        turn=local("turn").get("turn"), round=local("turn").get("round"),
        speaker=local("turn").get("speaker"), role=local("turn").get("role"),
        action=local("turn").get("action"), amount=local("turn").get("amount"),
        message=local("turn").get("message"),
    ),
)
terminal_turns = filter_items(field("turns"), item="turn", predicate=(local("turn").get("action") == "accept") | (local("turn").get("action") == "walk away"))

SPEC = Machine(
    name="SharedNegotiation", constants={"subject": "Price of a used sailboat"},
    fields={"turns": state_field(StateType.sequence(StateType.map()), []), "agreement": state_field(StateType.optional(StateType.number()), None)},
    commands={
        "record": Command(
            inputs={
                "speaker": StateType.text(), "role": StateType.choice(("buyer", "seller")),
                "action": StateType.choice(("offer", "accept", "reject", "walk away")),
                "amount": StateType.number(minimum=0), "message": StateType.text(),
            },
            effects=(
                append("turns", record(
                    turn=field("turns").length() + 1, round=same_role.length() + 1,
                    speaker=arg("speaker").stripped(), role=arg("role"),
                    action=arg("action"), amount=arg("amount"),
                    message=arg("message").stripped(), interview=current("interview_id"),
                )),
                when(accepted_with_offer, set_("agreement", prior_offers.at(prior_offers.length() - 1).get("amount"))),
            ),
        )
    },
    view={
        "subject": constant("subject"), "turns": public_turns,
        "turn_count": field("turns").length(), "agreement": field("agreement"),
    },
    complete_when=terminal_turns.length() > 0,
)
