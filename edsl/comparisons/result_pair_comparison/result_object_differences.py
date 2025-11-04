from typing import TYPE_CHECKING, Optional, Dict, Sequence, Any
from collections import UserDict

if TYPE_CHECKING:
    from rich.console import Console


class ResultObjectDifferences(UserDict):
    """A dictionary of differences between two Result objects."""

    def __init__(self, diff_keys: Sequence[str], data: Dict[str, Any]):
        self.diff_keys = diff_keys
        self.data = data
        super().__init__(data)

    @classmethod
    def example(cls) -> "ResultObjectDifferences":
        """Create an example ResultObjectDifferences object."""
        from ...results.results import Results

        r1 = Results.example()[0]
        r2 = Results.example()[1]
        return cls.from_comparison(r1, r2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the ResultObjectDifferences object to a dictionary."""
        return {
            "diff_keys": self.diff_keys,
            "data": [obj.to_dict() for obj in self.data.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResultObjectDifferences":
        """Create a ResultObjectDifferences object from a dictionary."""
        from ...base import BaseDiff

        return cls(data["diff_keys"], [BaseDiff.from_dict(obj) for obj in data["data"]])

    @classmethod
    def from_comparison(
        cls, result_A, results_B, diff_keys: Sequence[str] | None = None
    ) -> "ResultObjectDifferences":
        """Create a ResultDifferences object from a ResultPairComparison object."""
        data = {}
        diff_keys = diff_keys or ("scenario", "agent", "model")
        for key in diff_keys:
            diff_obj = result_A[key] - results_B[key]
            if diff_obj is None:
                diff_obj = None
            else:
                diff_obj = diff_obj
            data[key] = diff_obj

        return cls(diff_keys, data)

    def _summary_repr(self, console: Optional["Console"] = None) -> None:
        from rich.console import Console

        if console is None:
            console = Console()
        for key in self.diff_keys:
            diff_obj = self.get(key, None)
            if diff_obj is None:
                console.print(f"[red]No diff available for '{key}'[/red]")
            else:
                console.print(f"[bold]{key.title()} difference:[/bold]")
                if hasattr(diff_obj, "pretty_print"):
                    diff_obj.pretty_print()
                else:
                    console.print(str(diff_obj))


if __name__ == "__main__":
    rd = ResultObjectDifferences.example()
    rd._summary_repr()
