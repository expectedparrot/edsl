"""
Composed ScenarioListTransformer built from focused mixins.

This module assembles all transform mixins into a single class that
provides the same instance-method API as the original monolithic
``scenario_list_transformer.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .convert import ConvertMixin
from .filter import FilterMixin
from .mutate import MutateMixin
from .reshape import ReshapeMixin
from .combine import CombineMixin
from .select import SelectMixin
from .order import OrderMixin

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


class ScenarioListTransformer(
    ConvertMixin,
    FilterMixin,
    MutateMixin,
    ReshapeMixin,
    CombineMixin,
    SelectMixin,
    OrderMixin,
):
    """Collection of transformations operating on a ScenarioList.

    Each group of operations lives in its own mixin module under
    ``edsl.scenarios.transforms``.  This composed class re-exports
    every method so that existing call-sites keep working unchanged.
    """

    def __init__(self, scenario_list: "ScenarioList"):
        """Initialize with a reference to the ScenarioList.

        Args:
            scenario_list: The ScenarioList instance to operate on.
        """
        self._scenario_list = scenario_list
