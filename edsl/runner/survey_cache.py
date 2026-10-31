"""Reuse validated survey templates while isolating every caller's mutations."""

from collections import OrderedDict
from copy import deepcopy
import hashlib
import pickle
import threading

from ..surveys import Survey


class SurveyCache:
    """Small, process-local cache of deserialized survey definitions.

    Key the entire serialized payload, including state definitions and rules.
    Changed data must pass normal deserialization/validation again. Templates
    never escape: answer piping, rendering, and Results may mutate their copies.
    Runtime state, views, capability checks, and execution budgets are not cached.
    """

    def __init__(self, max_entries: int = 16):
        if type(max_entries) is not int or max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        self._max_entries = max_entries
        self._templates: OrderedDict[bytes, Survey] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, data: dict) -> Survey:
        # This process-local key must preserve Python types: JSON would conflate
        # integer/string map keys and could reuse a valid template for bad input.
        # These bytes are only hashed, never stored externally or unpickled.
        key = hashlib.sha256(pickle.dumps(data, protocol=5)).digest()
        with self._lock:
            if key in self._templates:
                template = self._templates[key]
                self._templates.move_to_end(key)
            else:
                # Publish only after decoding and validation have succeeded.
                template = Survey.from_dict(deepcopy(data))
                self._templates[key] = template
                if len(self._templates) > self._max_entries:
                    self._templates.popitem(last=False)
        return deepcopy(template)
