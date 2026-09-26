"""Jobs JSONL serialization.

JSONL format:
  - Line 1: metadata header (``__header__: true``, class name, version)
  - Line 2: inline Jobs dictionary representation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .jobs import Jobs


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


def _restore_post_run_methods(value: list) -> list:
    restored = []
    for item in value:
        if isinstance(item, list) and len(item) == 3:
            restored.append((item[0], tuple(item[1]), item[2]))
        else:
            restored.append(item)
    return restored


def _restore_json_round_trip_types(job: "Jobs") -> None:
    if job._post_run_methods:
        job._post_run_methods = _restore_post_run_methods(job._post_run_methods)
    if job._depends_on is not None:
        _restore_json_round_trip_types(job._depends_on)


class JobsSerializer:
    """JSONL serialization for Jobs objects."""

    def __init__(self, jobs: "Jobs") -> None:
        self._jobs = jobs

    # ------------------------------------------------------------------
    # export
    # ------------------------------------------------------------------

    def _build_header(self) -> dict:
        from edsl import __version__

        return {
            "__header__": True,
            "edsl_class_name": "Jobs",
            "edsl_version": __version__,
        }

    def to_jsonl(
        self,
        filename: Union[str, Path, None] = None,
        root=None,
        message: str = "",
    ) -> Optional[str]:
        """Export as JSONL string or write to *filename*."""
        header = json.dumps(self._build_header())
        payload = json.dumps(self._jobs.to_dict(add_edsl_version=True))
        content = header + "\n" + payload + "\n"

        if filename is not None:
            with open(filename, "w") as f:
                f.write(content)
            return None
        return content

    # ------------------------------------------------------------------
    # import
    # ------------------------------------------------------------------

    @staticmethod
    def from_jsonl(source: Union[str, Path, Iterable[str]], root=None) -> "Jobs":
        """Create a Jobs instance from a JSONL source."""
        from .jobs import Jobs

        line_iter = iter(_open_lines(source))
        _header = json.loads(next(line_iter))  # noqa: F841
        payload = json.loads(next(line_iter))
        job = Jobs.from_dict(payload)
        _restore_json_round_trip_types(job)
        return job
