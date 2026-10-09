"""LMSR is retained as a versioned scientific algorithm boundary."""

from edsl.sharedstate import Command, Machine, StateType, algorithm, constant, expr, field, arg, state_field

SPEC = Machine(
    name="SharedBinaryMarket",
    constants={"contract": "Event occurs", "liquidity": 50, "initial_cash": 100},
    fields={
        "q_yes": state_field(StateType.number(), 0),
        "q_no": state_field(StateType.number(), 0),
        "portfolios": state_field(StateType.map(), {}),
        "trades": state_field(StateType.sequence(), []),
        "outcome": state_field(StateType.optional(StateType.boolean()), None),
    },
    commands={
        "trade": Command(
            inputs={"trader": StateType.text(), "action": StateType.choice(("buy_yes", "buy_no", "hold")), "quantity": StateType.number(minimum=0)},
            effects=(algorithm("lmsr_trade", trader=arg("trader"), action=arg("action"), quantity=arg("quantity")),),
        ),
        "settle": Command(inputs={"outcome": StateType.boolean()}, effects=(algorithm("lmsr_settle", outcome=arg("outcome")),)),
    },
    view={
        "portfolios": field("portfolios"),
        "trades": field("trades"),
        "prices": expr("algorithm_view", "lmsr_prices", field("q_yes"), field("q_no"), constant("liquidity"), version=1),
    },
    algorithms=("lmsr_trade@1", "lmsr_settle@1", "lmsr_prices@1"),
)
