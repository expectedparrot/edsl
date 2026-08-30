"""Deterministic local interpreter for shared-state machine definitions."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import math
from typing import Any, Callable

from .dsl import Command, Effect, Expr, Machine


class DSLValidationError(ValueError):
    pass


@dataclass(frozen=True)
class CommandResult:
    state: dict[str, Any]
    event: dict[str, Any]

    @property
    def advisory(self) -> dict[str, Any]:
        """Convenience only; callers must not treat this as a state receipt."""

        return {
            "processed": True,
            "changed": self.event["changed"],
            "outcomes": self.event["outcomes"],
        }


Algorithm = Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], None]


class Runtime:
    def __init__(self):
        self.algorithms: dict[tuple[str, int], Algorithm] = {}

    def register(self, name: str, version: int, implementation: Algorithm) -> None:
        self.algorithms[(name, version)] = implementation

    def initial_state(self, spec: Machine) -> dict[str, Any]:
        context = {"constant": spec.constants, "state": {}, "input": {}, "current": {}}
        result: dict[str, Any] = {}
        context["state"] = result
        for name, definition in spec.fields.items():
            result[name] = deepcopy(self.evaluate(definition.initial, context))
        return result

    def execute(
        self,
        spec: Machine,
        state: dict[str, Any],
        command_name: str,
        inputs: dict[str, Any],
        *,
        current: dict[str, Any] | None = None,
    ) -> CommandResult:
        if command_name not in spec.commands:
            raise DSLValidationError(f"unknown command {command_name!r}")
        command = spec.commands[command_name]
        self._validate_inputs(command, inputs, spec.constants)
        working = deepcopy(state)
        context = {
            "constant": spec.constants,
            # Every expression in one command observes the same pre-command
            # snapshot. Effects are committed to ``working`` atomically.
            "state": deepcopy(state),
            "input": inputs,
            "current": current or {},
        }
        if command.require is not None and not self.evaluate(command.require, context):
            return CommandResult(
                state=working,
                event={
                    "command": command_name,
                    "inputs": deepcopy(inputs),
                    "processed": True,
                    "changed": False,
                    "outcomes": [{"status": "requirement_not_met"}],
                },
            )

        before = deepcopy(working)
        outcomes = [self._apply(effect, working, context) for effect in command.effects]
        state_context = context | {"state": working}
        for field_name, definition in spec.fields.items():
            self._validate_type(
                field_name, working[field_name], definition.type, state_context
            )
        return CommandResult(
            state=working,
            event={
                "command": command_name,
                "inputs": deepcopy(inputs),
                "processed": True,
                "changed": working != before,
                "outcomes": outcomes,
            },
        )

    def render_view(
        self,
        spec: Machine,
        state: dict[str, Any],
        *,
        current: dict[str, Any] | None = None,
        closed: bool = False,
    ) -> dict[str, Any]:
        context = {
            "constant": spec.constants,
            "state": state,
            "input": {},
            "current": (current or {}) | {"closed": closed},
        }
        return {
            name: self.evaluate(value, context) for name, value in spec.view.items()
        }

    def close(self, spec: Machine, state: dict[str, Any]) -> dict[str, Any]:
        working = deepcopy(state)
        context = {
            "constant": spec.constants,
            "state": deepcopy(state),
            "input": {},
            "current": {"closed": True},
        }
        for effect in spec.close_effects:
            self._apply(effect, working, context)
        state_context = context | {"state": working}
        for field_name, definition in spec.fields.items():
            self._validate_type(
                field_name, working[field_name], definition.type, state_context
            )
        return working

    def complete(self, spec: Machine, state: dict[str, Any]) -> bool:
        if spec.complete_when is None:
            return False
        return bool(
            self.evaluate(
                spec.complete_when,
                {
                    "constant": spec.constants,
                    "state": state,
                    "input": {},
                    "current": {},
                },
            )
        )

    def evaluate(self, value: Any, context: dict[str, Any]) -> Any:
        if not isinstance(value, Expr):
            if isinstance(value, dict):
                return {
                    key: self.evaluate(item, context) for key, item in value.items()
                }
            if isinstance(value, (tuple, list)):
                return [self.evaluate(item, context) for item in value]
            return value

        if value.op == "map_items":
            collection = self.evaluate(value.args[0], context)
            result = {}
            for key, item in collection.items():
                nested = context | {
                    "local": context.get("local", {})
                    | {value.kwargs["key"]: key, value.kwargs["value"]: item}
                }
                result[self.evaluate(value.kwargs["key_expr"], nested)] = self.evaluate(
                    value.kwargs["value_expr"], nested
                )
            return result

        if value.op == "filter_items":
            collection = self.evaluate(value.args[0], context)
            return [
                item
                for item in collection
                if self.evaluate(
                    value.kwargs["predicate"],
                    context
                    | {
                        "local": context.get("local", {}) | {value.kwargs["item"]: item}
                    },
                )
            ]

        if value.op == "map_sequence":
            collection = self.evaluate(value.args[0], context)
            return [
                self.evaluate(
                    value.kwargs["value_expr"],
                    context
                    | {
                        "local": context.get("local", {}) | {value.kwargs["item"]: item}
                    },
                )
                for item in collection
            ]

        if value.op == "if":
            condition = self.evaluate(value.args[0], context)
            return self.evaluate(value.args[1] if condition else value.args[2], context)

        if value.op == "and":
            return bool(
                self.evaluate(value.args[0], context)
                and self.evaluate(value.args[1], context)
            )

        if value.op == "or":
            return bool(
                self.evaluate(value.args[0], context)
                or self.evaluate(value.args[1], context)
            )

        args = [self.evaluate(item, context) for item in value.args]
        kwargs = {
            key: self.evaluate(item, context) for key, item in value.kwargs.items()
        }
        op = value.op
        if op == "ref":
            namespace = value.kwargs["namespace"]
            name = value.kwargs["name"]
            result: Any = context[namespace]
            for part in name.split("."):
                if namespace == "current" and part not in result:
                    return self.evaluate(value.kwargs.get("default"), context)
                result = result[part]
            return result
        if op == "record":
            return kwargs
        if op == "map_of":
            return {pair[0]: pair[1] for pair in args}
        if op == "add":
            return args[0] + args[1]
        if op == "subtract":
            return args[0] - args[1]
        if op == "multiply":
            return args[0] * args[1]
        if op == "divide":
            return args[0] / args[1]
        if op == "absolute":
            return abs(args[0])
        if op == "equals":
            return args[0] == args[1]
        if op == "not_equals":
            return args[0] != args[1]
        if op == "less_than":
            return args[0] < args[1]
        if op == "at_most":
            return args[0] <= args[1]
        if op == "greater_than":
            return args[0] > args[1]
        if op == "at_least":
            return args[0] >= args[1]
        if op == "not":
            return not args[0]
        if op == "get":
            return args[0].get(args[1], args[2])
        if op == "at":
            return args[0][int(args[1])]
        if op == "values":
            return list(args[0].values())
        if op == "length":
            return len(args[0])
        if op == "contains":
            return args[1] in args[0]
        if op == "first":
            return args[0][0] if args[0] else args[1]
        if op == "drop_first":
            return args[0][1:]
        if op == "append_value":
            return [*args[0], args[1]]
        if op == "remove_value":
            return [item for item in args[0] if item != args[1]]
        if op == "put_value":
            return dict(args[0]) | {args[1]: args[2]}
        if op == "strip":
            return args[0].strip()
        if op == "casefold":
            return args[0].casefold()
        if op == "minimum":
            return min(args)
        if op == "concat":
            return "".join(str(item) for item in args)
        if op == "reduce":
            operation, collection = args[:2]
            if operation == "tail":
                return collection[-int(kwargs["count"]) :]
            if operation == "count_by":
                return dict(Counter(collection))
            if operation == "sum":
                return sum(collection)
            if operation == "mean":
                return sum(collection) / len(collection) if collection else None
            if operation == "median":
                ordered = sorted(collection)
                middle = len(ordered) // 2
                return (
                    None
                    if not ordered
                    else (
                        ordered[middle]
                        if len(ordered) % 2
                        else (ordered[middle - 1] + ordered[middle]) / 2
                    )
                )
            if operation == "max":
                return max(collection, default=None)
            if operation == "argmax":
                return max(
                    collection, key=lambda item: item[kwargs["field"]], default=None
                )
            if operation == "sort_records":
                result = list(collection)
                fields = list(kwargs["fields"])
                descending = list(kwargs.get("descending", [False] * len(fields)))
                for field_name, reverse in reversed(list(zip(fields, descending))):
                    result.sort(key=lambda item: item[field_name], reverse=reverse)
                return result
            if operation == "latest_by":
                result = {}
                for item in collection:
                    result[item[kwargs["field"]]] = item
                return result
            if operation == "count_equal":
                return sum(item == kwargs["value"] for item in collection)
            if operation == "increment_keys":
                result = dict(collection)
                for key in kwargs["keys"]:
                    if key not in result:
                        raise DSLValidationError(f"unknown counter key {key!r}")
                    result[key] += kwargs.get("amount", 1)
                return result
            if operation == "keys_min_distance":
                target = kwargs["target"]
                distances = {
                    key: abs(item - target) for key, item in collection.items()
                }
                closest = min(distances.values())
                return [
                    key
                    for key, distance in distances.items()
                    if abs(distance - closest) < kwargs.get("tolerance", 1e-9)
                ]
            if operation == "weighted_matrix_tally":
                totals: dict[str, float] = {}
                weights = kwargs["weights"]
                for ballot in collection:
                    for key, selection in ballot["votes"].items():
                        totals[key] = totals.get(key, 0) + weights[selection]
                return totals
            if operation == "ranked_ballot_results":
                ballots, candidates = collection, list(kwargs["candidates"])
                plurality = Counter(ballot[0] for ballot in ballots.values())
                borda = Counter()
                for ballot in ballots.values():
                    for index, candidate in enumerate(ballot):
                        borda[candidate] += len(candidates) - index - 1
                pairwise = {candidate: 0 for candidate in candidates}
                for left_index, left in enumerate(candidates):
                    for right in candidates[left_index + 1 :]:
                        left_votes = sum(
                            ballot.index(left) < ballot.index(right)
                            for ballot in ballots.values()
                        )
                        right_votes = len(ballots) - left_votes
                        if left_votes > right_votes:
                            pairwise[left] += 1
                        elif right_votes > left_votes:
                            pairwise[right] += 1

                def winner(scores):
                    return max(
                        candidates,
                        key=lambda candidate: (
                            scores[candidate],
                            -candidates.index(candidate),
                        ),
                    )

                return {
                    "plurality_scores": dict(plurality),
                    "plurality_winner": winner(plurality),
                    "borda_scores": dict(borda),
                    "borda_winner": winner(borda),
                    "condorcet_winner": next(
                        (
                            c
                            for c, wins in pairwise.items()
                            if wins == len(candidates) - 1
                        ),
                        None,
                    ),
                }
            if operation == "group_numeric_summary":
                groups: dict[Any, list[dict[str, Any]]] = {}
                for item in collection:
                    groups.setdefault(item[kwargs["group"]], []).append(item)
                result = {}
                for key, items in groups.items():
                    values = sorted(item[kwargs["value"]] for item in items)
                    middle = len(values) // 2
                    median = (
                        values[middle]
                        if len(values) % 2
                        else (values[middle - 1] + values[middle]) / 2
                    )
                    result[key] = {
                        "count": len(items),
                        "minimum": min(values),
                        "maximum": max(values),
                        "range": max(values) - min(values),
                        "median": median,
                    }
                return result
            if operation == "series_converged":
                summaries = collection
                keys = sorted(summaries)
                if len(keys) < kwargs["min_groups"]:
                    return False
                latest, previous = summaries[keys[-1]], summaries[keys[-2]]
                minimum_size = kwargs.get("min_group_size")
                if minimum_size is not None and (
                    latest["count"] < minimum_size or previous["count"] < minimum_size
                ):
                    return False
                return (
                    latest["range"] <= kwargs["range_threshold"]
                    and abs(latest["median"] - previous["median"])
                    <= kwargs["shift_threshold"]
                )
            raise DSLValidationError(f"unknown reducer {operation!r}")
        if op == "algorithm_view":
            name = args[0]
            if name == "lmsr_prices":
                q_yes, q_no, liquidity = args[1:]
                difference = max(-700, min(700, (q_no - q_yes) / liquidity))
                yes = 1 / (1 + math.exp(difference))
                return {"yes": yes, "no": 1 - yes}
            raise DSLValidationError(f"unknown algorithm view {name!r}")
        if op == "type":
            return value
        raise DSLValidationError(f"unknown expression operation {op!r}")

    def _apply(
        self,
        effect: Effect,
        working: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        condition = effect.options.get("when")
        if condition is not None and not self.evaluate(condition, context):
            return {
                "effect": effect.op,
                "target": effect.target,
                "status": "condition_false",
            }
        if effect.op == "algorithm":
            name = effect.options["name"]
            version = effect.options["version"]
            implementation = self.algorithms.get((name, version))
            if implementation is None:
                raise DSLValidationError(f"unregistered algorithm {name}@{version}")
            bindings = {
                key: self.evaluate(value, context)
                for key, value in effect.options["bindings"].items()
            }
            implementation(working, bindings, context["constant"])
            return {
                "effect": "algorithm",
                "name": name,
                "version": version,
                "status": "applied",
            }

        evaluated = [self.evaluate(value, context) for value in effect.args]
        if effect.op == "set":
            working[effect.target] = evaluated[0]
            return {"effect": "set", "target": effect.target, "status": "applied"}
        if effect.op == "set_once":
            if working[effect.target] is not None:
                return {
                    "effect": "set_once",
                    "target": effect.target,
                    "status": "unchanged",
                }
            working[effect.target] = evaluated[0]
            return {"effect": "set_once", "target": effect.target, "status": "applied"}
        if effect.op == "put":
            key, item = evaluated
            if effect.options.get("once") and key in working[effect.target]:
                return {"effect": "put", "target": effect.target, "status": "unchanged"}
            working[effect.target][key] = item
            return {"effect": "put", "target": effect.target, "status": "applied"}
        if effect.op == "append":
            working[effect.target].append(evaluated[0])
            return {"effect": "append", "target": effect.target, "status": "applied"}
        raise DSLValidationError(f"unknown effect {effect.op!r}")

    def _validate_inputs(
        self, command: Command, inputs: dict[str, Any], constants: dict[str, Any]
    ) -> None:
        missing = set(command.inputs) - inputs.keys()
        extra = inputs.keys() - set(command.inputs)
        if missing or extra:
            raise DSLValidationError(
                f"input mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
            )
        context = {"constant": constants, "state": {}, "input": inputs, "current": {}}
        for name, type_expr in command.inputs.items():
            self._validate_type(name, inputs[name], type_expr, context)

    def _validate_type(
        self, name: str, value: Any, type_expr: Expr, context: dict[str, Any]
    ) -> None:
        kind = type_expr.args[0]
        constraints = {
            key: self.evaluate(item, context) for key, item in type_expr.kwargs.items()
        }
        if kind == "any":
            return
        if kind == "optional" and value is None:
            return
        if kind == "optional":
            return self._validate_type(name, value, constraints["item"], context)
        if kind == "text" and not isinstance(value, str):
            raise DSLValidationError(f"{name} must be text")
        if kind == "boolean" and not isinstance(value, bool):
            raise DSLValidationError(f"{name} must be boolean")
        if kind == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DSLValidationError(f"{name} must be numerical")
            if (
                constraints.get("minimum") is not None
                and value < constraints["minimum"]
            ):
                raise DSLValidationError(f"{name} is below its minimum")
            if (
                constraints.get("maximum") is not None
                and value > constraints["maximum"]
            ):
                raise DSLValidationError(f"{name} is above its maximum")
        if kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise DSLValidationError(f"{name} must be an integer")
            if (
                constraints.get("minimum") is not None
                and value < constraints["minimum"]
            ):
                raise DSLValidationError(f"{name} is below its minimum")
            if (
                constraints.get("maximum") is not None
                and value > constraints["maximum"]
            ):
                raise DSLValidationError(f"{name} is above its maximum")
        if kind == "choice" and value not in constraints["options"]:
            raise DSLValidationError(
                f"{name} must be one of {constraints['options']!r}"
            )
        if kind == "rank" and (
            not isinstance(value, (list, tuple))
            or len(value) != len(constraints["options"])
            or set(value) != set(constraints["options"])
        ):
            raise DSLValidationError(
                f"{name} must rank every configured option exactly once"
            )
        if kind == "sequence":
            if not isinstance(value, (list, tuple)):
                raise DSLValidationError(f"{name} must be a sequence")
            for index, item in enumerate(value):
                self._validate_type(
                    f"{name}[{index}]", item, constraints["item"], context
                )
        if kind == "map":
            if not isinstance(value, dict):
                raise DSLValidationError(f"{name} must be a map")
            for key, item in value.items():
                self._validate_type(f"{name}.key", key, constraints["key"], context)
                self._validate_type(
                    f"{name}[{key!r}]", item, constraints["value"], context
                )


def lmsr_runtime() -> Runtime:
    runtime = Runtime()

    def cost(q_yes, q_no, liquidity):
        high = max(q_yes, q_no) / liquidity
        return liquidity * (
            high
            + math.log(
                math.exp(q_yes / liquidity - high) + math.exp(q_no / liquidity - high)
            )
        )

    def trade(state, inputs, constants):
        action, quantity = inputs["action"], float(inputs["quantity"])
        if action == "hold":
            return
        trader = inputs["trader"]
        field_name = "q_yes" if action == "buy_yes" else "q_no"
        before = cost(state["q_yes"], state["q_no"], constants["liquidity"])
        state[field_name] += quantity
        after = cost(state["q_yes"], state["q_no"], constants["liquidity"])
        paid = after - before
        portfolio = state["portfolios"].setdefault(
            trader,
            {"cash": float(constants["initial_cash"]), "yes": 0.0, "no": 0.0},
        )
        side = "yes" if action == "buy_yes" else "no"
        portfolio["cash"] -= paid
        portfolio[side] += quantity
        state["trades"].append(dict(inputs) | {"cost": paid})

    def settle(state, inputs, constants):
        if state["outcome"] is None:
            state["outcome"] = inputs["outcome"]
            winning_side = "yes" if inputs["outcome"] else "no"
            for portfolio in state["portfolios"].values():
                portfolio["settled_wealth"] = (
                    portfolio["cash"] + portfolio[winning_side]
                )

    runtime.register("lmsr_trade", 1, trade)
    runtime.register("lmsr_settle", 1, settle)
    return runtime


def mechanism_runtime() -> Runtime:
    """Runtime with reviewed, versioned iterative mechanism implementations."""

    runtime = Runtime()

    def serial_dictatorship(state, inputs, constants):
        latest = {}
        for index, request in enumerate(inputs["requests"]):
            latest[request["claimant"]] = (
                request.get("priority"),
                index,
                request["ranking"],
            )
        remaining = {item: inputs["capacity"] for item in inputs["items"]}
        assignments = {}
        ordered = sorted(
            latest.items(),
            key=lambda pair: (
                pair[1][0] is None,
                pair[1][0] if pair[1][0] is not None else pair[1][1],
                pair[1][1],
            ),
        )
        for claimant, (_, _, ranking) in ordered:
            for item in ranking:
                if remaining.get(item, 0) > 0:
                    assignments[claimant] = item
                    remaining[item] -= 1
                    break
        state["assignments"] = assignments

    runtime.register("serial_dictatorship", 1, serial_dictatorship)

    def deferred_acceptance(state, inputs, constants):
        latest = {}
        for request in inputs["requests"]:
            latest[request["student"]] = list(request["ranking"])
        rank = {
            institution: {student: index for index, student in enumerate(order)}
            for institution, order in inputs["priorities"].items()
        }
        held = {institution: [] for institution in inputs["capacities"]}
        next_choice = {student: 0 for student in latest}
        unmatched = sorted(latest)
        while unmatched:
            student = unmatched.pop(0)
            choice_index = next_choice[student]
            if choice_index >= len(latest[student]):
                continue
            institution = latest[student][choice_index]
            next_choice[student] += 1
            candidates = held[institution] + [student]
            candidates.sort(
                key=lambda name: (rank[institution].get(name, math.inf), name)
            )
            held[institution] = candidates[: inputs["capacities"][institution]]
            unmatched.extend(candidates[inputs["capacities"][institution] :])
        state["matches"] = {
            student: institution
            for institution, students in held.items()
            for student in students
        }
        state["institution_matches"] = held

    runtime.register("deferred_acceptance", 1, deferred_acceptance)

    def double_auction_submit(state, inputs, constants):
        trader, action = str(inputs["trader"]), str(inputs["action"])
        if trader not in state["accounts"]:
            raise DSLValidationError(f"unknown trader {trader!r}")
        open_orders = [
            o
            for o in state["orders"]
            if o["trader"] == trader and o["status"] == "open"
        ]
        if action == "cancel":
            for order in open_orders:
                order["status"] = "cancelled"
            return
        if action == "hold":
            return
        if open_orders:
            raise DSLValidationError(
                f"trader {trader!r} must cancel an open order before replacing it"
            )
        price = inputs["price"]
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price <= 0:
            raise DSLValidationError("order price must be positive")
        account = state["accounts"][trader]
        if action == "buy" and account["cash"] < price:
            raise DSLValidationError(f"trader {trader!r} has insufficient cash")
        if action == "sell" and account["inventory"] < 1:
            raise DSLValidationError(f"trader {trader!r} has insufficient inventory")
        order = {
            "id": f"O{len(state['orders']) + 1}",
            "trader": trader,
            "side": action,
            "price": float(price),
            "round": int(inputs["round"]),
            "status": "open",
            "interview": inputs.get("interview"),
            "time": len(state["orders"]) + 1,
        }
        state["orders"].append(order)
        opposite = "sell" if action == "buy" else "buy"
        compatible = [
            candidate
            for candidate in state["orders"]
            if candidate["status"] == "open"
            and candidate["side"] == opposite
            and (
                candidate["price"] <= order["price"]
                if action == "buy"
                else candidate["price"] >= order["price"]
            )
        ]
        if not compatible:
            return
        resting = sorted(
            compatible,
            key=lambda candidate: (
                candidate["price"] if action == "buy" else -candidate["price"],
                candidate["time"],
            ),
        )[0]
        buyer_order, seller_order = (
            (order, resting) if action == "buy" else (resting, order)
        )
        trade_price = resting["price"]
        buyer, seller = (
            state["accounts"][buyer_order["trader"]],
            state["accounts"][seller_order["trader"]],
        )
        if buyer["cash"] < trade_price or seller["inventory"] < 1:
            raise DSLValidationError("resting order is no longer collateralized")
        buyer["cash"] -= trade_price
        buyer["inventory"] += 1
        seller["cash"] += trade_price
        seller["inventory"] -= 1
        buyer_order["status"] = seller_order["status"] = "filled"
        state["trades"].append(
            {
                "buyer": buyer_order["trader"],
                "seller": seller_order["trader"],
                "price": trade_price,
                "round": int(inputs["round"]),
                "maker_order": resting["id"],
                "taker_order": order["id"],
            }
        )

    def double_auction_close(state, inputs, constants):
        for order in state["orders"]:
            if order["status"] == "open":
                order["status"] = "expired"

    runtime.register("double_auction_submit", 1, double_auction_submit)
    runtime.register("double_auction_close", 1, double_auction_close)
    return runtime


def default_runtime() -> Runtime:
    """Return the reviewed capability set available to standard backends."""

    runtime = mechanism_runtime()
    runtime.algorithms.update(lmsr_runtime().algorithms)
    return runtime
