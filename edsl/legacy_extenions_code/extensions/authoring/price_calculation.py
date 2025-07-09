"""edsl/extensions/price_calculation.py

Utility for computing the price of calling a service defined by
`ServiceDefinition`.  The cost model is the one currently encoded in
`CostDefinition`:

• ``per_call_cost`` – a fixed amount charged for every invocation.
• ``variable_pricing_cost_formula`` – an optional arithmetic expression
  that can reference parameter names (e.g. ``num_questions * 10``).  The
  expression is evaluated using the concrete values that will be sent to
  the service (after default-value substitution).

The public helper exposed here is ``compute_price``.

Example
-------
>>> from edsl.extensions.authoring import ServiceDefinition
>>> from edsl.extensions.price_calculation import compute_price
>>> service_def = ServiceDefinition.example()
>>> compute_price(service_def, {"overall_question": "What is life?", "population": "humans", "num_questions": 7})
170  # 100 + 7*10
"""
from __future__ import annotations

import ast
from dataclasses import MISSING
from typing import Any, Dict, Union, Callable

from .authoring import ServiceDefinition

Number = Union[int, float]


class PriceCalculationError(Exception):
    """Raised when a price cannot be computed (e.g. invalid formula)."""


_ALLOWED_AST_NODES: tuple[type, ...] = (
    ast.Expression,
    ast.Num,  # py<3.8 fallback
    ast.Constant,  # numbers in py>=3.8
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.FloorDiv,
    ast.UAdd,
    ast.USub,
    ast.Name,
    ast.Load,
    ast.Call,  # Allow minimal use of "abs" etc. – guarded below.
)

_ALLOWED_BUILTINS: dict[str, Callable[[Any], Any]] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
}


def _validate_ast(node: ast.AST) -> None:
    """Recursively ensure the AST contains only whitelisted node types."""
    if not isinstance(node, _ALLOWED_AST_NODES):
        raise PriceCalculationError(
            f"Disallowed expression element: {node.__class__.__name__}."
        )

    for child in ast.iter_child_nodes(node):
        _validate_ast(child)


def _safe_eval(expr: str, variables: Dict[str, Number]) -> Number:
    """Safely evaluate a simple arithmetic *expr* given *variables*.

    Only numeric literals, variable names, the operators + – * / // % **,
    unary ± and a minimal selection of built-ins (abs, round, min, max)
    are permitted.  Anything else raises :class:`PriceCalculationError`.
    """
    try:
        parsed = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise PriceCalculationError(f"Invalid pricing formula: {e.msg}") from e

    _validate_ast(parsed)

    # Evaluate with an empty globals mapping and a restricted built-ins.
    try:
        return eval(  # noqa: S307 – deliberately controlled
            compile(parsed, filename="<pricing_formula>", mode="eval"),
            {"__builtins__": _ALLOWED_BUILTINS},
            variables,
        )
    except NameError as e:
        # Missing variable reference
        raise PriceCalculationError(f"Unknown variable in pricing formula – {e}") from e
    except Exception as e:  # pragma: no cover – catch-all safety net
        raise PriceCalculationError(str(e)) from e


def _prepare_call_parameters(
    service_def: ServiceDefinition, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Mimic :py:meth:`ServiceDefinition._prepare_parameters` (private).

    We re-implement just what is needed for cost computation so that the
    helper works even if consumers don't have access to the *private*
    method or want to avoid the underscore call.
    """
    prepared: Dict[str, Any] = {}
    for name, p_def in service_def.parameters.items():
        if name in params:
            prepared[name] = params[name]
        elif p_def.default_value is not MISSING:
            prepared[name] = p_def.default_value
    return prepared


def compute_price(
    service_def: ServiceDefinition, call_params: Dict[str, Any]
) -> Number:
    """Return the price (in the ``unit`` specified by the service) for a call.

    Parameters
    ----------
    service_def:
        The :class:`ServiceDefinition` describing the service.
    call_params:
        The user-supplied parameters (before default substitution).  They
        will be validated with :py:meth:`ServiceDefinition.validate_call_parameters`.
    """
    # Validate parameters so we can safely rely on them.
    service_def.validate_call_parameters(call_params)
    prepared = _prepare_call_parameters(service_def, call_params)

    cost_def = service_def.cost
    total: Number = cost_def.per_call_cost

    if cost_def.variable_pricing_cost_formula:
        variable_component = _safe_eval(
            cost_def.variable_pricing_cost_formula,
            variables={
                k: v for k, v in prepared.items() if isinstance(v, (int, float))
            },
        )
        total += variable_component

    return total
