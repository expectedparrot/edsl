"""Deterministic interpreter quotas, independent of host wall-clock speed.

These bound DSL work and JSON trees, not arbitrary registered Python callbacks.
"""

from contextvars import ContextVar
from dataclasses import dataclass, fields, is_dataclass
from functools import wraps


class ResourceLimitError(ValueError):
    """An operation exhausted a configured interpreter resource quota."""


@dataclass(frozen=True)
class ExecutionLimits:
    max_steps: int = 1_000_000
    max_ast_nodes: int = 100_000
    max_depth: int = 80
    max_collection_items: int = 10_000
    max_value_nodes: int = 100_000
    max_value_bytes: int = 8_000_000
    max_integer_bits: int = 4096

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{field.name} must be a positive integer")


class Budget:
    def __init__(self, limits):
        self.limits = limits
        self.steps = 0

    def check(self, resource, actual):
        maximum = getattr(self.limits, resource)
        if actual > maximum:
            raise ResourceLimitError(
                f"Machine resource limit {resource} exceeded ({maximum})"
            )

    def charge(self, count=1):
        self.steps += count
        self.check("max_steps", self.steps)

    def tree(self, value, *, ast=False, start_depth=0):
        """Iterative walk: reject excessive depth before recursive interpreter work.

        JSON byte accounting is a conservative upper bound (including escaping),
        not a measurement of Python heap usage. Repeated references count again.
        """
        pending = [(value, start_depth)]
        count = size = 0
        while pending:
            item, depth = pending.pop()
            count += 1
            self.charge()
            self.check("max_depth", depth)
            self.check("max_ast_nodes" if ast else "max_value_nodes", count)
            if isinstance(item, str):
                size += 2 + 6 * len(item)
            elif isinstance(item, bool) or item is None:
                size += 5
            elif isinstance(item, int):
                self.check("max_integer_bits", item.bit_length())
                size += max(1, item.bit_length()) + 1
            elif isinstance(item, float):
                size += 32
            elif isinstance(item, dict):
                self.check("max_collection_items", len(item))
                size += 2 + 2 * len(item)
                pending.extend(
                    (child, depth + 1) for pair in item.items() for child in pair
                )
            elif isinstance(item, (tuple, list)):
                self.check("max_collection_items", len(item))
                size += 2 + len(item)
                pending.extend((child, depth + 1) for child in item)
            elif is_dataclass(item):
                pending.extend((getattr(item, f.name), depth + 1) for f in fields(item))
            self.check("max_value_bytes", size)
        return count, size


_active_budget = ContextVar("machine_execution_budget", default=None)


def bounded_operation(method):
    """Nested interpreter calls share the outer budget; parallel calls do not."""

    @wraps(method)
    def run(self, *args, **kwargs):
        if _active_budget.get() is not None:
            return method(self, *args, **kwargs)
        budget = Budget(self.limits)
        token = _active_budget.set(budget)
        try:
            # Check all external trees before deepcopy, recursion or JSON encoding.
            for index, arg in enumerate(args):
                budget.tree(
                    arg,
                    ast=is_dataclass(arg)
                    or (method.__name__ == "_evaluate_standalone" and index == 0),
                )
            for name, arg in kwargs.items():
                budget.tree(
                    arg,
                    ast=is_dataclass(arg)
                    or (method.__name__ == "_evaluate_standalone" and name == "value"),
                )
            result = method(self, *args, **kwargs)
            budget.tree(result)
            return result
        finally:
            _active_budget.reset(token)

    return run


def check_machine_tree(machine):
    """Guard Machine.validate before serialization and recursive AST checks."""
    Budget(ExecutionLimits()).tree(machine, ast=True)


class BoundedCollection:
    """Account for a growing result before retaining each newly computed value."""

    def __init__(self, *, mapping=False):
        self.budget = _active_budget.get()
        self.value = {} if mapping else []
        self.nodes, self.size = 1, 2
        self.members = {}

    def _include(self, item, previous=(0, 0)):
        nodes, size = self.budget.tree(item, start_depth=1)
        self.nodes += nodes - previous[0]
        self.size += size - previous[1]
        self.budget.check("max_value_nodes", self.nodes)
        self.budget.check("max_value_bytes", self.size)
        return nodes, size

    def append(self, item):
        self.budget.check("max_collection_items", len(self.value) + 1)
        self._include((item,))  # Also accounts conservatively for separators.
        self.value.append(item)

    def put(self, key, item):
        self.budget.check(
            "max_collection_items", len(self.value) + (key not in self.value)
        )
        self.members[key] = self._include((key, item), self.members.get(key, (0, 0)))
        self.value[key] = item
