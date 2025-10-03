from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class DebugSnapshot:
    params: Any | None
    head_attachments: Any | None
    jobs: Any | None
    results: Any | None
    formatted_output: Any | None

    @staticmethod
    def capture(app: Any) -> "DebugSnapshot":
        return DebugSnapshot(
            params=app._debug_params_last,
            head_attachments=app._debug_head_attachments_last,
            jobs=app._debug_jobs_last,
            results=app._debug_results_last,
            formatted_output=app._debug_output_last,
        )


