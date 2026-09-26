"""Versioned, derived Machine requirements and interpreter advertisements.

Manifest schema 1 is separate from Machine language version 1. These manifests
are derived metadata and never participate in persisted definition fingerprints.
"""

from .exceptions import UnsupportedCapabilityError
from .resources import Budget, ExecutionLimits, _active_budget

EXPRESSION_OPERATORS = {
    "let",
    "fold",
    "iterate",
    "take",
    "exp",
    "logsumexp",
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
    "decode_matrix",
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

REDUCERS = {
    "tail",
    "count_by",
    "sum",
    "mean",
    "median",
    "max",
    "argmax",
    "sort_records",
    "latest_by",
    "count_equal",
    "increment_keys",
    "keys_min_distance",
    "weighted_matrix_tally",
    "ranked_ballot_results",
    "group_numeric_summary",
    "series_converged",
}

TYPE_KINDS = frozenset(
    {
        "any",
        "boolean",
        "text",
        "integer",
        "number",
        "choice",
        "rank",
        "optional",
        "sequence",
        "map",
        "record",
    }
)
EFFECT_OPERATORS = frozenset({"set", "set_once", "put", "append", "algorithm"})
FEATURES = frozenset({"fold.accumulator_type", "iterate.state_type"})
BUILTIN_CAPABILITIES = frozenset(
    {"language:machine@1", "algorithm_view:lmsr_prices@1", "dependency:lmsr_prices@1"}
    | {f"expression:{name}@1" for name in EXPRESSION_OPERATORS}
    | {f"reducer:{name}@1" for name in REDUCERS}
    | {f"type:{name}@1" for name in TYPE_KINDS}
    | {f"effect:{name}@1" for name in EFFECT_OPERATORS}
    | {f"feature:{name}@1" for name in FEATURES}
)


def requirements(value):
    """Return every required capability and its source locations, including dead code."""
    from .dsl import Effect, Expr, Machine
    from .validation import walk_paths

    # Also protects standalone callers before the recursive location walk.
    (_active_budget.get() or Budget(ExecutionLimits())).tree(value, ast=True)
    found = {}

    def add(name, path):
        found.setdefault(name, []).append(path)

    if isinstance(value, Machine):
        add("language:machine@1", "$.version")
        for index, capability in enumerate(value.algorithms):
            add(f"dependency:{capability}", f"$.algorithms[{index}]")
    for path, item in walk_paths(value):
        if isinstance(item, Expr):
            add(f"expression:{item.op}@1", path)
            if item.op == "type" and item.args:
                add(f"type:{item.args[0]}@1", path)
            if item.op == "reduce" and item.args:
                add(f"reducer:{item.args[0]}@1", path)
            if item.op == "algorithm_view" and item.args:
                add(
                    f"algorithm_view:{item.args[0]}@{item.kwargs.get('version', 1)}",
                    path,
                )
            for feature in FEATURES:
                operation, option = feature.split(".")
                if item.op == operation and option in item.kwargs:
                    add(f"feature:{feature}@1", path + f".kwargs[{option!r}]")
        elif isinstance(item, Effect):
            add(f"effect:{item.op}@1", path)
            if item.op == "algorithm":
                add(f"algorithm:{item.options['name']}@{item.options['version']}", path)
    return found


def check_capabilities(value, manifest):
    """Compare against an advertised exact-version set; do not trust sender claims."""
    if (
        not isinstance(manifest, dict)
        or manifest.get("version") != 1
        or type(manifest.get("version")) is not int
    ):
        raise ValueError("unsupported capability manifest version")
    supported = manifest.get("supported")
    if not isinstance(supported, list) or any(
        not isinstance(name, str) for name in supported
    ):
        raise ValueError("capability manifest requires a supported list of strings")
    available = set(supported)
    missing = {
        name: paths
        for name, paths in requirements(value).items()
        if name not in available
    }
    if missing:
        raise UnsupportedCapabilityError(getattr(value, "name", "Expression"), missing)
