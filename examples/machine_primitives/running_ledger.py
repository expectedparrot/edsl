"""Smallest fold example: balances plus an auditable running total."""

from edsl.sharedstate import (
    Command,
    Machine,
    StateType,
    field,
    fold,
    arg,
    local,
    record,
    set_,
    state_field,
)


def build_machine():
    previous, amount = local("previous"), local("amount")
    balance = previous.get("balance") + amount
    return Machine(
        constants={},
        name="RunningLedger",
        fields={
            "ledger": state_field(
                StateType.record({"balance": StateType.number(), "history": StateType.sequence(StateType.number())}),
                {"balance": 0, "history": []},
            )
        },
        commands={
            "post": Command(
                inputs={"amounts": StateType.sequence(StateType.number())},
                effects=(
                    set_(
                        "ledger",
                        fold(
                            arg("amounts"),
                            field("ledger"),
                            item="amount",
                            accumulator="previous",
                            accumulator_type=StateType.record(
                                {
                                    "balance": StateType.number(),
                                    "history": StateType.sequence(StateType.number()),
                                }
                            ),
                            body=record(
                                balance=balance,
                                history=previous.get("history").appended(balance),
                            ),
                        ),
                    ),
                ),
            )
        },
        view={"ledger": field("ledger")},
    )


DEMO = [("post", {"amounts": [10, -3, 5]})]
