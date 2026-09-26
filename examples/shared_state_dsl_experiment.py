"""Design experiment: express every current SharedPrimitive with a small DSL.

This is deliberately not wired into EDSL execution.  It is a serializable
catalog used to test the proposed DSL's expressive surface before changing core
objects.  Run this file to validate JSON serialization and print a coverage
report.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import json
from typing import Any


@dataclass(frozen=True)
class Node:
    """One serializable expression or atomic effect node."""

    op: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)


def node(op: str, *args: Any, **kwargs: Any) -> Node:
    return Node(op, args, kwargs)


def ref(namespace: str, name: str) -> Node:
    return node("ref", namespace=namespace, name=name)


def state(name: str) -> Node:
    return ref("state", name)


def value(name: str) -> Node:
    return ref("input", name)


def const(name: str) -> Node:
    return ref("constant", name)


def current(name: str) -> Node:
    return ref("current", name)


def typ(kind: str, **constraints: Any) -> Node:
    return node("type", kind, **constraints)


TEXT = typ("text")
NUMBER = typ("number")
BOOLEAN = typ("boolean")
ANY = typ("any")


def choice(options: Any) -> Node:
    return typ("choice", options=options)


def mapping(key: Node = TEXT, item: Node = ANY) -> Node:
    return typ("map", key=key, item=item)


def sequence(item: Node = ANY) -> Node:
    return typ("sequence", item=item)


def optional(item: Node) -> Node:
    return typ("optional", item=item)


@dataclass(frozen=True)
class Field:
    type: Node
    initial: Any


@dataclass(frozen=True)
class Command:
    inputs: dict[str, Node] = field(default_factory=dict)
    require: Node | None = None
    effects: tuple[Node, ...] = ()
    timing: str = "after_answer"


@dataclass(frozen=True)
class Machine:
    constants: dict[str, Any] = field(default_factory=dict)
    fields: dict[str, Field] = field(default_factory=dict)
    commands: dict[str, Command] = field(default_factory=dict)
    view: dict[str, Node] = field(default_factory=dict)
    complete_when: Node | None = None
    close_effects: tuple[Node, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        for command_name, spec in self.commands.items():
            for effect in spec.effects:
                if effect.op in {"set", "set_once", "put", "append", "increment"}:
                    target = effect.args[0]
                    if target not in self.fields:
                        errors.append(
                            f"{command_name}: effect targets unknown field {target!r}"
                        )
            for item in walk(spec):
                if item.op != "ref" or item.kwargs.get("namespace") != "input":
                    continue
                name = item.kwargs["name"]
                if name != "input_record" and name not in spec.inputs:
                    errors.append(
                        f"{command_name}: references undeclared input {name!r}"
                    )
        return errors


# The generic effect vocabulary.  An executor applies a command's effects
# atomically against one state version.
def set_(target: str, expression: Any) -> Node:
    return node("set", target, expression)


def set_once(target: str, expression: Any) -> Node:
    return node("set_once", target, expression)


def put(target: str, key: Any, item: Any, *, once: bool = False) -> Node:
    return node("put", target, key, item, once=once)


def append(target: str, item: Any) -> Node:
    return node("append", target, item)


def increment(target: str, key: Any, amount: Any = 1) -> Node:
    return node("increment", target, key, amount)


def call(name: str, *args: Any, **kwargs: Any) -> Node:
    """Pure, registered expression used inside guards, views, or effects."""

    return node("call", name, *args, **kwargs)


def algorithm(name: str, **bindings: Any) -> Node:
    """Versioned registered algorithm for transitions not worth expanding."""

    return node("algorithm", name, version=1, **bindings)


def record(**items: Any) -> Node:
    return node("record", **items)


def command(
    *,
    inputs: dict[str, Node] | None = None,
    require: Node | None = None,
    effects: list[Node] | tuple[Node, ...] = (),
    timing: str = "after_answer",
) -> Command:
    return Command(inputs or {}, require, tuple(effects), timing)


def basic_view(*names: str, **derived: Node) -> dict[str, Node]:
    return {name: state(name) for name in names} | derived


def recipes() -> dict[str, Machine]:
    """Return DSL rewrites for all concrete classes in primitives.py."""

    r: dict[str, Machine] = {}

    r["SharedRegister"] = Machine(
        constants={"value_contract": "configured"},
        fields={"values": Field(mapping(TEXT, ANY), {})},
        commands={
            "set": command(
                inputs={"key": TEXT, "value": ANY},
                effects=[put("values", value("key"), value("value"))],
            )
        },
        view=basic_view("values"),
    )

    r["SharedLog"] = Machine(
        fields={"entries": Field(sequence(ANY), [])},
        commands={
            "append": command(
                inputs={"entry": ANY}, effects=[append("entries", value("entry"))]
            )
        },
        view=basic_view(
            "entries",
            count=call("length", state("entries")),
            tail=call("tail", state("entries"), 10),
        ),
    )

    r["SharedWorkPool"] = Machine(
        constants={"items": "configured work-item records"},
        fields={
            "available": Field(sequence(ANY), const("items")),
            "claims": Field(mapping(TEXT, ANY), {}),
            "completed": Field(mapping(TEXT, ANY), {}),
        },
        commands={
            "claim_before": command(
                inputs={"claimant": TEXT},
                effects=[algorithm("claim_first_available", claimant=value("claimant"))],
                timing="before_question",
            ),
            "complete": command(
                inputs={"claimant": TEXT, "result": ANY},
                require=call("has_key", state("claims"), value("claimant")),
                effects=[
                    put(
                        "completed",
                        value("claimant"),
                        record(
                            item=call("get", state("claims"), value("claimant")),
                            result=value("result"),
                        ),
                    )
                ],
            ),
        },
        view=basic_view("available", "claims", "completed"),
    )

    r["SharedSignalSchedule"] = Machine(
        constants={"signals": "participant -> ordered signals"},
        fields={
            "revealed": Field(mapping(TEXT, sequence(ANY)), {}),
            "events": Field(sequence(ANY), []),
        },
        commands={
            "reveal_before": command(
                inputs={"participant": TEXT, "round": NUMBER},
                effects=[algorithm("reveal_scheduled_signal")],
                timing="before_question",
            )
        },
        view=basic_view("revealed", "events"),
    )

    r["SharedCounterMap"] = Machine(
        constants={"keys": "configured choices"},
        fields={"counts": Field(mapping(TEXT, NUMBER), call("zeros", const("keys")))},
        commands={
            "tally": command(
                inputs={"selected": typ("checkbox", options=const("keys"))},
                effects=[algorithm("increment_selected", selected=value("selected"))],
            )
        },
        view=basic_view("counts"),
    )

    r["SharedDocument"] = Machine(
        constants={"title": "configured", "initial_text": "configured"},
        fields={
            "text": Field(TEXT, const("initial_text")),
            "revisions": Field(sequence(ANY), []),
        },
        commands={
            "revise": command(
                inputs={
                    "text": TEXT,
                    "rationale": TEXT,
                    "author": TEXT,
                    "round": NUMBER,
                },
                effects=[
                    set_("text", value("text")),
                    append(
                        "revisions",
                        record(
                            text=value("text"),
                            rationale=value("rationale"),
                            author=value("author"),
                            round=value("round"),
                        ),
                    ),
                ],
            )
        },
        view=basic_view("text", "revisions"),
    )

    r["SharedMessageBoard"] = Machine(
        fields={"messages": Field(sequence(ANY), [])},
        commands={
            "add": command(
                inputs={"author": TEXT, "message": TEXT, "reply_to": optional(TEXT)},
                effects=[
                    append(
                        "messages",
                        record(
                            author=value("author"),
                            message=value("message"),
                            reply_to=value("reply_to"),
                        ),
                    )
                ],
            )
        },
        view=basic_view("messages", message_count=call("length", state("messages"))),
    )

    r["SharedAgenda"] = Machine(
        fields={
            "proposals": Field(sequence(ANY), []),
            "ballots": Field(sequence(ANY), []),
        },
        commands={
            "propose": command(
                inputs={"proposer": TEXT, "title": TEXT},
                effects=[algorithm("append_numbered_proposal")],
            ),
            "vote": command(
                inputs={"voter": TEXT, "votes": typ("matrix", values=("up", "neutral", "down"))},
                effects=[append("ballots", record(voter=value("voter"), votes=value("votes")))],
            ),
        },
        view=basic_view(
            "proposals",
            "ballots",
            scores=call("weighted_tallies", state("ballots"), up=1, neutral=0, down=-1),
        ),
    )

    r["SharedNegotiation"] = Machine(
        constants={"subject": "configured"},
        fields={"turns": Field(sequence(ANY), [])},
        commands={
            "record": command(
                inputs={
                    "speaker": TEXT,
                    "role": TEXT,
                    "action": choice(("offer", "accept", "walk away")),
                    "amount": optional(NUMBER),
                    "message": TEXT,
                },
                effects=[append("turns", value("input_record"))],
            )
        },
        view=basic_view("turns"),
        complete_when=call("any_field_in", state("turns"), "action", ("accept", "walk away")),
    )

    r["SharedForecast"] = Machine(
        fields={"forecasts": Field(sequence(ANY), [])},
        commands={
            "submit": command(
                inputs={
                    "forecaster": TEXT,
                    "round": NUMBER,
                    "probability": typ("number", minimum=0, maximum=1),
                    "confidence": typ("number", minimum=0, maximum=1),
                },
                effects=[append("forecasts", value("input_record"))],
            )
        },
        view=basic_view(
            "forecasts",
            consensus=call("weighted_mean", state("forecasts"), "probability", "confidence"),
        ),
    )

    r["SharedDelphiPanel"] = Machine(
        constants={
            "panel_size": "configured",
            "range_threshold": "configured",
            "median_shift_threshold": "configured",
            "min_rounds": "configured",
        },
        fields={"responses": Field(sequence(ANY), [])},
        commands={
            "submit": command(
                inputs={
                    "expert": TEXT,
                    "round": NUMBER,
                    "estimate": NUMBER,
                    "confidence": NUMBER,
                    "rationale": TEXT,
                },
                effects=[append("responses", value("input_record"))],
            )
        },
        view=basic_view("responses", summaries=call("delphi_summaries", state("responses"))),
        complete_when=call("delphi_converged", state("responses")),
    )

    # Allocation and matching recipes.
    r["SharedMatchPool"] = Machine(
        constants={"items": "configured", "rule": "configured", "capacity": "configured"},
        fields={"requests": Field(sequence(ANY), []), "matches": Field(mapping(), {})},
        commands={
            "collect": command(
                inputs={"claimant": TEXT, "ranking": typ("rank", options=const("items")), "priority": NUMBER},
                effects=[append("requests", value("input_record"))],
            )
        },
        view=basic_view("requests", "matches"),
        close_effects=(algorithm("serial_dictatorship_match"),),
    )

    r["SharedDeferredAcceptance"] = Machine(
        constants={"capacities": "configured", "priorities": "configured"},
        fields={"requests": Field(sequence(ANY), []), "matches": Field(mapping(), {})},
        commands={
            "collect": command(
                inputs={"student": TEXT, "ranking": typ("rank", options=call("keys", const("capacities")))},
                effects=[append("requests", value("input_record"))],
            )
        },
        view=basic_view("requests", "matches"),
        close_effects=(algorithm("deferred_acceptance"),),
    )

    r["SharedCoalitionPool"] = Machine(
        constants={"coalitions": "name -> platform and capacity"},
        fields={
            "memberships": Field(mapping(), {}),
            "members": Field(mapping(TEXT, sequence(TEXT)), call("empty_lists", call("keys", const("coalitions")))),
            "requests": Field(sequence(ANY), []),
        },
        commands={
            "request": command(
                inputs={"member": TEXT, "coalition": choice(call("keys", const("coalitions"))), "round": NUMBER},
                effects=[algorithm("capacity_constrained_membership")],
            )
        },
        view=basic_view("memberships", "members", "requests"),
    )

    r["SharedBudgetPool"] = Machine(
        constants={"total": "configured", "projects": "configured"},
        fields={
            "remaining": Field(NUMBER, const("total")),
            "funded": Field(mapping(TEXT, NUMBER), call("zeros", call("keys", const("projects")))),
            "allocations": Field(sequence(ANY), []),
        },
        commands={
            "fund": command(
                inputs={"sponsor": TEXT, "round": NUMBER, "project": choice(call("keys", const("projects"))), "amount": NUMBER},
                effects=[algorithm("partial_fund_under_contention")],
            )
        },
        view=basic_view("remaining", "funded", "allocations"),
        complete_when=call("equals", state("remaining"), 0),
    )

    r["SharedResourceBoard"] = Machine(
        constants={"incidents": "configured", "resources": "configured"},
        fields={
            "assignments": Field(mapping(), {}),
            "resource_use": Field(mapping(), {}),
            "attempts": Field(sequence(ANY), []),
        },
        commands={
            "allocate": command(
                inputs={"responder": TEXT, "round": NUMBER, "incident": choice(call("ids", const("incidents"))), "resource": choice(call("keys", const("resources")))},
                effects=[algorithm("capability_constrained_allocation")],
            )
        },
        view=basic_view("assignments", "resource_use", "attempts"),
    )

    # Markets.
    r["SharedAuction"] = Machine(
        constants={"item": "configured", "increment": "configured"},
        fields={
            "bids": Field(sequence(NUMBER), []),
            "winner": Field(optional(ANY), None),
        },
        commands={"bid": command(inputs={"amount": NUMBER}, effects=[append("bids", value("amount"))])},
        view=basic_view("bids", high_bid=call("max", state("bids"))),
        close_effects=(set_("winner", call("argmax", state("bids"))),),
    )

    r["SharedSealedAuction"] = Machine(
        constants={"mechanism": "configured", "bidder_count": "configured"},
        fields={"bids": Field(mapping(TEXT, ANY), {}), "outcome": Field(optional(ANY), None)},
        commands={
            "bid": command(
                inputs={"bidder": TEXT, "seat": NUMBER, "private_value": NUMBER, "amount": NUMBER},
                effects=[put("bids", value("bidder"), value("input_record"), once=True)],
            )
        },
        view={"bid_count": call("length", state("bids")), "outcome": state("outcome")},
        close_effects=(algorithm("sealed_auction_settlement"),),
    )

    r["SharedDoubleAuction"] = Machine(
        constants={"participants": "configured accounts"},
        fields={
            "accounts": Field(mapping(), const("participants")),
            "orders": Field(sequence(ANY), []),
            "trades": Field(sequence(ANY), []),
        },
        commands={
            "submit": command(
                inputs={"trader": TEXT, "round": NUMBER, "action": choice(("buy", "sell", "hold")), "price": NUMBER},
                effects=[algorithm("continuous_double_auction")],
            )
        },
        view=basic_view("accounts", "orders", "trades"),
        close_effects=(algorithm("double_auction_mark_to_market"),),
    )

    r["SharedBinaryMarket"] = Machine(
        constants={"contract": "configured", "liquidity": 50, "initial_cash": 100},
        fields={
            "q_yes": Field(NUMBER, 0),
            "q_no": Field(NUMBER, 0),
            "portfolios": Field(mapping(), {}),
            "trades": Field(sequence(ANY), []),
            "outcome": Field(optional(BOOLEAN), None),
        },
        commands={
            "trade": command(
                inputs={"trader": TEXT, "round": NUMBER, "action": choice(("buy_yes", "buy_no", "hold")), "quantity": NUMBER},
                effects=[algorithm("lmsr_trade")],
            ),
            "settle": command(inputs={"outcome": BOOLEAN}, effects=[algorithm("lmsr_settle")]),
        },
        view=basic_view("portfolios", "trades", "outcome", prices=call("lmsr_prices", state("q_yes"), state("q_no"), const("liquidity"))),
    )

    # Economic games.  Simple games use the generic effects; payoff views use
    # pure registered functions when spelling the arithmetic would obscure the
    # structural comparison this experiment is intended to make.
    r["SharedUltimatumGame"] = Machine(
        constants={"stake": 100},
        fields={
            "offer": Field(optional(NUMBER), None),
            "proposer": Field(optional(TEXT), None),
            "responder": Field(optional(TEXT), None),
            "accepted": Field(optional(BOOLEAN), None),
        },
        commands={
            "offer": command(inputs={"player": TEXT, "offer": typ("number", minimum=0, maximum=const("stake"))}, effects=[set_once("offer", value("offer")), set_once("proposer", value("player"))]),
            "respond": command(inputs={"player": TEXT, "decision": choice(("accept", "reject"))}, require=call("is_set", state("offer")), effects=[set_once("accepted", call("equals", value("decision"), "accept")), set_once("responder", value("player"))]),
        },
        view=basic_view("offer", "proposer", "responder", "accepted", payoffs=call("ultimatum_payoffs", state("offer"), state("accepted"), const("stake"))),
        complete_when=call("is_set", state("accepted")),
    )

    r["SharedMoneyRequestGame"] = Machine(
        constants={"minimum": 11, "maximum": 20, "bonus": 20},
        fields={"choices": Field(mapping(TEXT, NUMBER), {})},
        commands={"submit": command(inputs={"player": TEXT, "request": typ("number", minimum=const("minimum"), maximum=const("maximum"))}, effects=[put("choices", value("player"), value("request"), once=True)])},
        view=basic_view("choices", payoffs=call("money_request_payoffs", state("choices"), const("bonus"))),
    )

    r["SharedMatrixGame"] = Machine(
        constants={"actions": "configured", "payoffs": "configured matrix"},
        fields={"choices": Field(mapping(), {}), "players": Field(mapping(), {})},
        commands={"submit": command(inputs={"player": TEXT, "seat": NUMBER, "action": choice(const("actions"))}, effects=[put("choices", value("seat"), value("action"), once=True), put("players", value("seat"), value("player"), once=True)])},
        view=basic_view("choices", "players", payoffs=call("matrix_payoffs", state("choices"), const("payoffs"))),
    )

    r["SharedRepeatedMatrixGame"] = Machine(
        constants={"actions": "configured", "payoffs": "configured matrix", "round_count": "configured"},
        fields={"rounds": Field(mapping(), {}), "players": Field(mapping(), {})},
        commands={"submit": command(inputs={"player": TEXT, "seat": NUMBER, "round": NUMBER, "action": choice(const("actions"))}, effects=[algorithm("record_repeated_matrix_action")])},
        view=basic_view("rounds", "players", history=call("matrix_history", state("rounds"), const("payoffs"))),
    )

    r["SharedDictatorGame"] = Machine(
        constants={"endowment": 100},
        fields={"dictator": Field(optional(TEXT), None), "recipient": Field(optional(TEXT), None), "transfer": Field(optional(NUMBER), None)},
        commands={"allocate": command(inputs={"dictator": TEXT, "recipient": TEXT, "transfer": typ("number", minimum=0, maximum=const("endowment"))}, effects=[set_once("dictator", value("dictator")), set_once("recipient", value("recipient")), set_once("transfer", value("transfer"))])},
        view=basic_view("dictator", "recipient", "transfer", payoffs=call("dictator_payoffs", state("transfer"), const("endowment"))),
    )

    r["SharedTrustGame"] = Machine(
        constants={"endowment": 100, "multiplier": 3},
        fields={"sender": Field(optional(TEXT), None), "receiver": Field(optional(TEXT), None), "sent": Field(optional(NUMBER), None), "returned": Field(optional(NUMBER), None)},
        commands={
            "send": command(inputs={"player": TEXT, "amount": typ("number", minimum=0, maximum=const("endowment"))}, effects=[set_once("sender", value("player")), set_once("sent", value("amount"))]),
            "return_funds": command(inputs={"player": TEXT, "amount": NUMBER}, require=call("between", value("amount"), 0, call("multiply", state("sent"), const("multiplier"))), effects=[set_once("receiver", value("player")), set_once("returned", value("amount"))]),
        },
        view=basic_view("sender", "receiver", "sent", "returned", payoffs=call("trust_payoffs", state("sent"), state("returned"), const("endowment"), const("multiplier"))),
    )

    r["SharedBeautyContest"] = Machine(
        constants={"player_count": "configured", "factor": 2 / 3},
        fields={"choices": Field(mapping(TEXT, NUMBER), {})},
        commands={"submit": command(inputs={"player": TEXT, "guess": NUMBER}, effects=[put("choices", value("player"), value("guess"), once=True)])},
        view=basic_view("choices", outcome=call("beauty_contest", state("choices"), const("factor"))),
    )

    r["SharedCommonPoolGame"] = Machine(
        constants={"player_count": "configured", "stock": 60, "max_request": 20},
        fields={"requests": Field(mapping(TEXT, NUMBER), {})},
        commands={"extract": command(inputs={"player": TEXT, "amount": typ("number", minimum=0, maximum=const("max_request"))}, effects=[put("requests", value("player"), value("amount"), once=True)])},
        view=basic_view("requests", outcome=call("common_pool_outcome", state("requests"), const("stock"))),
    )

    r["SharedCentipedeGame"] = Machine(
        constants={"take_payoffs": "configured", "final_pass_payoffs": "configured"},
        fields={"history": Field(sequence(ANY), []), "outcome": Field(optional(TEXT), None), "payoffs": Field(optional(ANY), None)},
        commands={"move": command(inputs={"player": TEXT, "node": NUMBER, "action": choice(("take", "pass"))}, effects=[algorithm("centipede_move")])},
        view=basic_view("history", "outcome", "payoffs"),
        complete_when=call("is_set", state("outcome")),
    )

    r["SharedMarketEntryGame"] = Machine(
        constants={"player_count": "configured", "outside_payoff": "configured", "entry_value": "configured", "congestion_cost": "configured"},
        fields={"choices": Field(mapping(TEXT, BOOLEAN), {})},
        commands={"submit": command(inputs={"player": TEXT, "enter": BOOLEAN}, effects=[put("choices", value("player"), value("enter"), once=True)])},
        view=basic_view("choices", payoffs=call("market_entry_payoffs", state("choices"), current("constants"))),
    )

    r["SharedBilateralTrade"] = Machine(
        fields={"buyer": Field(optional(TEXT), None), "seller": Field(optional(TEXT), None), "buyer_value": Field(optional(NUMBER), None), "seller_cost": Field(optional(NUMBER), None), "price": Field(optional(NUMBER), None), "accepted": Field(optional(BOOLEAN), None)},
        commands={
            "offer": command(inputs={"buyer": TEXT, "buyer_value": NUMBER, "price": NUMBER}, effects=[set_once("buyer", value("buyer")), set_once("buyer_value", value("buyer_value")), set_once("price", value("price"))]),
            "respond": command(inputs={"seller": TEXT, "seller_cost": NUMBER, "decision": choice(("accept", "reject"))}, require=call("is_set", state("price")), effects=[set_once("seller", value("seller")), set_once("seller_cost", value("seller_cost")), set_once("accepted", call("equals", value("decision"), "accept"))]),
        },
        view=basic_view("buyer", "seller", "price", "accepted", payoffs=call("bilateral_trade_payoffs", current("state"))),
        complete_when=call("is_set", state("accepted")),
    )

    r["SharedSignalingGame"] = Machine(
        constants={"wage": 60},
        fields={"worker": Field(optional(TEXT), None), "employer": Field(optional(TEXT), None), "education": Field(optional(BOOLEAN), None), "productivity": Field(optional(NUMBER), None), "signal_cost": Field(optional(NUMBER), None), "hired": Field(optional(BOOLEAN), None)},
        commands={
            "signal": command(inputs={"worker": TEXT, "productivity": NUMBER, "signal_cost": NUMBER, "education": BOOLEAN}, effects=[set_once("worker", value("worker")), set_once("productivity", value("productivity")), set_once("signal_cost", value("signal_cost")), set_once("education", value("education"))]),
            "decide": command(inputs={"employer": TEXT, "hire": BOOLEAN}, require=call("is_set", state("education")), effects=[set_once("employer", value("employer")), set_once("hired", value("hire"))]),
        },
        view=basic_view("worker", "employer", "education", "hired", payoffs=call("signaling_payoffs", current("state"), const("wage"))),
        complete_when=call("is_set", state("hired")),
    )

    r["SharedNashDemandGame"] = Machine(
        constants={"pie": 100},
        fields={"demands": Field(mapping(NUMBER, NUMBER), {}), "players": Field(mapping(NUMBER, TEXT), {})},
        commands={"demand": command(inputs={"player": TEXT, "seat": NUMBER, "amount": typ("number", minimum=0, maximum=const("pie"))}, effects=[put("demands", value("seat"), value("amount"), once=True), put("players", value("seat"), value("player"), once=True)])},
        view=basic_view("demands", "players", payoffs=call("nash_demand_payoffs", state("demands"), const("pie"))),
    )

    r["SharedVotingGame"] = Machine(
        constants={"candidates": "configured", "voter_count": "configured"},
        fields={"ballots": Field(mapping(TEXT, TEXT), {})},
        commands={"vote": command(inputs={"voter": TEXT, "candidate": choice(const("candidates"))}, effects=[put("ballots", value("voter"), value("candidate"), once=True)])},
        view=basic_view("ballots", tallies=call("count_by", call("values", state("ballots")))),
    )

    r["SharedCheapTalkGame"] = Machine(
        fields={"sender": Field(optional(TEXT), None), "receiver": Field(optional(TEXT), None), "state": Field(optional(ANY), None), "preference": Field(optional(ANY), None), "message": Field(optional(TEXT), None), "action": Field(optional(ANY), None)},
        commands={
            "message": command(inputs={"sender": TEXT, "state": ANY, "preference": ANY, "message": TEXT}, effects=[set_once("sender", value("sender")), set_once("state", value("state")), set_once("preference", value("preference")), set_once("message", value("message"))]),
            "act": command(inputs={"receiver": TEXT, "action": ANY}, require=call("is_set", state("message")), effects=[set_once("receiver", value("receiver")), set_once("action", value("action"))]),
        },
        view=basic_view("sender", "receiver", "message", "action", outcome=call("cheap_talk_outcome", current("state"))),
        complete_when=call("is_set", state("action")),
    )

    r["SharedPrincipalAgentGame"] = Machine(
        constants={"output_value": "configured", "high_probability": "configured", "low_probability": "configured", "high_cost": "configured"},
        fields={"principal": Field(optional(TEXT), None), "worker": Field(optional(TEXT), None), "bonus": Field(optional(NUMBER), None), "effort": Field(optional(TEXT), None)},
        commands={
            "contract": command(inputs={"principal": TEXT, "bonus": NUMBER}, effects=[set_once("principal", value("principal")), set_once("bonus", value("bonus"))]),
            "effort": command(inputs={"worker": TEXT, "effort": choice(("high", "low"))}, require=call("is_set", state("bonus")), effects=[set_once("worker", value("worker")), set_once("effort", value("effort"))]),
        },
        view=basic_view("principal", "worker", "bonus", "effort", expected_payoffs=call("principal_agent_payoffs", current("state"), current("constants"))),
        complete_when=call("is_set", state("effort")),
    )

    return r


CURRENT_CONCRETE_PRIMITIVES = {
    "SharedLog",
    "SharedWorkPool",
    "SharedSignalSchedule",
    "SharedBinaryMarket",
    "SharedUltimatumGame",
    "SharedMoneyRequestGame",
    "SharedMatrixGame",
    "SharedRepeatedMatrixGame",
    "SharedDictatorGame",
    "SharedTrustGame",
    "SharedBeautyContest",
    "SharedCommonPoolGame",
    "SharedCentipedeGame",
    "SharedMarketEntryGame",
    "SharedSealedAuction",
    "SharedBilateralTrade",
    "SharedSignalingGame",
    "SharedNashDemandGame",
    "SharedVotingGame",
    "SharedCheapTalkGame",
    "SharedPrincipalAgentGame",
    "SharedCoalitionPool",
    "SharedBudgetPool",
    "SharedDocument",
    "SharedCounterMap",
    "SharedMatchPool",
    "SharedDeferredAcceptance",
    "SharedDoubleAuction",
    "SharedResourceBoard",
    "SharedAuction",
    "SharedMessageBoard",
    "SharedNegotiation",
    "SharedAgenda",
    "SharedDelphiPanel",
    "SharedForecast",
}


def walk(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from walk(item)
    elif isinstance(value, Node):
        yield value
        yield from walk(value.args)
        yield from walk(value.kwargs)
    elif hasattr(value, "__dataclass_fields__"):
        for item in fields(value):
            yield from walk(getattr(value, item.name))


def report() -> dict[str, Any]:
    catalog = recipes()
    represented = set(catalog) - {"SharedRegister"}
    missing = sorted(CURRENT_CONCRETE_PRIMITIVES - represented)
    extra = sorted(represented - CURRENT_CONCRETE_PRIMITIVES)
    payload = {name: recipe.to_dict() for name, recipe in catalog.items()}
    serialized = json.dumps(payload, sort_keys=True)
    all_nodes = list(walk(catalog))
    algorithm_names = sorted(
        {n.args[0] for n in all_nodes if n.op == "algorithm"}
    )
    call_names = sorted({n.args[0] for n in all_nodes if n.op == "call"})
    validation_errors = {
        name: errors
        for name, recipe in catalog.items()
        if (errors := recipe.validation_errors())
    }
    return {
        "recipe_count": len(catalog),
        "current_primitive_count": len(CURRENT_CONCRETE_PRIMITIVES),
        "missing": missing,
        "extra": extra,
        "validation_errors": validation_errors,
        "serialized_bytes": len(serialized.encode()),
        "kernel_node_kinds": sorted({n.op for n in all_nodes}),
        "registered_transition_algorithms": algorithm_names,
        "pure_function_names": call_names,
    }


if __name__ == "__main__":
    summary = report()
    assert not summary["missing"], summary
    assert not summary["extra"], summary
    assert not summary["validation_errors"], summary
    print(json.dumps(summary, indent=2))
