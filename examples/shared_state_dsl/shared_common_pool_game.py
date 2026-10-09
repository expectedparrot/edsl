"""Common-pool requests with generic map transformation at close."""

from edsl.sharedstate import Command, Machine, StateType, choose, constant, current, field, arg, local, map_items, put, reduce, , state_field

total = reduce("sum", field("requests").values())
overdrawn = total > constant("stock")
payoffs = map_items(field("requests"), key="player", value="amount", key_expr=local("player"), value_expr=choose(overdrawn, constant("stock") * local("amount") / total, local("amount") + (constant("stock") - total) / constant("player_count")))
SPEC = Machine(
    name="SharedCommonPoolGame", constants={"player_count": 3, "stock": 60, "max_request": 20},
    fields={"requests": state_field(StateType.map(StateType.text(), StateType.number()), {}), "total_requested": state_field(StateType.optional(StateType.number()), None), "overdrawn": state_field(StateType.optional(StateType.boolean()), None), "payoffs": state_field(StateType.map(), {})},
    commands={"extract": Command(inputs={"player": StateType.text(), "amount": StateType.number(minimum=0, maximum=constant("max_request"))}, effects=(put("requests", arg("player"), arg("amount")),))},
    view={"stock": constant("stock"), "max_request": constant("max_request"), "player_count": constant("player_count"), "submission_count": field("requests").length(), "requests": choose(current("closed"), field("requests"), {}), "total_requested": choose(current("closed"), field("total_requested"), None), "overdrawn": choose(current("closed"), field("overdrawn"), None), "payoffs": choose(current("closed"), field("payoffs"), {})},
    complete_when=field("requests").length() == constant("player_count"),
    close_effects=(assign("total_requested", total), assign("overdrawn", overdrawn), assign("payoffs", payoffs)),
)
