"""Configured state-machine primitive for shared economic games.

This is an example-level prototype: the engine is generic, while named games are
plain configurations composed from fields, actions, expressions, and settlement.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from edsl.sharedstate.exceptions import SharedStateAuthoringError
from edsl.sharedstate.primitives import SharedPrimitive
from edsl.sharedstate.refs import AnswerRef
from edsl.sharedstate.steps import WriteStep


@dataclass(frozen=True)
class Field:
    kind: str
    initial: Any = None
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[Any, ...] = ()

    @classmethod
    def number(cls, *, minimum=None, maximum=None, initial=None):
        return cls("number", initial, minimum, maximum)

    @classmethod
    def choice(cls, choices, *, initial=None):
        return cls("choice", initial, choices=tuple(choices))

    def validate(self, value, name):
        if self.kind == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise SharedStateAuthoringError(f"{name} must be a number")
            if self.minimum is not None and value < self.minimum:
                raise SharedStateAuthoringError(f"{name} must be at least {self.minimum:g}")
            if self.maximum is not None and value > self.maximum:
                raise SharedStateAuthoringError(f"{name} must be at most {self.maximum:g}")
            return float(value)
        if self.kind == "choice":
            normalized = str(value).lower()
            if normalized not in self.choices:
                raise SharedStateAuthoringError(
                    f"{name} must be one of {', '.join(map(str, self.choices))}"
                )
            return normalized
        raise SharedStateAuthoringError(f"unknown field kind '{self.kind}'")


@dataclass(frozen=True)
class Action:
    actor: str
    writes: str
    requires: tuple[str, ...] = ()
    write_once: bool = True


@dataclass(frozen=True)
class Ref:
    name: str


@dataclass(frozen=True)
class Subtract:
    left: Any
    right: Any


@dataclass(frozen=True)
class Equals:
    left: Any
    right: Any


@dataclass(frozen=True)
class Settlement:
    when: Equals
    payoffs: Mapping[str, Any]
    otherwise: float = 0


def _evaluate(expression, values):
    if isinstance(expression, Ref):
        return values[expression.name]
    if isinstance(expression, Subtract):
        return _evaluate(expression.left, values) - _evaluate(expression.right, values)
    if isinstance(expression, Equals):
        return _evaluate(expression.left, values) == _evaluate(expression.right, values)
    return expression


def _expression_to_dict(expression):
    if isinstance(expression, Ref):
        return {"op": "ref", "name": expression.name}
    if isinstance(expression, Subtract):
        return {
            "op": "subtract",
            "left": _expression_to_dict(expression.left),
            "right": _expression_to_dict(expression.right),
        }
    if isinstance(expression, Equals):
        return {
            "op": "equals",
            "left": _expression_to_dict(expression.left),
            "right": _expression_to_dict(expression.right),
        }
    return {"op": "literal", "value": expression}


def _expression_from_dict(data):
    if data["op"] == "ref":
        return Ref(data["name"])
    if data["op"] == "subtract":
        return Subtract(
            _expression_from_dict(data["left"]),
            _expression_from_dict(data["right"]),
        )
    if data["op"] == "equals":
        return Equals(
            _expression_from_dict(data["left"]),
            _expression_from_dict(data["right"]),
        )
    if data["op"] == "literal":
        return data["value"]
    raise SharedStateAuthoringError(f"unknown expression operation '{data['op']}'")


class ConfiguredSharedGame(SharedPrimitive):
    """Generic event-sourced game assembled entirely from configuration."""

    def __init__(
        self,
        *,
        constants: Mapping[str, Any] | None = None,
        fields: Mapping[str, Field],
        actions: Mapping[str, Action],
        terminal_when_set: str,
        settlement: Settlement,
    ):
        self.constants = dict(constants or {})
        self.fields = dict(fields)
        self.actions = dict(actions)
        self.terminal_when_set = terminal_when_set
        self.settlement = settlement
        if terminal_when_set not in self.fields:
            raise SharedStateAuthoringError(
                f"terminal field '{terminal_when_set}' is not configured"
            )
        for name, action in self.actions.items():
            if action.writes not in self.fields:
                raise SharedStateAuthoringError(
                    f"action '{name}' writes unknown field '{action.writes}'"
                )
            missing = set(action.requires) - self.fields.keys()
            if missing:
                raise SharedStateAuthoringError(
                    f"action '{name}' requires unknown fields: {sorted(missing)}"
                )

    @property
    def valid_operations(self):
        return set(self.actions)

    def bind(self, action_name, question, *, player="{{ agent.name }}"):
        """Bind a question answer to one configured state transition."""
        if action_name not in self.actions:
            raise SharedStateAuthoringError(f"unknown action '{action_name}'")
        action = self.actions[action_name]
        return WriteStep(
            self,
            action_name,
            {
                "player": player,
                "role": action.actor,
                action.writes: AnswerRef(question.question_name),
            },
        )

    def initial(self):
        return {
            "values": {name: field.initial for name, field in self.fields.items()},
            "actors": {action.actor: None for action in self.actions.values()},
        }

    def apply(self, state, op, args, interview_id):
        if op not in self.actions:
            raise SharedStateAuthoringError(f"unknown action '{op}'")
        action = self.actions[op]
        if str(args.get("role")) != action.actor:
            raise SharedStateAuthoringError(
                f"action '{op}' requires role '{action.actor}'"
            )
        missing = [name for name in action.requires if state["values"][name] is None]
        if missing:
            raise SharedStateAuthoringError(
                f"action '{op}' requires completed fields: {', '.join(missing)}"
            )
        if action.write_once and state["values"][action.writes] is not None:
            raise SharedStateAuthoringError(
                f"field '{action.writes}' has already been written"
            )
        state["values"][action.writes] = self.fields[action.writes].validate(
            args[action.writes], action.writes
        )
        state["actors"][action.actor] = str(args["player"])
        return state

    def terminal(self, state):
        values = state.get("values", state)
        return values[self.terminal_when_set] is not None

    def view(self, state, closed, context=None):
        values = self.constants | state["values"]
        settled = self.terminal(state)
        condition = settled and _evaluate(self.settlement.when, values)
        payoffs = None
        if settled:
            payoffs = {
                state["actors"][role]: (
                    _evaluate(expression, values) if condition else self.settlement.otherwise
                )
                for role, expression in self.settlement.payoffs.items()
            }
        return {
            **values,
            **state["actors"],
            "terminal": settled,
            "payoffs": payoffs,
        }

    def to_dict(self):
        return {
            "type": "configured_game",
            "constants": self.constants,
            "fields": {
                name: {
                    "kind": field.kind,
                    "initial": field.initial,
                    "minimum": field.minimum,
                    "maximum": field.maximum,
                    "choices": list(field.choices),
                }
                for name, field in self.fields.items()
            },
            "actions": {
                name: {
                    "actor": action.actor,
                    "writes": action.writes,
                    "requires": list(action.requires),
                    "write_once": action.write_once,
                }
                for name, action in self.actions.items()
            },
            "terminal_when_set": self.terminal_when_set,
            "settlement": {
                "when": _expression_to_dict(self.settlement.when),
                "payoffs": {
                    role: _expression_to_dict(expression)
                    for role, expression in self.settlement.payoffs.items()
                },
                "otherwise": self.settlement.otherwise,
            },
        }

    @classmethod
    def from_dict(cls, data):
        settlement = data["settlement"]
        return cls(
            constants=data.get("constants", {}),
            fields={
                name: Field(
                    kind=config["kind"],
                    initial=config.get("initial"),
                    minimum=config.get("minimum"),
                    maximum=config.get("maximum"),
                    choices=tuple(config.get("choices", ())),
                )
                for name, config in data["fields"].items()
            },
            actions={
                name: Action(
                    actor=config["actor"],
                    writes=config["writes"],
                    requires=tuple(config.get("requires", ())),
                    write_once=config.get("write_once", True),
                )
                for name, config in data["actions"].items()
            },
            terminal_when_set=data["terminal_when_set"],
            settlement=Settlement(
                when=_expression_from_dict(settlement["when"]),
                payoffs={
                    role: _expression_from_dict(expression)
                    for role, expression in settlement["payoffs"].items()
                },
                otherwise=settlement.get("otherwise", 0),
            ),
        )
