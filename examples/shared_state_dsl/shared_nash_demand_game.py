"""Two bounded demands and a feasibility-conditioned payoff map."""

from edsl.sharedstate import Command, Machine, StateType, choose, constant, current, field, arg, local, map_items, put, reduce, assign, state_field

feasible = reduce("sum", field("demands").values()) <= constant("pie")
named_demands = map_items(field("demands"), key="seat", value="amount", key_expr=field("players").get(local("seat")), value_expr=local("amount"))
payoffs = map_items(field("demands"), key="seat", value="amount", key_expr=field("players").get(local("seat")), value_expr=choose(feasible, local("amount"), 0))
SPEC = Machine(
    name="SharedNashDemandGame", constants={"pie": 100},
    fields={"demands": state_field(StateType.map(), {}), "players": state_field(StateType.map(), {}), "feasible": state_field(StateType.optional(StateType.boolean()), None), "payoffs": state_field(StateType.map(), {})},
    commands={"demand": Command(inputs={"player": StateType.text(), "seat": StateType.choice(("0", "1")), "amount": StateType.number(minimum=0, maximum=constant("pie"))}, effects=(put("demands", arg("seat"), arg("amount")), put("players", arg("seat"), arg("player"))))},
    view={"pie": constant("pie"), "submission_count": field("demands").length(), "demands": choose(current("closed"), named_demands, {}), "feasible": choose(current("closed"), field("feasible"), None), "payoffs": choose(current("closed"), field("payoffs"), {})},
    complete_when=field("demands").length() == 2, close_effects=(assign("feasible", feasible), assign("payoffs", payoffs)),
)
