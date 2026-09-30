"""Two bounded demands and a feasibility-conditioned payoff map."""

from edsl.sharedstate import Command, Machine, T, choose, constant, current, field, input_, local, map_items, put, reduce_, set_, state_field

feasible = reduce_("sum", field("demands").values()) <= constant("pie")
named_demands = map_items(field("demands"), key="seat", value="amount", key_expr=field("players").get(local("seat")), value_expr=local("amount"))
payoffs = map_items(field("demands"), key="seat", value="amount", key_expr=field("players").get(local("seat")), value_expr=choose(feasible, local("amount"), 0))
SPEC = Machine(
    name="SharedNashDemandGame", constants={"pie": 100},
    fields={"demands": state_field(T.map(), {}), "players": state_field(T.map(), {}), "feasible": state_field(T.optional(T.boolean()), None), "payoffs": state_field(T.map(), {})},
    commands={"demand": Command(inputs={"player": T.text(), "seat": T.choice(("0", "1")), "amount": T.number(minimum=0, maximum=constant("pie"))}, effects=(put("demands", input_("seat"), input_("amount")), put("players", input_("seat"), input_("player"))))},
    view={"pie": constant("pie"), "submission_count": field("demands").length(), "demands": choose(current("closed"), named_demands, {}), "feasible": choose(current("closed"), field("feasible"), None), "payoffs": choose(current("closed"), field("payoffs"), {})},
    complete_when=field("demands").length() == 2, close_effects=(set_("feasible", feasible), set_("payoffs", payoffs)),
)
