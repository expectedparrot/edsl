"""Declarative, scoped shared state for coordinated surveys."""

from .refs import current
from .model import (
    ReadOperation, ScopeKey, SharedState, SharedStateMap, StateCondition,
    StateRead, StateWrite,
    WriteOperation, resolve_read, resolve_write, step_from_dict, step_to_dict,
)
from .backend import (
    AdvisoryWriteOutcome, ObservedState, SQLiteStateBackend,
    StateBackend, StateSnapshot,
)
from .dsl import (
    Command, Effect, Expr, Machine, T, algorithm, append, choose, constant,
    current as current_value, decode_matrix, expr, field, filter_items, input_, local,
    map_items, map_of, map_sequence, put, record, reduce_, set_, set_once, state_field,
    when,
)

__all__ = [
    "SharedState", "SharedStateMap", "ScopeKey", "StateCondition", "StateRead",
    "StateWrite",
    "ReadOperation", "WriteOperation", "resolve_read", "resolve_write",
    "step_from_dict", "step_to_dict", "SQLiteStateBackend",
    "StateBackend", "StateSnapshot", "AdvisoryWriteOutcome", "ObservedState",
    "Machine", "Command", "Effect",
    "Expr", "T", "algorithm", "append", "choose", "constant", "current",
    "current_value", "decode_matrix", "expr", "field", "filter_items", "input_", "local",
    "map_items", "map_of", "map_sequence", "put", "record", "reduce_", "set_",
    "set_once", "state_field", "when",
]
