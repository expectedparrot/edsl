from __future__ import annotations

from typing import Any, Optional

from .output_formatter import OutputFormatter


class AppRenderer:
    @staticmethod
    def render(app: Any, jobs: Any, formatter_name: Optional[str]) -> Any:
        if formatter_name is not None:
            formatter = app.output_formatters.get_formatter(formatter_name)
        else:
            formatter = app.output_formatters.get_default()
        results = jobs.run(stop_on_exception=True)
        app._debug_results_last = results
        formatted = formatter.render(
            results,
            params=(app._debug_params_last if isinstance(app._debug_params_last, dict) else {}),
        )
        app._debug_output_last = formatted
        return formatted


