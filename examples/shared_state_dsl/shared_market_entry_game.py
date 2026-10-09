"""Entry choices and congestion payoffs as collection expressions."""

from edsl.sharedstate import Command, Machine, StateType, choose, constant, current, field, arg, local, map_items, put, reduce, , state_field

entrants = reduce("count_equal", field("choices").values(), value="enter")
entrant_payoff = constant("entry_value") - constant("congestion_cost") * entrants
payoffs = map_items(field("choices"), key="player", value="action", key_expr=local("player"), value_expr=choose(local("action") == "enter", entrant_payoff, constant("outside_payoff")))
SPEC = Machine(
    name="SharedMarketEntryGame", constants={"player_count": 3, "outside_payoff": 2, "entry_value": 10, "congestion_cost": 3},
    fields={"choices": state_field(StateType.map(), {}), "entrant_count": state_field(StateType.optional(StateType.number()), None), "entrant_payoff": state_field(StateType.optional(StateType.number()), None), "payoffs": state_field(StateType.map(), {})},
    commands={"submit": Command(inputs={"player": StateType.text(), "action": StateType.choice(("enter", "stay_out"))}, effects=(put("choices", arg("player"), arg("action")),))},
    view={"player_count": constant("player_count"), "submission_count": field("choices").length(), "outside_payoff": constant("outside_payoff"), "entry_value": constant("entry_value"), "congestion_cost": constant("congestion_cost"), "choices": choose(current("closed"), field("choices"), {}), "entrant_count": choose(current("closed"), field("entrant_count"), None), "entrant_payoff": choose(current("closed"), field("entrant_payoff"), None), "payoffs": choose(current("closed"), field("payoffs"), {})},
    complete_when=field("choices").length() == constant("player_count"), close_effects=(assign("entrant_count", entrants), assign("entrant_payoff", entrant_payoff), assign("payoffs", payoffs)),
)
