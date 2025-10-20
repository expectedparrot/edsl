"""MacroRunOutput wraps Results and provides lazy-evaluated access to output formats."""
from typing import TYPE_CHECKING, Any, Optional
from ..base import Base

if TYPE_CHECKING:
    from ..results import Results
    from .output_formatter import OutputFormatters


class MacroRunOutput(Base):
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

    def to_dict(self, add_edsl_version: bool = False) -> dict[str, Any]:
        """Serialize this object to a dictionary.

        Args:
            add_edsl_version: Whether to include EDSL version information in the output.
                Defaults to False.

        Returns:
            A dictionary representation of the MacroRunOutput object.
        """
        d = {
            "results": self._results.to_dict(add_edsl_version=False),
            "formatters": self._formatters.to_dict(),
            "params": self._params,
            "default_formatter_name": self._default_formatter_name,
        }
        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "MacroRunOutput":
        """Create a MacroRunOutput instance from a dictionary.

        Args:
            data: Dictionary containing MacroRunOutput data.

        Returns:
            A new MacroRunOutput object created from the dictionary data.
        """
        from ..results import Results
        from .output_formatter import OutputFormatters

        results = Results.from_dict(data["results"])
        formatters = OutputFormatters.from_dict(data["formatters"])
        params = data["params"]
        default_formatter_name = data.get("default_formatter_name")

        return cls(results, formatters, params, default_formatter_name)

    @classmethod
    def example(cls) -> "MacroRunOutput":
        """Create an example MacroRunOutput instance.

        Returns:
            A sample MacroRunOutput object for testing and demonstration purposes.
        """
        from ..results import Results
        from .output_formatter import OutputFormatters, OutputFormatter

        # Create example results
        results = Results.example()

        # Create simple example formatters
        class ExampleFormatter(OutputFormatter):
            """Example formatter for demonstration."""

            def __init__(self):
                super().__init__(description="example")

            def render(self, results: Results, params: dict) -> str:
                return f"Example output with {len(results)} results"

        formatters = OutputFormatters(data=[ExampleFormatter()], default="example")
        params = {"text": "example"}

        return cls(results, formatters, params, default_formatter_name="example")

    def code(self) -> str:
        """Return code to recreate this MacroRunOutput object.

        Note: This method is not fully implemented as MacroRunOutput objects
        are typically created as the result of running a Macro, not directly
        instantiated. Access the underlying results via the .results property.

        Returns:
            A message indicating how to access the results.
        """
        return (
            "# MacroRunOutput objects are created by running a Macro.\n"
            "# To access the underlying results:\n"
            "# results = macro_output.results\n"
            f"# This output contains {len(self._results)} result(s)\n"
            f"# Available formats: {list(self._formatters.mapping.keys())}"
        )

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the MacroRunOutput object.

        This representation can be used with eval() to recreate the MacroRunOutput object.
        Used primarily for doctests and debugging.
        """
        return (
            f"{self.__class__.__name__}("
            f"results={self._results._eval_repr_()}, "
            f"formatters={self._formatters._eval_repr_()}, "
            f"params={repr(self._params)}, "
            f"default_formatter_name={repr(self._default_formatter_name)})"
        )

    def _summary_repr(self) -> str:
        """Generate a summary representation of the MacroRunOutput with Rich formatting.

        Returns:
            A formatted string representation showing available output formats.
        """
        from rich.console import Console
        from rich.text import Text
        import io

        formatter_names = list(self._formatters.mapping.keys())
        default = self._default_formatter_name or self._formatters.default

        # Build the Rich text
        output = Text()
        output.append("MacroRunOutput(\n", style="bold cyan")

        # Number of results
        num_results = len(self._results) if hasattr(self._results, "__len__") else "?"
        output.append(f"    results: {num_results} result(s),\n", style="green")

        # Number of formatters
        output.append(
            f"    formatters: {len(formatter_names)} available format(s),\n",
            style="magenta",
        )

        # List formatters
        if formatter_names:
            output.append("    available formats:\n", style="white")
            for name in formatter_names:
                formatter = self._formatters.mapping[name]
                desc = getattr(formatter, "description", name)
                is_default = " (default)" if name == default else ""

                output.append("        • ", style="white")
                output.append(f"{name}", style="bold yellow")
                if is_default:
                    output.append(is_default, style="bold green")
                output.append(f": {desc}\n", style="white")

        output.append("\n    ", style="white")
        output.append("Access formats via: ", style="dim")
        output.append("output.<format_name>", style="bold blue")

        output.append("\n    ", style="white")
        output.append("Access underlying results: ", style="dim")
        output.append("output.results", style="bold blue")

        output.append("\n)", style="bold cyan")

        # Render to string
        string_io = io.StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        console.print(output, end="")
        return string_io.getvalue()
