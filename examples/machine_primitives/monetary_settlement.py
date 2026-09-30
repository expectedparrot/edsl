"""Exact invoice settlement: round gross once, split fee, conserve minor units."""

from edsl.sharedstate import (
    Command,
    Machine,
    T,
    assert_,
    decimal_units,
    field,
    input_,
    let,
    local,
    record,
    round_ratio,
    set_,
    state_field,
)


def build_machine():
    gross = decimal_units(input_("amount"), places=2, rounding="half_up")
    accounts = field("accounts")
    settlement = let(
        "gross",
        gross,
        let(
            "fee",
            round_ratio(local("gross") * 25, 10000, rounding="half_even"),
            record(
                payer=accounts.get("payer") - local("gross"),
                payee=accounts.get("payee") + local("gross") - local("fee"),
                fees=accounts.get("fees") + local("fee"),
            ),
        ),
    )
    return Machine(
        name="MonetarySettlement",
        constants={},
        fields={
            "accounts": state_field(
                T.record(
                    {name: T.integer(minimum=0) for name in ("payer", "payee", "fees")}
                ),
                {"payer": 100000, "payee": 0, "fees": 0},
            )
        },
        commands={
            "pay": Command(
                inputs={"amount": T.text()},
                effects=(
                    assert_(gross > 0, code="nonpositive_payment"),
                    assert_(gross <= accounts.get("payer"), code="insufficient_funds"),
                    set_("accounts", settlement),
                ),
            )
        },
        view={"accounts": accounts},
    )


DEMO = [("pay", {"amount": amount}) for amount in ["1.005", "2.00", "6.00", "9999.99"]]
