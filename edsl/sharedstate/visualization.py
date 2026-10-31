"""Visualize a shared-state Machine as fields, transitions, and projections."""

from __future__ import annotations

import json
import re
import textwrap
from typing import Any

from edsl.utilities.graph_renderer import DiGraph, PydotRenderer


_BINARY = {
    "add": "+",
    "subtract": "−",
    "multiply": "×",
    "divide": "/",
    "equals": "=",
    "not_equals": "≠",
    "less_than": "<",
    "at_most": "≤",
    "greater_than": ">",
    "at_least": "≥",
    "and": "and",
    "or": "or",
}


def _value(value: Any, limit: int = 72) -> str:
    if hasattr(value, "op") and hasattr(value, "args"):
        rendered = _expression(value)
    else:
        try:
            rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            rendered = repr(value)
    if len(rendered) > limit:
        rendered = rendered[: limit - 1] + "…"
    return rendered


def _wrap_label(label: str, width: int = 42) -> str:
    """Keep Graphviz labels from forcing a very wide canvas."""
    lines = []
    for line in label.splitlines():
        wrapped = textwrap.wrap(
            line,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=False,
        )
        lines.extend(wrapped or [""])
    return "\n".join(lines)


def _expression(expression: Any) -> str:
    op = expression.op
    args = expression.args
    kwargs = expression.kwargs
    if op == "ref":
        namespace = kwargs.get("namespace")
        name = kwargs.get("name", "?")
        if namespace == "current":
            return f"current.{name}"
        return str(name)
    if op in _BINARY and len(args) == 2:
        return f"({_value(args[0])} {_BINARY[op]} {_value(args[1])})"
    if op == "not" and args:
        return f"¬{_value(args[0])}"
    if op == "if" and len(args) == 3:
        return f"if {_value(args[0])} then {_value(args[1])} else {_value(args[2])}"
    if op == "reduce" and len(args) >= 2:
        return f"{args[0]}({_value(args[1])})"
    if op in {"values", "length", "strip", "casefold", "drop_first"} and args:
        method = {"values": "values", "length": "len", "strip": "strip",
                  "casefold": "casefold", "drop_first": "drop_first"}[op]
        return f"{method}({_value(args[0])})"
    if op == "record":
        return "{" + ", ".join(f"{k}: {_value(v)}" for k, v in kwargs.items()) + "}"
    if op == "get" and len(args) >= 2:
        return f"{_value(args[0])}[{_value(args[1])}]"
    if op == "at" and len(args) >= 2:
        return f"{_value(args[0])}[{_value(args[1])}]"
    if op == "type":
        return _type(expression)
    if op == "ref":
        return f"ref({kwargs.get('name', '?')})"
    rendered = ", ".join(_value(arg) for arg in args)
    if kwargs:
        extras = ", ".join(f"{key}={_value(value)}" for key, value in kwargs.items())
        rendered = ", ".join(part for part in (rendered, extras) if part)
    return f"{op}({rendered})"


def _type(type_expr: Any) -> str:
    if not (hasattr(type_expr, "op") and type_expr.op == "type"):
        return _value(type_expr)
    kind = type_expr.args[0] if type_expr.args else "any"
    kwargs = type_expr.kwargs
    if kind == "map":
        return f"map[{_type(kwargs.get('key'))} → {_type(kwargs.get('value'))}]"
    if kind == "choice":
        options = kwargs.get("options", ())
        return f"choice({_value(options)})"
    if kind in {"sequence", "optional"}:
        return f"{kind}[{_type(kwargs.get('item'))}]"
    if kind == "record":
        fields = kwargs.get("fields", {})
        body = ", ".join(f"{name}: {_type(value)}" for name, value in fields.items())
        return f"record{{{body}}}"
    details = ", ".join(
        f"{key}={_value(value)}"
        for key, value in kwargs.items()
        if value is not None
    )
    return f"{kind}({details})" if details else str(kind)


