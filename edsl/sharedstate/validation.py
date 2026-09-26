"""Conservative scope, operand, record-shape and loop-contract analysis.

Unknown shapes and value-dependent constraints remain runtime checked. This
implements a gradual subset of the formal type rules, not complete inference.
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
    """Widen compatible branches without inventing guarantees for mixed values."""
    if not shapes:
        return T.any()
    result = shapes[0]
    for other in shapes[1:]:
        left, right = _kind(result), _kind(other)
        if result.to_dict() == other.to_dict():
            continue
        if {left, right} <= {"integer", "number"}:
            result = T.number()
        elif left == right == "sequence":
            result = T.sequence(_join([result.kwargs["item"], other.kwargs["item"]]))
        elif (
            left == right == "record"
            and result.kwargs["fields"].keys() == other.kwargs["fields"].keys()
        ):
            result = T.record(
                {
                    k: _join([v, other.kwargs["fields"][k]])
                    for k, v in result.kwargs["fields"].items()
                },
                allow_extra=result.kwargs["allow_extra"] or other.kwargs["allow_extra"],
            )
        elif left == right == "map":
            result = T.map(
                _join([result.kwargs["key"], other.kwargs["key"]]),
                _join([result.kwargs["value"], other.kwargs["value"]]),
            )
        else:
            result = T.any()
    return result


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

    def expect(self, shape, kinds, path, operation):
        # Optional values and choice domains need flow/value analysis. They and
        # unknown shapes stay runtime-checked rather than rejecting valid guards.
        kind = _kind(shape)
        if kind not in kinds | {"any", "optional", "choice"}:
            self.fail(
                path, f"{operation} requires {' or '.join(sorted(kinds))}; got {kind}"
            )

    def compatible(self, actual, expected, path):
        kind, target = _kind(actual), _kind(expected)
        if kind in {"any", "choice", "optional"} or target == "any":
            return
        if target == "optional":
            return self.compatible(actual, expected.kwargs["item"], path)
        if kind == "record" and target == "record":
            members, required = actual.kwargs["fields"], expected.kwargs["fields"]
            if required.keys() - members.keys() or (
                not expected.kwargs["allow_extra"] and members.keys() - required.keys()
            ):
                self.fail(
                    path, "accumulator record fields do not match declared invariant"
                )
            for name in required.keys() & members.keys():
                self.compatible(members[name], required[name], path + f".{name}")
        elif kind == target == "sequence":
            self.compatible(actual.kwargs["item"], expected.kwargs["item"], path)
        elif kind == target == "map":
            self.compatible(actual.kwargs["key"], expected.kwargs["key"], path)
            self.compatible(actual.kwargs["value"], expected.kwargs["value"], path)
        elif kind == "map" and target == "record":
            return  # Literal dictionaries have open shapes; validate at runtime.
        elif kind != target and not (kind == "integer" and target == "number"):
            self.fail(path, f"accumulator invariant requires {target}; got {kind}")

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
            if value.op == "assert":
                condition = self.expression(
                    value.args[0], path + ".args[0]", locals_, inputs
                )
                self.expect(condition, {"boolean"}, path + ".args[0]", "assert")
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
                self.expect(args[0], {"sequence", "rank"}, path, op)
                invariant = value.kwargs.get("accumulator_type", T.any())
                self.expression(
                    invariant, path + ".kwargs['accumulator_type']", locals_, inputs
                )
                self.compatible(args[1], invariant, path + ".args[1]")
                item, accumulator = self.bind(value, ("item", "accumulator"), path)
                item_shape = (
                    args[0].kwargs["item"] if _kind(args[0]) == "sequence" else T.any()
                )
                body = self.expression(
                    value.kwargs["body"],
                    path + ".kwargs['body']",
                    locals_ | {item: item_shape, accumulator: invariant},
                    inputs,
                )
                self.compatible(body, invariant, path + ".kwargs['body']")
                return (
                    invariant
                    if "accumulator_type" in value.kwargs
                    else _join([args[1], body])
                )
            if op == "iterate":
                (name,) = self.bind(value, ("state",), path)
                limit = self.expression(
                    value.kwargs["max_steps"],
                    path + ".kwargs['max_steps']",
                    locals_,
                    inputs,
                )
                self.expect(limit, {"integer"}, path, "iterate max_steps")
                invariant = value.kwargs.get("state_type", T.any())
                self.expression(
                    invariant, path + ".kwargs['state_type']", locals_, inputs
                )
                self.compatible(args[0], invariant, path + ".args[0]")
                nested = locals_ | {name: invariant}
                condition = self.expression(
                    value.kwargs["until"], path + ".kwargs['until']", nested, inputs
                )
                body = self.expression(
                    value.kwargs["step"], path + ".kwargs['step']", nested, inputs
                )
                self.expect(condition, {"boolean"}, path, "iterate until")
                self.compatible(body, invariant, path + ".kwargs['step']")
                return (
                    invariant
                    if "state_type" in value.kwargs
                    else _join([args[0], body])
                )
            if op == "map_items":
                self.expect(args[0], {"map", "record"}, path, op)
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
            self.expect(args[0], {"sequence", "rank"}, path, op)
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
        numeric = {"integer", "number"}
        if op in {"subtract", "divide", "absolute", "exp"}:
            for shape in args:
                self.expect(shape, numeric, path, op)
            return T.number()
        if op == "add":
            for shape in args:
                self.expect(shape, numeric | {"text", "sequence"}, path, op)
            if all(_kind(shape) not in {"any", "optional", "choice"} for shape in args):
                if (
                    _kind(args[0]) != _kind(args[1])
                    and not {_kind(s) for s in args} <= numeric
                ):
                    self.fail(
                        path,
                        "add requires matching numeric, text, or sequence operands",
                    )
            return _join(args)
        if op == "multiply":
            for shape in args:
                self.expect(shape, numeric | {"text", "sequence"}, path, op)
            known = [_kind(s) for s in args]
            if all(k not in {"any", "optional", "choice"} for k in known):
                if not set(known) <= numeric and not (
                    "integer" in known and ({"text", "sequence"} & set(known))
                ):
                    self.fail(
                        path,
                        "multiply requires numbers or a sequence/text and an integer",
                    )
            return next(
                (s for s in args if _kind(s) in {"text", "sequence"}), _join(args)
            )
        if op in {
            "equals",
            "not_equals",
            "less_than",
            "at_most",
            "greater_than",
            "at_least",
            "and",
            "or",
            "not",
            "contains",
        }:
            # Boolean combinators intentionally use Python truthiness.
            if op in {"less_than", "at_most", "greater_than", "at_least"}:
                for shape in args:
                    self.expect(shape, numeric | {"text", "sequence"}, path, op)
                kinds = {_kind(s) for s in args}
                if (
                    not kinds & {"any", "optional", "choice"}
                    and len(kinds) > 1
                    and not kinds <= numeric
                ):
                    self.fail(path, f"{op} requires comparable operands")
            return T.boolean()
        if op in {"strip", "casefold"}:
            self.expect(args[0], {"text"}, path, op)
            return T.text()
        if op == "concat":
            return T.text()
        if op == "length":
            self.expect(
                args[0], {"sequence", "rank", "map", "record", "text"}, path, op
            )
            return T.integer()
        if op in {"get", "values", "put_value"}:
            self.expect(args[0], {"map", "record"}, path, op)
        if op in {
            "first",
            "at",
            "take",
            "drop_first",
            "append_value",
            "remove_value",
            "logsumexp",
        }:
            self.expect(args[0], {"sequence", "rank"}, path, op)
        if op == "take":
            self.expect(args[1], {"integer"}, path, op)
        if op == "logsumexp":
            if _kind(args[0]) == "sequence":
                self.expect(args[0].kwargs["item"], numeric, path, op)
            return T.number()
        if op == "type":
            return value
        if op == "record":
            return T.record(kwargs)
        if op == "get":
            return (
                (
                    self.member(args[0], value.args[1], path)
                    if _kind(args[0]) == "record"
                    else _join([self.member(args[0], value.args[1], path), args[2]])
                )
                if isinstance(value.args[1], str)
                else (
                    _join([args[0].kwargs["value"], args[2]])
                    if _kind(args[0]) == "map"
                    else T.any()
                )
            )
        if op in {"first", "at"}:
            item = args[0].kwargs["item"] if _kind(args[0]) == "sequence" else T.any()
            return _join([item, args[1]]) if op == "first" else item
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
