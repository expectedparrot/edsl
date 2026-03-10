"""ScenarioList JSONL serialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generator, Iterable, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .scenario import Scenario
    from .scenario_list import ScenarioList


class ScenarioListSerializer:
    """JSONL serialization for ScenarioList objects.

    JSONL format:
      - Line 1: metadata header (``__header__: true``, class name, count, codebook)
      - Lines 2+: one Scenario per line (``to_dict(add_edsl_version=False)``)
    """

    def __init__(self, scenario_list: "ScenarioList") -> None:
        self._scenario_list = scenario_list

    # ------------------------------------------------------------------
    # export
    # ------------------------------------------------------------------

    def _build_metadata(self, add_edsl_version: bool = True) -> dict:
        meta: dict = {
            "__header__": True,
            "edsl_class_name": "ScenarioList",
            "n_scenarios": len(self._scenario_list),
        }
        if add_edsl_version:
            from edsl import __version__

            meta["edsl_version"] = __version__

        codebook = getattr(self._scenario_list, "codebook", None)
        if codebook:
            meta["codebook"] = codebook

        return meta

    def to_jsonl_rows(self, add_edsl_version: bool = True) -> Generator[str, None, None]:
        """Yield one JSON string per line — header then one Scenario per line."""
        yield json.dumps(self._build_metadata(add_edsl_version))
        for scenario in self._scenario_list:
            yield json.dumps(scenario.to_dict(add_edsl_version=False))

    def to_jsonl(self, filename: Union[str, Path, None] = None) -> Optional[str]:
        """Export as JSONL string or write to *filename*.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([Scenario({'food': 'pizza'}), Scenario({'food': 'tacos'})])
            >>> text = sl.to_jsonl()
            >>> lines = text.strip().splitlines()
            >>> len(lines)
            3
            >>> import json; json.loads(lines[0])['n_scenarios']
            2
        """
        if filename is not None:
            with open(filename, "w") as f:
                for row in self.to_jsonl_rows():
                    f.write(row + "\n")
            return None
        return "\n".join(self.to_jsonl_rows()) + "\n"

    # ------------------------------------------------------------------
    # import (static — no instance needed)
    # ------------------------------------------------------------------

    @staticmethod
    def _open_lines(source: Union[str, Path, Iterable[str]]) -> Iterable[str]:
        """Normalise *source* into an iterable of lines."""
        if isinstance(source, Path):
            with open(source, "r") as fh:
                yield from fh
            return

        if isinstance(source, str):
            if "\n" not in source.rstrip("\n"):
                candidate = Path(source)
                try:
                    if candidate.is_file():
                        with open(candidate, "r") as fh:
                            yield from fh
                        return
                except OSError:
                    pass
            yield from source.splitlines()
        else:
            yield from source

    @staticmethod
    def from_jsonl(source: Union[str, Path, Iterable[str]]) -> "ScenarioList":
        """Create a ScenarioList from a JSONL source.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([Scenario({'food': 'pizza'}), Scenario({'food': 'tacos'})])
            >>> sl2 = ScenarioList.from_jsonl(sl.to_jsonl())
            >>> sl == sl2
            True
        """
        from .scenario import Scenario
        from .scenario_list import ScenarioList

        lines = ScenarioListSerializer._open_lines(source)
        line_iter = iter(lines)
        meta = json.loads(next(line_iter))
        scenarios = [
            Scenario.from_dict(json.loads(line))
            for line in line_iter
            if line.strip()
        ]
        codebook = meta.get("codebook") or None
        return ScenarioList(scenarios, codebook=codebook)

    @staticmethod
    def iter_scenarios_from_jsonl(
        source: Union[str, Path, Iterable[str]],
    ) -> Generator["Scenario", None, None]:
        """Lazily yield Scenario objects from a JSONL source."""
        from .scenario import Scenario

        lines = ScenarioListSerializer._open_lines(source)
        line_iter = iter(lines)
        next(line_iter)  # skip header
        for line in line_iter:
            if line.strip():
                yield Scenario.from_dict(json.loads(line))


if __name__ == "__main__":
    import doctest

    doctest.testmod()
