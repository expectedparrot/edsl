from __future__ import annotations
from typing import Any, List


class DebugInfo:
    """Container for App runtime debug information with convenience setters.

    Tracks the most recent params, head_attachments, jobs, results, and
    formatted output. Also maintains a history of snapshots captured via
    `DebugSnapshot` for post-hoc inspection.
    """

    def __init__(self, app: Any) -> None:
        self._app = app
        self.params_last: Any | None = None
        self.head_attachments_last: Any | None = None
        self.jobs_last: Any | None = None
        self.results_last: Any | None = None
        self.output_last: Any | None = None
        self.history: List[dict] = []

    # Setters
    def set_params(self, params: Any) -> None:
        self.params_last = params

    def set_head_attachments(self, head_attachments: Any) -> None:
        self.head_attachments_last = head_attachments

    def set_jobs(self, jobs: Any) -> None:
        self.jobs_last = jobs

    def set_results(self, results: Any) -> None:
        self.results_last = results

    def set_output(self, output: Any) -> None:
        self.output_last = output

    # Snapshot helpers
    def capture_snapshot(self) -> dict:
        # Import lazily to avoid circular dependencies
        from .debug_snapshot import DebugSnapshot

        return DebugSnapshot.capture(self._app)

    def record_snapshot(self) -> dict:
        snap = self.capture_snapshot()
        self.history.append(snap)
        return snap


