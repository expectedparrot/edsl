"""Decorators and supporting classes shared across all EDSL objects."""

from __future__ import annotations

import difflib
import inspect
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from typing import Dict, Optional


@dataclass(frozen=True)
class Snapshot:
    """An immutable record of an EDSL object's state at a point in time.

    Attributes:
        yaml: Full YAML serialization of the object.
        note: Human-readable label supplied by the ``snapshot`` decorator.
        timestamp: UTC ISO-8601 timestamp.
        object_hash: ``hash()`` of the object at snapshot time.
        parameters: Stringified method arguments (excluding *self*).
        yaml_diff: Unified diff against the previous snapshot's YAML,
                   or ``None`` for the first snapshot (display shows full YAML).
    """

    yaml: str
    note: str
    timestamp: str
    object_hash: int
    parameters: Dict[str, str]
    yaml_diff: Optional[str] = None

    def __repr__(self) -> str:
        import io
        from rich.console import Console
        from rich.panel import Panel
        from rich.syntax import Syntax
        from rich.table import Table

        buf = io.StringIO()
        console = Console(file=buf, width=120, force_terminal=True)

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Field", style="bold cyan", width=12)
        table.add_column("Value")
        table.add_row("Note", self.note)
        table.add_row("Timestamp", self.timestamp)
        table.add_row("Hash", str(self.object_hash))
        if self.parameters:
            params_str = ", ".join(
                f"{k}={v}" for k, v in self.parameters.items()
            )
            table.add_row("Parameters", params_str)
        console.print(table)

        if self.yaml_diff is None:
            syntax = Syntax(
                self.yaml, "yaml", theme="monokai", line_numbers=False
            )
            console.print(Panel(syntax, title="YAML"))
        else:
            syntax = Syntax(
                self.yaml_diff, "diff", theme="monokai", line_numbers=False
            )
            console.print(Panel(syntax, title="Changes"))

        return buf.getvalue()


def _compute_yaml_diff(old_yaml: str, new_yaml: str) -> str:
    """Return a unified diff between two YAML strings."""
    return "\n".join(
        difflib.unified_diff(
            old_yaml.splitlines(),
            new_yaml.splitlines(),
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )


def make_initial_snapshot(obj) -> Snapshot:
    """Create the first snapshot for a freshly constructed EDSL object.

    The object must support ``.to_yaml()`` and ``hash()``.
    """
    return Snapshot(
        yaml=obj.to_yaml(),
        note="Initial snapshot",
        timestamp=datetime.now(timezone.utc).isoformat(),
        object_hash=hash(obj),
        parameters={},
    )


def snapshot(note: str):
    """Decorator for methods that return an EDSL object with ``to_yaml()``.

    After the decorated method executes, a :class:`Snapshot` is created from
    the result and appended to the snapshot history carried forward from
    ``self``.  The object must expose ``_snapshots`` (a list of
    :class:`Snapshot`) and ``to_yaml()``.
    """

    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            result = method(self, *args, **kwargs)

            sig = inspect.signature(method)
            bound = sig.bind(self, *args, **kwargs)
            bound.apply_defaults()
            params = {
                k: str(v) for k, v in bound.arguments.items() if k != "self"
            }

            new_yaml = result.to_yaml()
            prev_yaml = (
                self._snapshots[-1].yaml if self._snapshots else None
            )
            diff = (
                _compute_yaml_diff(prev_yaml, new_yaml) if prev_yaml else None
            )

            snap = Snapshot(
                yaml=new_yaml,
                note=note,
                timestamp=datetime.now(timezone.utc).isoformat(),
                object_hash=hash(result),
                parameters=params,
                yaml_diff=diff if diff else None,
            )
            result._snapshots = list(self._snapshots) + [snap]
            return result

        return wrapper

    return decorator


def polly_command(func):
    """Decorator to mark methods as available commands."""
    func._is_polly_command = True
    return func
