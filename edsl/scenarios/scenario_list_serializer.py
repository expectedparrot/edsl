"""ScenarioList JSONL serialization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Generator, Iterable, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .scenario import Scenario
    from .scenario_list import ScenarioList

_BLOB_SENTINEL = "__cas_blob__"
_BLOB_HASH_KEY = "__blob_hash__"


# ------------------------------------------------------------------
# FileStore blob offloading / rehydration helpers
# ------------------------------------------------------------------

def _is_filestore_dict(value: dict) -> bool:
    """Return True if *value* looks like a serialized FileStore."""
    return isinstance(value, dict) and "base64_string" in value and "path" in value


def _offload_filestores(
    scenario_dict: dict,
    blob_writer: Callable[[str], str],
) -> dict:
    """Replace FileStore base64 content with blob references.

    Walks the top-level values of *scenario_dict*.  For any value that
    is a FileStore dict (has ``base64_string`` and ``path``), the
    base64 content is passed to *blob_writer* which stores it and
    returns its SHA-256 hex hash.  The dict is modified in-place to
    replace ``base64_string`` with the sentinel and add a hash key.
    """
    for key, value in scenario_dict.items():
        if _is_filestore_dict(value):
            b64 = value["base64_string"]
            if b64 == _BLOB_SENTINEL:
                continue  # already offloaded
            blob_hash = blob_writer(b64)
            value["base64_string"] = _BLOB_SENTINEL
            value[_BLOB_HASH_KEY] = blob_hash
    return scenario_dict


def _rehydrate_filestores(
    scenario_dict: dict,
    blob_reader: Callable[[str], str],
) -> dict:
    """Replace blob references with actual base64 content."""
    for key, value in scenario_dict.items():
        if (
            isinstance(value, dict)
            and value.get("base64_string") == _BLOB_SENTINEL
            and _BLOB_HASH_KEY in value
        ):
            blob_hash = value[_BLOB_HASH_KEY]
            value["base64_string"] = blob_reader(blob_hash)
            del value[_BLOB_HASH_KEY]
    return scenario_dict


# ------------------------------------------------------------------
# Sidecar blob store (for file-based export)
# ------------------------------------------------------------------

class SidecarBlobStore:
    """Read/write blobs in a sidecar directory alongside a JSONL file."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def write_blob(self, base64_content: str) -> str:
        """Write *base64_content* and return its SHA-256 hex hash."""
        h = hashlib.sha256(base64_content.encode()).hexdigest()
        path = self.directory / h
        if not path.exists():
            path.write_text(base64_content)
        return h

    def read_blob(self, hash_hex: str) -> str:
        """Return the content for the given hash."""
        path = self.directory / hash_hex
        if not path.exists():
            raise FileNotFoundError(f"Blob {hash_hex} not found in {self.directory}")
        return path.read_text()


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

    def _build_metadata(
        self, add_edsl_version: bool = True, has_blobs: bool = False,
    ) -> dict:
        meta: dict = {
            "__header__": True,
            "edsl_class_name": "ScenarioList",
            "n_scenarios": len(self._scenario_list),
        }
        if has_blobs:
            meta["has_blobs"] = True
        if add_edsl_version:
            from edsl import __version__

            meta["edsl_version"] = __version__

        codebook = getattr(self._scenario_list, "codebook", None)
        if codebook:
            meta["codebook"] = codebook

        return meta

    def to_jsonl_rows(
        self,
        add_edsl_version: bool = True,
        blob_writer: Optional[Callable[[str], str]] = None,
    ) -> Generator[str, None, None]:
        """Yield one JSON string per line — header then one Scenario per line."""
        yield json.dumps(self._build_metadata(
            add_edsl_version, has_blobs=blob_writer is not None,
        ))
        for scenario in self._scenario_list:
            row = scenario.to_dict(add_edsl_version=False)
            if blob_writer is not None:
                row = _offload_filestores(row, blob_writer)
            yield json.dumps(row)

    def to_jsonl(
        self,
        filename: Union[str, Path, None] = None,
        blob_writer: Optional[Callable[[str], str]] = None,
    ) -> Optional[str]:
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
                for row in self.to_jsonl_rows(blob_writer=blob_writer):
                    f.write(row + "\n")
            return None
        return "\n".join(self.to_jsonl_rows(blob_writer=blob_writer)) + "\n"

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
    def from_jsonl(
        source: Union[str, Path, Iterable[str]],
        blob_reader: Optional[Callable[[str], str]] = None,
    ) -> "ScenarioList":
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
        has_blobs = meta.get("has_blobs", False)

        scenarios = []
        for line in line_iter:
            if not line.strip():
                continue
            row = json.loads(line)
            if has_blobs and blob_reader is not None:
                row = _rehydrate_filestores(row, blob_reader)
            scenarios.append(Scenario.from_dict(row))

        codebook = meta.get("codebook") or None
        return ScenarioList(scenarios, codebook=codebook)

    @staticmethod
    def iter_scenarios_from_jsonl(
        source: Union[str, Path, Iterable[str]],
        blob_reader: Optional[Callable[[str], str]] = None,
    ) -> Generator["Scenario", None, None]:
        """Lazily yield Scenario objects from a JSONL source."""
        from .scenario import Scenario

        lines = ScenarioListSerializer._open_lines(source)
        line_iter = iter(lines)
        meta = json.loads(next(line_iter))
        has_blobs = meta.get("has_blobs", False)
        for line in line_iter:
            if line.strip():
                row = json.loads(line)
                if has_blobs and blob_reader is not None:
                    row = _rehydrate_filestores(row, blob_reader)
                yield Scenario.from_dict(row)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
