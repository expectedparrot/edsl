from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DebugSnapshot:
    params: Any | None
    head_attachments: Any | None
    jobs: Any | None
    results: Any | None
    formatted_output: Any | None

    @staticmethod
    def capture(app: Any) -> "DebugSnapshot":
        # Prefer new DebugInfo container if available
        debug = getattr(app, "debug", None)
        if debug is not None:
            return DebugSnapshot(
                params=getattr(debug, "params_last", None),
                head_attachments=getattr(debug, "head_attachments_last", None),
                jobs=getattr(debug, "jobs_last", None),
                results=getattr(debug, "results_last", None),
                formatted_output=getattr(debug, "output_last", None),
            )
        # Fallback to legacy attributes for compatibility
        return DebugSnapshot(
            params=getattr(app, "_debug_params_last", None),
            head_attachments=getattr(app, "_debug_head_attachments_last", None),
            jobs=getattr(app, "_debug_jobs_last", None),
            results=getattr(app, "_debug_results_last", None),
            formatted_output=getattr(app, "_debug_output_last", None),
        )
