"""Scope checking and conservative record-shape analysis for Machine authoring.

This is not a complete type checker: unknown or dynamic shapes stay unknown.
Only references and record members that are provably invalid are rejected.
"""

from dataclasses import fields, is_dataclass
from typing import Any

from .dsl import Effect, Expr, Machine, T
from .exceptions import MachineValidationError


def walk_paths(value: Any, path: str = "$"):
    """Walk the authoring tree with locations in its serialized structure."""
    yield path, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk_paths(item, f"{path}[{key!r}]")
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            yield from walk_paths(item, f"{path}[{index}]")
    elif is_dataclass(value):
        for member in fields(value):
            yield from walk_paths(getattr(value, member.name), f"{path}.{member.name}")


def _kind(shape):
    return shape.args[0]


def _join(shapes):
    if not shapes:
        return T.any()
    first = shapes[0]
    return first if all(s.to_dict() == first.to_dict() for s in shapes[1:]) else T.any()


def _literal_shape(value):
    if isinstance(value, bool):
        return T.boolean()
    if isinstance(value, str):
        return T.text()
    if isinstance(value, int):
        return T.integer()
    if isinstance(value, float):
        return T.number()
    if isinstance(value, dict):
        # A literal dictionary does not declare that its keys are closed.
        return T.map(T.text(), _join([_literal_shape(v) for v in value.values()]))
    if isinstance(value, (list, tuple)):
        return T.sequence(_join([_literal_shape(v) for v in value]))
    return T.any()