def _references(value: Any, namespace: str) -> set[str]:
    found: set[str] = set()
    if hasattr(value, "op") and hasattr(value, "args"):
        options = getattr(value, "kwargs", getattr(value, "options", {}))
        if value.op == "ref" and options.get("namespace") == namespace:
            found.add(options.get("name", "?"))
        for child in value.args:
            found.update(_references(child, namespace))
        for child in options.values():
            found.update(_references(child, namespace))
    elif isinstance(value, dict):
        for child in value.values():
            found.update(_references(child, namespace))
    elif isinstance(value, (tuple, list)):
        for child in value:
            found.update(_references(child, namespace))
    return found


def _effect_label(effect: Any, *, detail: bool = False, summary: bool = False) -> str:
    op = effect.op
    args = effect.args
    if summary and not detail and op in {"set", "set_once", "put", "append"}:
        if op == "put":
            return f"{effect.target}[{_value(args[0])}] ← …"
        suffix = " (once)" if op == "set_once" else ""
        return f"{effect.target} ← …{suffix}"
    limit = 220 if detail else 72
    if op == "set":
        action = f"{effect.target} ← {_value(args[0], limit)}"
    elif op == "set_once":
        action = f"{effect.target} ← {_value(args[0], limit)} (once)"
    elif op == "put":
        action = f"{effect.target}[{_value(args[0], limit)}] ← {_value(args[1], limit)}"
        if effect.options.get("once"):
            action += " (once)"
    elif op == "append":
        action = f"append {_value(args[0], limit)} to {effect.target}"
    elif op == "assert":
        action = f"require {_value(args[0])} [{effect.options.get('code', '')}]"
    elif op == "reject":
        action = f"reject [{effect.options.get('code', '')}]"
    elif op == "algorithm":
        action = f"algorithm {effect.options.get('name', '?')}"
    else:
        action = f"{op}({', '.join(_value(arg) for arg in args)})"
    condition = effect.options.get("when")
    return f"when {_value(condition)}: {action}" if condition is not None else action


def _node_id(prefix: str, name: str) -> str:
    safe = re.sub(r"\W+", "_", name).strip("_") or "item"
    return f"{prefix}_{safe}"


