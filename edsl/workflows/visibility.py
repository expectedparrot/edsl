"""Template reference analysis and least-privilege workflow observations.

Static checks give authoring errors; filtering the runtime data is the actual
visibility boundary, including for aliases and dynamic Jinja lookups.
"""

from __future__ import annotations

from collections.abc import Mapping

from jinja2 import Environment, nodes


OWN = object()
DYNAMIC = object()


def template_references(value):
    """Yield access paths, recognizing dot, bracket and dictionary-get syntax."""

    def key(node):
        if isinstance(node, nodes.Const):
            return node.value if isinstance(node.value, str) else DYNAMIC
        return OWN if path(node) == ("participant", "name") else DYNAMIC

    def path(node):
        if isinstance(node, nodes.Name):
            return (node.name,)
        if isinstance(node, nodes.Getattr):
            parent = path(node.node)
            return (*parent, node.attr) if parent else None
        if isinstance(node, nodes.Getitem):
            parent = path(node.node)
            return (*parent, key(node.arg)) if parent else None
        if isinstance(node, nodes.Call) and isinstance(node.node, nodes.Getattr):
            parent = path(node.node.node)
            if parent and node.node.attr == "get" and node.args:
                return (*parent, key(node.args[0]))
        return None

    def visit(node, parent=None):
        current = path(node)
        # Only the outermost member of an access chain is a reference. Other
        # expressions (such as a .get default) remain independent references.
        chained = (
            isinstance(parent, (nodes.Getattr, nodes.Getitem)) and parent.node is node
        ) or (
            isinstance(parent, nodes.Call)
            and path(parent) is not None
            and parent.node is node
        )
        if current and not chained:
            yield current
        for child in node.iter_child_nodes():
            yield from visit(child, node)

    if isinstance(value, str) and any(marker in value for marker in ("{{", "{%")):
        yield from visit(Environment().parse(value))
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from template_references(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from template_references(item)


def participant_keyed(expression, definitions):
    if expression.op in {"map_submissions", "map_joined_submissions", "payoff_matrix"}:
        return True
    if expression.op == "derived_ref":
        source = definitions[expression.options["name"]]
        return participant_keyed(
            source.fields[expression.options["field"]], definitions
        )
    return False


def own_projections(step, definitions):
    return {
        (reference[2], reference[3])
        for reference in template_references(step.survey.to_dict())
        if len(reference) >= 5
        and reference[:2] == ("workflow", "derived")
        and reference[4] is OWN
        and reference[2] in definitions
        and reference[3] in definitions[reference[2]].fields
        and participant_keyed(
            definitions[reference[2]].fields[reference[3]], definitions
        )
    }


def visible_derived(workflow, step, traits, values):
    definitions = {
        definition.name: definition for definition in workflow.derived_values
    }
    projections = own_projections(step, definitions)
    visible = {}
    for name, fields in values.items():
        for field, value in fields.items():
            expression = definitions[name].fields[field]
            if all(
                workflow.step(source).output_visibility is None
                or any(
                    selector.matches(traits)
                    for selector in workflow.step(source).output_visibility
                )
                for source in expression.dependencies
            ):
                visible.setdefault(name, {})[field] = value
            elif (name, field) in projections and isinstance(value, Mapping):
                # Explicit participant projection releases just the recipient's
                # value, never the full private table or unrelated fields.
                participant = traits["name"]
                visible.setdefault(name, {})[field] = (
                    {participant: value[participant]} if participant in value else {}
                )
    return visible
