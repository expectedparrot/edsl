"""Serializable definitions for user-authored shared-state machines."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field as dc_field, fields
import json
from typing import Any


def encode(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(item) for item in value]
    return value


@dataclass(frozen=True)
class Expr:
    op: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"op": self.op, "args": encode(self.args), "kwargs": encode(self.kwargs)}

    def _binary(self, op: str, other: Any) -> "Expr":
        return Expr(op, (self, other))

    def __add__(self, other: Any) -> "Expr":
        return self._binary("add", other)

    def __sub__(self, other: Any) -> "Expr":
        return self._binary("subtract", other)

    def __mul__(self, other: Any) -> "Expr":
        return self._binary("multiply", other)

    def __truediv__(self, other: Any) -> "Expr":
        return self._binary("divide", other)

    def __eq__(self, other: Any) -> "Expr":
        return self._binary("equals", other)  # type: ignore[override]

    def __ne__(self, other: Any) -> "Expr":
        return self._binary("not_equals", other)  # type: ignore[override]

    def __lt__(self, other: Any) -> "Expr":
        return self._binary("less_than", other)

    def __le__(self, other: Any) -> "Expr":
        return self._binary("at_most", other)

    def __gt__(self, other: Any) -> "Expr":
        return self._binary("greater_than", other)

    def __ge__(self, other: Any) -> "Expr":
        return self._binary("at_least", other)

    def __and__(self, other: Any) -> "Expr":
        return self._binary("and", other)

    def __or__(self, other: Any) -> "Expr":
        return self._binary("or", other)

    def __invert__(self) -> "Expr":
        return Expr("not", (self,))

    def get(self, key: Any, default: Any = None) -> "Expr":
        return Expr("get", (self, key, default))

    def at(self, index: Any) -> "Expr":
        return Expr("at", (self, index))

    def values(self) -> "Expr":
        return Expr("values", (self,))

    def length(self) -> "Expr":
        return Expr("length", (self,))

    def contains(self, item: Any) -> "Expr":
        return Expr("contains", (self, item))

    def first(self, default: Any = None) -> "Expr":
        return Expr("first", (self, default))

    def drop_first(self) -> "Expr":
        return Expr("drop_first", (self,))

    def appended(self, item: Any) -> "Expr":
        return Expr("append_value", (self, item))

    def removed(self, item: Any) -> "Expr":
        return Expr("remove_value", (self, item))

    def with_item(self, key: Any, item: Any) -> "Expr":
        return Expr("put_value", (self, key, item))

    def stripped(self) -> "Expr":
        return Expr("strip", (self,))

    def casefolded(self) -> "Expr":
        return Expr("casefold", (self,))


def expr(op: str, *args: Any, **kwargs: Any) -> Expr:
    return Expr(op, args, kwargs)


def ref(namespace: str, name: str) -> Expr:
    return expr("ref", namespace=namespace, name=name)


def field(name: str) -> Expr:
    return ref("state", name)


def input_(name: str) -> Expr:
    return ref("input", name)


def constant(name: str) -> Expr:
    return ref("constant", name)


def current(path: str, default: Any = None) -> Expr:
    return expr("ref", namespace="current", name=path, default=default)


def local(name: str) -> Expr:
    return ref("local", name)


def record(**values: Any) -> Expr:
    return expr("record", **values)


def map_of(*pairs: tuple[Any, Any]) -> Expr:
    return expr("map_of", *pairs)


def choose(condition: Any, yes: Any, no: Any) -> Expr:
    return expr("if", condition, yes, no)


def reduce_(operation: str, collection: Any, **kwargs: Any) -> Expr:
    return expr("reduce", operation, collection, **kwargs)


def map_items(
    collection: Any, *, key: str, value: str, key_expr: Any, value_expr: Any
) -> Expr:
    return expr(
        "map_items",
        collection,
        key=key,
        value=value,
        key_expr=key_expr,
        value_expr=value_expr,
    )


def filter_items(collection: Any, *, item: str, predicate: Any) -> Expr:
    return expr("filter_items", collection, item=item, predicate=predicate)


def map_sequence(collection: Any, *, item: str, value_expr: Any) -> Expr:
    return expr("map_sequence", collection, item=item, value_expr=value_expr)


class T:
    @staticmethod
    def any() -> Expr:
        return expr("type", "any")

    @staticmethod
    def boolean() -> Expr:
        return expr("type", "boolean")

    @staticmethod
    def text() -> Expr:
        return expr("type", "text")

    @staticmethod
    def integer(*, minimum: Any = None, maximum: Any = None) -> Expr:
        return expr("type", "integer", minimum=minimum, maximum=maximum)

    @staticmethod
    def number(*, minimum: Any = None, maximum: Any = None) -> Expr:
        return expr("type", "number", minimum=minimum, maximum=maximum)

    @staticmethod
    def choice(options: Any) -> Expr:
        return expr("type", "choice", options=options)

    @staticmethod
    def rank(options: Any) -> Expr:
        return expr("type", "rank", options=options)

    @staticmethod
    def optional(item: Expr) -> Expr:
        return expr("type", "optional", item=item)

    @staticmethod
    def sequence(item: Expr | None = None) -> Expr:
        return expr("type", "sequence", item=item or T.any())

    @staticmethod
    def map(key: Expr | None = None, value: Expr | None = None) -> Expr:
        return expr("type", "map", key=key or T.text(), value=value or T.any())


@dataclass(frozen=True)
class StateField:
    type: Expr
    initial: Any

    def to_dict(self) -> dict[str, Any]:
        return encode(asdict(self))


def state_field(type_: Expr, initial: Any) -> StateField:
    return StateField(type_, initial)


@dataclass(frozen=True)
class Effect:
    op: str
    target: str
    args: tuple[Any, ...]
    options: dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return encode(asdict(self))


def set_(target: str, value: Any) -> Effect:
    return Effect("set", target, (value,))


def set_once(target: str, value: Any) -> Effect:
    return Effect("set_once", target, (value,))


def put(target: str, key: Any, value: Any, *, once: bool = False) -> Effect:
    return Effect("put", target, (key, value), {"once": once})


def append(target: str, value: Any) -> Effect:
    return Effect("append", target, (value,))


def algorithm(name: str, **bindings: Any) -> Effect:
    return Effect(
        "algorithm", "", (), {"name": name, "version": 1, "bindings": bindings}
    )


def when(condition: Expr, effect: Effect) -> Effect:
    return Effect(
        effect.op, effect.target, effect.args, effect.options | {"when": condition}
    )


@dataclass(frozen=True)
class Command:
    inputs: dict[str, Expr]
    effects: tuple[Effect, ...]
    require: Expr | None = None
    timing: str = "after_answer"

    def to_dict(self) -> dict[str, Any]:
        return encode(asdict(self))


@dataclass(frozen=True)
class Machine:
    name: str
    constants: dict[str, Any]
    fields: dict[str, StateField]
    commands: dict[str, Command]
    view: dict[str, Expr]
    complete_when: Expr | None = None
    close_effects: tuple[Effect, ...] = ()
    algorithms: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return encode(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Machine":
        constants = decode(data["constants"])
        state_fields = {
            name: StateField(decode(definition["type"]), decode(definition["initial"]))
            for name, definition in data["fields"].items()
        }
        commands = {}
        for name, definition in data["commands"].items():
            commands[name] = Command(
                inputs={
                    key: decode(item) for key, item in definition["inputs"].items()
                },
                effects=tuple(
                    Effect(
                        item["op"],
                        item["target"],
                        tuple(decode(item["args"])),
                        decode(item["options"]),
                    )
                    for item in definition["effects"]
                ),
                require=decode(definition["require"]),
                timing=definition["timing"],
            )
        return cls(
            name=data["name"],
            constants=constants,
            fields=state_fields,
            commands=commands,
            view={name: decode(item) for name, item in data["view"].items()},
            complete_when=decode(data["complete_when"]),
            close_effects=tuple(
                Effect(
                    item["op"],
                    item["target"],
                    tuple(decode(item["args"])),
                    decode(item["options"]),
                )
                for item in data.get("close_effects", [])
            ),
            algorithms=tuple(data["algorithms"]),
        )

    @classmethod
    def from_json(cls, payload: str) -> "Machine":
        return cls.from_dict(json.loads(payload))

    def validate(self) -> None:
        from .dsl_runtime import DSLValidationError, Runtime

        allowed_ops = {
            "absolute",
            "add",
            "algorithm_view",
            "and",
            "append_value",
            "at",
            "at_least",
            "at_most",
            "casefold",
            "concat",
            "contains",
            "divide",
            "drop_first",
            "equals",
            "filter_items",
            "first",
            "get",
            "greater_than",
            "if",
            "less_than",
            "length",
            "map_items",
            "map_of",
            "map_sequence",
            "minimum",
            "multiply",
            "not",
            "not_equals",
            "or",
            "put_value",
            "record",
            "reduce",
            "ref",
            "remove_value",
            "strip",
            "subtract",
            "type",
            "values",
        }
        namespaces = {"state", "input", "constant", "current", "local"}
        declared_algorithms = set(self.algorithms)
        for item in walk(self):
            if isinstance(item, Expr) and item.op not in allowed_ops:
                raise ValueError(f"{self.name} uses unknown expression {item.op!r}")
            if isinstance(item, Expr) and item.op == "algorithm_view":
                capability = f"{item.args[0]}@{item.kwargs.get('version', 1)}"
                if capability not in declared_algorithms:
                    raise ValueError(
                        f"{self.name} uses undeclared algorithm {capability!r}"
                    )
        for command_name, command in self.commands.items():
            for effect in command.effects:
                if effect.op != "algorithm" and effect.target not in self.fields:
                    raise ValueError(
                        f"{self.name}.{command_name} targets unknown field {effect.target!r}"
                    )
                if effect.op == "algorithm":
                    algorithm_name = effect.options.get("name")
                    capability = f"{algorithm_name}@{effect.options.get('version', 1)}"
                    if capability not in declared_algorithms:
                        raise ValueError(
                            f"{self.name}.{command_name} uses undeclared algorithm "
                            f"{capability!r}"
                        )
            for item in walk(command):
                if not isinstance(item, Expr):
                    continue
                if item.op not in allowed_ops:
                    raise ValueError(
                        f"{self.name}.{command_name} uses unknown expression {item.op!r}"
                    )
                if item.op == "ref":
                    namespace, name = item.kwargs.get("namespace"), item.kwargs.get(
                        "name"
                    )
                    if namespace not in namespaces:
                        raise ValueError(f"unknown reference namespace {namespace!r}")
                    if namespace == "input" and name not in command.inputs:
                        raise ValueError(
                            f"{self.name}.{command_name} references undeclared input {name!r}"
                        )
                    if namespace == "state" and name.split(".")[0] not in self.fields:
                        raise ValueError(
                            f"{self.name}.{command_name} references unknown field {name!r}"
                        )
                    if (
                        namespace == "constant"
                        and name.split(".")[0] not in self.constants
                    ):
                        raise ValueError(
                            f"{self.name}.{command_name} references unknown constant {name!r}"
                        )
        for effect in self.close_effects:
            if effect.op != "algorithm" and effect.target not in self.fields:
                raise ValueError(
                    f"{self.name}.close targets unknown field {effect.target!r}"
                )
            if effect.op == "algorithm":
                capability = (
                    f"{effect.options.get('name')}@{effect.options.get('version', 1)}"
                )
                if capability not in declared_algorithms:
                    raise ValueError(
                        f"{self.name}.close uses undeclared algorithm {capability!r}"
                    )
        runtime = Runtime()
        try:
            initial = runtime.initial_state(self)
            type_context = {
                "constant": self.constants,
                "state": initial,
                "input": {},
                "current": {},
            }
            for name, definition in self.fields.items():
                runtime._validate_type(
                    name, initial[name], definition.type, type_context
                )
            runtime.render_view(self, initial)
        except (DSLValidationError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid {self.name} definition: {exc}") from exc
        try:
            self.to_json()
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{self.name} contains a non-serializable value") from exc


def walk(value: Any):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from walk(item)
    elif hasattr(value, "__dataclass_fields__"):
        for item in fields(value):
            yield from walk(getattr(value, item.name))


def decode(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(decode(item) for item in value)
    if isinstance(value, dict):
        if set(value) >= {"op", "args", "kwargs"} and "target" not in value:
            return Expr(
                value["op"],
                tuple(decode(value["args"])),
                {key: decode(item) for key, item in value["kwargs"].items()},
            )
        return {key: decode(item) for key, item in value.items()}
    return value