class _References:
    def __init__(self, machine):
        self.machine = machine
        self.state_types = {k: v.type for k, v in machine.fields.items()}
        self.constant_types = {
            k: _literal_shape(v) for k, v in machine.constants.items()
        }

    def fail(self, path, reason):
        raise MachineValidationError(self.machine.name, path, reason)

    def member(self, shape, key, path):
        while _kind(shape) == "optional":
            shape = shape.kwargs["item"]
        if _kind(shape) == "record":
            members = shape.kwargs["fields"]
            if key in members:
                return members[key]
            if not shape.kwargs["allow_extra"]:
                self.fail(
                    path,
                    f"unknown record field {key!r}; declared fields: {sorted(members)}",
                )
        if _kind(shape) == "map":
            return shape.kwargs["value"]
        return T.any()

    def bind(self, expr, names, path):
        values = [expr.kwargs[key] for key in names]
        if any(not isinstance(name, str) or not name.isidentifier() for name in values):
            self.fail(path, f"{expr.op} requires identifier binding names")
        if len(set(values)) != len(values):
            self.fail(path, f"{expr.op} requires distinct binding names")
        return values

    def expression(self, value, path, locals_, inputs):
        if isinstance(value, dict):
            shapes = [
                self.expression(v, f"{path}[{k!r}]", locals_, inputs)
                for k, v in value.items()
            ]
            return T.map(T.text(), _join(shapes))
        if isinstance(value, (tuple, list)):
            return T.sequence(
                _join(
                    [
                        self.expression(v, f"{path}[{i}]", locals_, inputs)
                        for i, v in enumerate(value)
                    ]
                )
            )
        if isinstance(value, Effect):
            self.expression(value.args, path + ".args", locals_, inputs)
            self.expression(value.options, path + ".options", locals_, inputs)
            return T.any()
        if not isinstance(value, Expr):
            return _literal_shape(value)

        op = value.op
        if op == "ref":
            namespace, name = value.kwargs["namespace"], value.kwargs["name"]
            if (
                not isinstance(name, str)
                or not name
                or any(not part for part in name.split("."))
            ):
                self.fail(path, "reference name must be a nonempty dotted path")
            root, *members = name.split(".")
            spaces = {
                "state": self.state_types,
                "constant": self.constant_types,
                "input": inputs,
                "local": locals_,
            }
            if namespace == "current":
                shape = T.any()  # The host supplies this schema.
            elif namespace not in spaces:
                self.fail(path, f"unknown reference namespace {namespace!r}")
            elif root not in spaces[namespace]:
                self.fail(path, f"unbound {namespace} reference {root!r}")
            else:
                shape = spaces[namespace][root]
                for member in members:
                    shape = self.member(shape, member, path)
            if "default" in value.kwargs:
                self.expression(
                    value.kwargs["default"],
                    path + ".kwargs['default']",
                    locals_,
                    inputs,
                )
            return shape

        args = [
            self.expression(arg, f"{path}.args[{i}]", locals_, inputs)
            for i, arg in enumerate(value.args)
        ]
        if op in {
            "let",
            "fold",
            "iterate",
            "map_sequence",
            "map_items",
            "filter_items",
        }:
            if op == "let":
                (name,) = self.bind(value, ("name",), path)
                return self.expression(
                    value.kwargs["body"],
                    path + ".kwargs['body']",
                    locals_ | {name: args[0]},
                    inputs,
                )
            if op == "fold":
                # A body may change accumulator shape between visits. Checking
                # invariants needs fixed-point analysis; do not assume the seed
                # type holds for every iteration.
                item, accumulator = self.bind(value, ("item", "accumulator"), path)
                item_shape = (
                    args[0].kwargs["item"] if _kind(args[0]) == "sequence" else T.any()
                )
                body = self.expression(
                    value.kwargs["body"],
                    path + ".kwargs['body']",
                    locals_ | {item: item_shape, accumulator: T.any()},
                    inputs,
                )
                return _join([args[1], body])
            if op == "iterate":
                (name,) = self.bind(value, ("state",), path)
                self.expression(
                    value.kwargs["max_steps"],
                    path + ".kwargs['max_steps']",
                    locals_,
                    inputs,
                )
                nested = locals_ | {name: T.any()}
                self.expression(
                    value.kwargs["until"], path + ".kwargs['until']", nested, inputs
                )
                body = self.expression(
                    value.kwargs["step"], path + ".kwargs['step']", nested, inputs
                )
                return _join([args[0], body])
            if op == "map_items":
                key, item = self.bind(value, ("key", "value"), path)
                shape = args[0]
                if _kind(shape) == "map":
                    key_shape, item_shape = shape.kwargs["key"], shape.kwargs["value"]
                elif _kind(shape) == "record":
                    key_shape, item_shape = T.text(), _join(
                        list(shape.kwargs["fields"].values())
                    )
                else:
                    key_shape, item_shape = T.any(), T.any()
                nested = locals_ | {key: key_shape, item: item_shape}
                k = self.expression(
                    value.kwargs["key_expr"],
                    path + ".kwargs['key_expr']",
                    nested,
                    inputs,
                )
                v = self.expression(
                    value.kwargs["value_expr"],
                    path + ".kwargs['value_expr']",
                    nested,
                    inputs,
                )
                return T.map(k if _kind(k) in {"text", "choice"} else T.any(), v)
            (item,) = self.bind(value, ("item",), path)
            shape = args[0].kwargs["item"] if _kind(args[0]) == "sequence" else T.any()
            body_key = "predicate" if op == "filter_items" else "value_expr"
            body = self.expression(
                value.kwargs[body_key],
                f"{path}.kwargs[{body_key!r}]",
                locals_ | {item: shape},
                inputs,
            )
            return args[0] if op == "filter_items" else T.sequence(body)

        kwargs = {
            k: self.expression(v, f"{path}.kwargs[{k!r}]", locals_, inputs)
            for k, v in value.kwargs.items()
        }
        if op == "type":
            return value
        if op == "record":
            return T.record(kwargs)
        if op == "get":
            return (
                self.member(args[0], value.args[1], path)
                if isinstance(value.args[1], str)
                else T.any()
            )
        if op in {"first", "at"}:
            return args[0].kwargs["item"] if _kind(args[0]) == "sequence" else T.any()
        if op in {"take", "drop_first", "remove_value"}:
            return args[0]
        if op == "append_value":
            return (
                T.sequence(_join([args[0].kwargs["item"], args[1]]))
                if _kind(args[0]) == "sequence"
                else T.any()
            )
        if op == "put_value":
            if _kind(args[0]) == "record" and isinstance(value.args[1], str):
                return T.record(
                    args[0].kwargs["fields"] | {value.args[1]: args[2]},
                    allow_extra=args[0].kwargs["allow_extra"],
                )
            return T.map()
        if op == "values":
            if _kind(args[0]) == "record":
                return T.sequence(_join(list(args[0].kwargs["fields"].values())))
            return (
                T.sequence(args[0].kwargs["value"])
                if _kind(args[0]) == "map"
                else T.any()
            )
        if op == "if":
            return _join(args[1:])
        return T.any()


def validate_references(machine: Machine) -> None:
    checker = _References(machine)
    for name, definition in machine.fields.items():
        checker.expression(definition.initial, f"$.fields[{name!r}].initial", {}, {})
        checker.expression(definition.type, f"$.fields[{name!r}].type", {}, {})
    for name, command in machine.commands.items():
        path = f"$.commands[{name!r}]"
        checker.expression(command.inputs, path + ".inputs", {}, {})
        checker.expression(command.require, path + ".require", {}, command.inputs)
        checker.expression(command.effects, path + ".effects", {}, command.inputs)
    checker.expression(machine.view, "$.view", {}, {})
    checker.expression(machine.complete_when, "$.complete_when", {}, {})
    checker.expression(machine.close_effects, "$.close_effects", {}, {})
