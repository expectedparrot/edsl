# plan.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .ops import (Op, 
    LoadMeta, 
    ValidateNoDroppedKeys, 
    ApplyRenames, 
    ComputeDigest, 
    AssignPosition, 
    PersistScenario, 
    AddRename, 
    PersistMeta, 
    AddDrop,
    AddValues,
    )

from .ops import State



@dataclass(frozen=True)
class Plan:
    ops: List[Op]

    def execute(self, st: State, ctx: Dict[str, Any]) -> Dict[str, Any]:
        for op in self.ops:
            op.run(st, ctx)
        return ctx


def build_append_plan(payload: Dict[str, Any]) -> Plan:
    """
    Append semantics = this fixed pipeline.
    Any backend must run the same pipeline.
    """
    return Plan(ops=[
        LoadMeta(),
        ValidateNoDroppedKeys(),
        ApplyRenames(),
        ComputeDigest(),
        AssignPosition(),
        PersistScenario(),
    ])

def build_rename_plan(old_key: str, new_key: str) -> Plan:
    """
    Rename a field: updates meta so future scenarios apply the rename.
    """
    return Plan(ops=[
        LoadMeta(),
        AddRename(old_key, new_key),
        PersistMeta(),
    ])

def build_drop_key_plan(key: str) -> Plan:
    """
    Drop a field: updates meta so future scenarios drop the key.
    """
    return Plan(ops=[
        LoadMeta(),
        AddDrop(key),
        PersistMeta(),
    ])

def build_add_values_plan(key: str, values: List[Any]) -> Plan:

    """
    Add values to a field: updates meta so future scenarios add the values.
    """
    return Plan(ops=[
        LoadMeta(),
        AddValues(key, values),
        PersistMeta(),
    ])