def machine_graph(
    machine: Any,
    renderer: str | None = None,
    dpi: int = 192,
    detail: bool = False,
):
    """Build a rendered machine diagram; command cards describe transitions."""
    graph_renderer = PydotRenderer(dpi=dpi) if renderer == "pydot" else renderer
    graph = DiGraph(renderer=graph_renderer, direction="LR")
    constant_refs = _references(
        (
            tuple(
                (command.inputs, command.require, command.effects)
                for command in machine.commands.values()
            ),
            machine.view,
            machine.complete_when,
            machine.close_effects,
            tuple((definition.type, definition.initial) for definition in machine.fields.values()),
        ),
        "constant",
    )
    used_constants = {
        name: value for name, value in machine.constants.items() if name in constant_refs
    }
    if used_constants:
        graph.add_subgraph(
            "constants", label=f"{machine.name} · Constants", fill_color="lightyellow"
        )
        constants_id = "machine_constants"
        constants_text = "\n".join(
            f"{name} = {_value(value)}" for name, value in used_constants.items()
        )
        graph.add_node(
            constants_id,
            label=_wrap_label(constants_text),
            fill_color="lightyellow",
            font_size="12",
            subgraph="constants",
        )
    else:
        constants_id = None

    graph.add_subgraph(
        "state", label=f"{machine.name} · Persistent state", fill_color="lightblue"
    )
    field_ids = {}
    if machine.fields:
        for name, definition in machine.fields.items():
            node_id = _node_id("field", name)
            field_ids[name] = node_id
            graph.add_node(
                node_id,
                label=_wrap_label(
                    f"{name}\n{_type(definition.type)}\ninitial: {_value(definition.initial)}"
                ),
                fill_color="white",
                font_size="12",
                subgraph="state",
            )
            if constants_id and _references(definition.type, "constant") & used_constants.keys():
                graph.add_edge(
                    constants_id, node_id, label="defines type", style="dotted", color="orange"
                )
    else:
        graph.add_node("no_state", label="No fields", subgraph="state")

    graph.add_subgraph(
        "commands", label="Commands · state transitions", fill_color="honeydew"
    )
    for name, command in machine.commands.items():
        lines = [name, "INPUTS"]
        if command.inputs:
            lines.extend(f"  {key}: {_type(value)}" for key, value in command.inputs.items())
        else:
            lines.append("  none")
        if command.require is not None:
            lines.extend(("GUARD", f"  {_value(command.require)}"))
        lines.append("EFFECTS")
        if command.effects:
            lines.extend(
                f"  {_effect_label(effect, detail=detail)}" for effect in command.effects
            )
        else:
            lines.append("  none")
        node_id = _node_id("command", name)
        graph.add_node(
            node_id,
            label=_wrap_label("\n".join(lines)),
            fill_color="white",
            font_size="12",
            subgraph="commands",
        )
        read_fields = set()
        if command.require is not None:
            read_fields.update(_references(command.require, "state"))
        for effect in command.effects:
            read_fields.update(_references(effect.args, "state"))
            read_fields.update(_references(effect.options, "state"))
        written_fields = {effect.target for effect in command.effects if effect.target in field_ids}
        for field_name in sorted(read_fields & field_ids.keys()):
            graph.add_edge(field_ids[field_name], node_id, label="reads", style="dashed", color="slategray")
        for field_name in sorted(written_fields):
            graph.add_edge(node_id, field_ids[field_name], label="writes", color="darkgreen")
        command_constants = _references(
            (command.inputs, command.require, command.effects), "constant"
        )
        if constants_id and command_constants & used_constants.keys():
            graph.add_edge(
                constants_id, node_id, label="uses", style="dotted", color="orange"
            )

    graph.add_subgraph("view", label="Read-only view", fill_color="mistyrose")
    if machine.view:
        for name, expression in machine.view.items():
            node_id = _node_id("view", name)
            if (
                getattr(expression, "op", None) == "ref"
                and expression.kwargs.get("namespace") == "state"
                and expression.kwargs.get("name") == name
            ):
                expression_label = "(state field)"
            elif (
                getattr(expression, "op", None) == "ref"
                and expression.kwargs.get("namespace") == "constant"
                and expression.kwargs.get("name") == name
            ):
                expression_label = "(constant)"
            else:
                expression_label = _value(expression, 220 if detail else 72)
            graph.add_node(
                node_id,
                label=_wrap_label(f"{name}\n{expression_label}"),
                fill_color="white",
                font_size="12",
                subgraph="view",
            )
            if constants_id and _references(expression, "constant") & used_constants.keys():
                graph.add_edge(
                    constants_id, node_id, label="uses", style="dotted", color="orange"
                )
            for field_name in sorted(_references(expression, "state") & field_ids.keys()):
                graph.add_edge(field_ids[field_name], node_id, label="projects", color="purple")
    else:
        graph.add_node("empty_view", label="No view fields", subgraph="view")

    lifecycle = []
    if machine.complete_when is not None:
        lifecycle.append(f"complete when: {_value(machine.complete_when)}")
    if machine.close_effects:
        lifecycle.append("on close:")
        lifecycle.extend(
            f"  {_effect_label(effect, detail=detail, summary=True)}"
            for effect in machine.close_effects
        )
    lifecycle_constants = _references(
        (machine.complete_when, machine.close_effects), "constant"
    )
    lifecycle_constant_names = sorted(lifecycle_constants & used_constants.keys())
    if lifecycle_constant_names:
        lifecycle.append(
            "uses constants: " + ", ".join(lifecycle_constant_names)
        )
    if lifecycle:
        graph.add_subgraph("lifecycle", label="Lifecycle", fill_color="khaki")
        graph.add_node(
            "lifecycle_rules",
            label=_wrap_label("\n".join(lifecycle)),
            fill_color="white",
            font_size="12",
            subgraph="lifecycle",
        )
        close_reads = _references((machine.complete_when, machine.close_effects), "state")
        for field_name in sorted(close_reads & field_ids.keys()):
            graph.add_edge(field_ids[field_name], "lifecycle_rules", label="reads", style="dashed", color="slategray")
        for effect in machine.close_effects:
            if effect.target in field_ids:
                graph.add_edge("lifecycle_rules", field_ids[effect.target], label="writes", color="darkgreen")
    return graph
