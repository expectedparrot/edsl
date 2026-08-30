"""LMSR is retained as a versioned scientific algorithm boundary."""

from edsl.sharedstate import Command, Machine, T, algorithm, constant, expr, field, input_, state_field

SPEC = Machine(
    name="SharedBinaryMarket",
    constants={"contract": "Event occurs", "liquidity": 50, "initial_cash": 100},
    fields={
        "q_yes": state_field(T.number(), 0),
        "q_no": state_field(T.number(), 0),
        "portfolios": state_field(T.map(), {}),
        "trades": state_field(T.sequence(), []),
        "outcome": state_field(T.optional(T.boolean()), None),
    },
    commands={
        "trade": Command(
            inputs={"trader": T.text(), "action": T.choice(("buy_yes", "buy_no", "hold")), "quantity": T.number(minimum=0)},
            effects=(algorithm("lmsr_trade", trader=input_("trader"), action=input_("action"), quantity=input_("quantity")),),
        ),
        "settle": Command(inputs={"outcome": T.boolean()}, effects=(algorithm("lmsr_settle", outcome=input_("outcome")),)),
    },
    view={
        "portfolios": field("portfolios"),
        "trades": field("trades"),
        "prices": expr("algorithm_view", "lmsr_prices", field("q_yes"), field("q_no"), constant("liquidity"), version=1),
    },
    algorithms=("lmsr_trade@1", "lmsr_settle@1", "lmsr_prices@1"),
)
