"""Serialization functionality for Results objects.

This module provides the ResultsSerializer class which handles serialization and
deserialization operations for Results objects, including dictionary conversion,
object reconstruction, shelve operations, and disk persistence.

Inline JSONL format:
  - Line 1: header (``__header__: true``, class name, version, n_results, format)
  - Line 2: manifest (created_columns, name, n_survey_lines, n_cache_lines)
  - Lines 3..S+2: Survey JSONL lines (inline)
  - Lines S+3..S+C+2: Cache JSONL lines (inline, 0 lines if empty)
  - Lines S+C+3..: Result rows (one Result.to_dict() per line)
"""

import json
from pathlib import Path
from typing import Iterable, Optional, Union, TYPE_CHECKING, Any, Dict
from ..utilities import remove_edsl_version

if TYPE_CHECKING:
    from .results import Results
    from .result import Result

from .exceptions import ResultsDeserializationError


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


class ResultsSerializer:
    """Handles serialization and deserialization operations for Results objects.

    This class encapsulates all the serialization logic for Results objects,
    including conversion to and from dictionary representations for storage
    and transmission.

    Attributes:
        results: The Results object to serialize
    """

    def __init__(self, results: "Results"):
        """Initialize the serializer with a Results object.

        Args:
            results: The Results object to serialize
        """
        self.results = results

    def to_dict(
        self,
        sort: bool = False,
        add_edsl_version: bool = True,
        include_cache: bool = True,
        include_task_history: bool = False,
        include_cache_info: bool = True,
        offload_scenarios: bool = True,
        full_dict: bool = False,
    ) -> Dict[str, Any]:
        """Convert the Results object to a dictionary representation.

        Args:
            sort: Whether to sort the results data by hash before serialization
            add_edsl_version: Whether to include the EDSL version in the output
            include_cache: Whether to include cache data in the output
            include_task_history: Whether to include task history in the output
            include_cache_info: Whether to include cache information in result data
            offload_scenarios: Whether to optimize scenarios before serialization

        Returns:
            dict[str, Any]: Dictionary representation of the Results object
        """
        from ..caching import Cache

        if offload_scenarios:
            self.results.optimzie_scenarios()
        if sort:
            data = sorted(
                [result for result in self.results.data], key=lambda x: hash(x)
            )
        else:
            data = [result for result in self.results.data]

        d = {
            "data": [
                result.to_dict(
                    add_edsl_version=add_edsl_version,
                    include_cache_info=include_cache_info,
                )
                for result in data
            ],
            "survey": self.results.survey.to_dict(add_edsl_version=add_edsl_version),
            "created_columns": self.results.created_columns,
        }
        if include_cache:
            d.update(
                {
                    "cache": (
                        Cache()
                        if not hasattr(self.results, "cache")
                        else self.results.cache.to_dict(
                            add_edsl_version=add_edsl_version
                        )
                    )
                }
            )
        if self.results.name is not None:
            d["name"] = self.results.name

        if self.results.task_history.has_unfixed_exceptions or include_task_history:
            d.update(
                {
                    "task_history": self.results.task_history.to_dict(
                        offload_content=True
                    )
                }
            )

        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Results"

        return d

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: Dict[str, Any]) -> "Results":
        """Convert a dictionary to a Results object.

        Args:
            data: A dictionary representation of a Results object.

        Returns:
            Results: A new Results object created from the dictionary data

        Raises:
            ResultsDeserializationError: If there's an error during deserialization

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> d = r.to_dict()
            >>> r2 = Results.from_dict(d)
            >>> r == r2
            True
        """
        # Import here to avoid circular imports
        from .results import Results
        from ..surveys import Survey
        from ..caching import Cache
        from .result import Result
        from ..tasks import TaskHistory

        survey = Survey.from_dict(data["survey"])
        # Convert dictionaries to Result objects
        results_data = [Result.from_dict(r) for r in data["data"]]
        created_columns = data.get("created_columns", None)
        cache = Cache.from_dict(data.get("cache")) if "cache" in data else Cache()
        task_history = (
            TaskHistory.from_dict(data.get("task_history"))
            if "task_history" in data
            else TaskHistory(interviews=[])
        )
        name = data.get("name", None)

        # Create a Results object with original order preserved
        # using the empty data list initially
        params = {
            "survey": survey,
            "data": [],  # Start with empty data
            "created_columns": created_columns,
            "cache": cache,
            "task_history": task_history,
            "name": name,
        }

        try:
            results = Results(**params)
            # Add each result individually to respect order attributes
            for result in results_data:
                results.append(result)
        except Exception as e:
            raise ResultsDeserializationError(f"Error in Results.from_dict: {e}")
        return results

    # ------------------------------------------------------------------
    # Inline JSONL serialization
    # ------------------------------------------------------------------

    def to_jsonl_rows(self, blob_writer=None):
        """Yield JSONL rows for inline format.

        Format:
          - Line 1: header
          - Line 2: manifest (line counts + metadata)
          - Survey lines (from Survey.to_jsonl_rows())
          - Cache lines (from Cache.to_jsonl_rows(), skipped if empty)
          - Result rows (one Result.to_dict() per line)
        """
        from .. import __version__
        from ..caching import Cache

        # Collect survey and cache rows first to get counts
        survey_rows = list(self.results.survey.to_jsonl_rows(blob_writer=blob_writer))

        has_cache = hasattr(self.results, "cache") and len(self.results.cache) > 0
        cache_rows = list(self.results.cache.to_jsonl_rows(blob_writer=blob_writer)) if has_cache else []

        # Header
        yield json.dumps({
            "__header__": True,
            "edsl_class_name": "Results",
            "edsl_version": __version__,
            "n_results": len(self.results.data),
            "format": "inline",
        })

        # Manifest
        yield json.dumps({
            "created_columns": self.results.created_columns,
            "name": self.results.name,
            "n_survey_lines": len(survey_rows),
            "n_cache_lines": len(cache_rows),
        })

        # Survey lines
        yield from survey_rows

        # Cache lines
        yield from cache_rows

        # Result rows
        for result in self.results.data:
            yield json.dumps(result.to_dict(add_edsl_version=True))

    def to_jsonl(
        self,
        filename: Union[str, Path, None] = None,
        **kwargs,
    ) -> Optional[str]:
        """Export as inline JSONL.

        Format:
          - Line 1: header
          - Line 2: manifest (line counts + metadata)
          - Survey lines inline
          - Cache lines inline (if non-empty)
          - Result rows
        """
        content = "\n".join(self.to_jsonl_rows()) + "\n"

        if filename is not None:
            with open(filename, "w") as f:
                f.write(content)
            return None
        return content

    @staticmethod
    def from_jsonl(
        source: Union[str, Path, Iterable[str]], **kwargs
    ) -> "Results":
        """Create a Results instance from an inline JSONL source.

        Reads the manifest to determine line counts for Survey and Cache
        sections, then parses each section from the inline content.
        """
        from .results import Results
        from .result import Result
        from ..surveys import Survey
        from ..caching import Cache
        from ..tasks import TaskHistory

        lines = [l.rstrip("\n") for l in _open_lines(source) if l.strip()]

        _header = json.loads(lines[0])
        manifest = json.loads(lines[1])

        n_survey = manifest["n_survey_lines"]
        n_cache = manifest["n_cache_lines"]

        # Survey section starts at line index 2
        survey_lines = lines[2 : 2 + n_survey]
        survey = Survey.from_jsonl(survey_lines)

        # Cache section
        if n_cache > 0:
            cache_start = 2 + n_survey
            cache_lines = lines[cache_start : cache_start + n_cache]
            cache = Cache.from_jsonl(cache_lines)
        else:
            cache = Cache()

        created_columns = manifest.get("created_columns", [])
        name = manifest.get("name", None)

        # Result rows
        result_start = 2 + n_survey + n_cache
        results_data = [
            Result.from_dict(json.loads(line))
            for line in lines[result_start:]
            if line.strip()
        ]

        results = Results(
            survey=survey,
            data=[],
            created_columns=created_columns,
            cache=cache,
            task_history=TaskHistory(interviews=[]),
            name=name,
        )
        for result in results_data:
            results.append(result)

        return results

