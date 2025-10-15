"""MacroRunOutput wraps Results and provides lazy-evaluated access to output formats."""
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..results import Results
    from .output_formatter import OutputFormatters


class MacroRunOutput:
    """Wraps Results and provides lazy access to different output formats.

    This class allows users to see available output formats and access them
    via dot notation (e.g., output.table, output.raw_results).

    Example:
        >>> from edsl.macros import Macro
        >>> macro = Macro.example()
        >>> output = macro.run(text="hello")  # doctest: +SKIP
        >>> output  # Shows available formats  # doctest: +SKIP
        >>> output.table  # Returns table format  # doctest: +SKIP
        >>> output.raw_results  # Returns raw results  # doctest: +SKIP
    """

    def __init__(
        self,
        results: "Results",
        formatters: "OutputFormatters",
        params: dict[str, Any],
        default_formatter_name: Optional[str] = None,
    ):
        """Initialize MacroRunOutput.

        Args:
            results: The Results object from running the macro.
            formatters: The OutputFormatters instance containing available formatters.
            params: The params dict that was used to generate these results.
            default_formatter_name: The name of the default formatter to use.
        """
        self._results = results
        self._formatters = formatters
        self._params = params
        self._default_formatter_name = default_formatter_name
        self._cache: dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        """Lazily evaluate and return the formatted output for the given formatter name.
        
        Args:
            name: The formatter name to use.
            
        Returns:
            The formatted output.
            
        Raises:
            AttributeError: If the formatter name is not found.
        """
        # Check if this is a valid formatter name
        if name in self._formatters.mapping:
            # Check cache first
            if name not in self._cache:
                # Lazily evaluate and cache
                formatter = self._formatters.get_formatter(name)
                self._cache[name] = formatter.render(
                    self._results, params={"params": self._params}
                )
            return self._cache[name]
        
        # Not a formatter, raise AttributeError
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'. "
            f"Available formatters: {list(self._formatters.mapping.keys())}"
        )

    def __repr__(self) -> str:
        """Return a string representation showing available formatters."""
        formatter_names = list(self._formatters.mapping.keys())
        default = self._default_formatter_name or self._formatters.default
        
        lines = [
            f"MacroRunOutput with {len(formatter_names)} available format(s):",
            "",
        ]
        
        for name in formatter_names:
            formatter = self._formatters.mapping[name]
            desc = getattr(formatter, "description", name)
            is_default = " (default)" if name == default else ""
            lines.append(f"  • {name}{is_default}: {desc}")
        
        lines.append("")
        lines.append(f"Access formats via: output.<format_name>")
        
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        """Return an HTML representation showing available formatters."""
        formatter_names = list(self._formatters.mapping.keys())
        default = self._default_formatter_name or self._formatters.default
        
        rows = []
        for name in formatter_names:
            formatter = self._formatters.mapping[name]
            desc = getattr(formatter, "description", name)
            is_default = " ⭐" if name == default else ""
            
            rows.append(
                f"<tr>"
                f"<td><code>output.{name}</code></td>"
                f"<td>{desc}{is_default}</td>"
                f"</tr>"
            )
        
        html = f"""
        <div style="font-family: sans-serif; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9;">
            <h3 style="margin-top: 0;">MacroRunOutput</h3>
            <p><strong>{len(formatter_names)}</strong> available output format(s):</p>
            <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                <thead>
                    <tr style="background-color: #e9e9e9;">
                        <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Access</th>
                        <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Description</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
            <p style="margin-top: 15px; font-size: 0.9em; color: #666;">
                ⭐ = default format | Access any format via: <code>output.&lt;format_name&gt;</code>
            </p>
        </div>
        """
        return html

    @property
    def results(self) -> "Results":
        """Direct access to the underlying Results object."""
        return self._results
    
    @property
    def formatters(self) -> "OutputFormatters":
        """Direct access to the OutputFormatters object."""
        return self._formatters

