"""Smallest fold example: balances plus an auditable running total."""

from edsl.sharedstate import (
    Command,
    Machine,
    T,
    field,
    fold,
    input_,
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
                T.record({"balance": T.number(), "history": T.sequence(T.number())}),
                {"balance": 0, "history": []},
            )
        },
        commands={
            "post": Command(
                inputs={"amounts": T.sequence(T.number())},
                effects=(
                    set_(
                        "ledger",
                        fold(
                            input_("amounts"),
                            field("ledger"),
                            item="amount",
                            accumulator="previous",
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
