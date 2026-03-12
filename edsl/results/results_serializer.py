"""Serialization functionality for Results objects.

This module provides the ResultsSerializer class which handles serialization and
deserialization operations for Results objects, including dictionary conversion,
object reconstruction, shelve operations, and disk persistence.

CAS JSONL format (Jobs-style pointers):
  - Line 1: header (``__header__: true``, class name, version, n_results)
  - Line 2: manifest with CAS pointers to Survey and Cache, plus inline metadata
  - Lines 3–N+2: one ``Result.to_dict()`` per line (inline)
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


def _component_pointer(component, name: str, root=None, message: str = "") -> dict:
    """Return a CAS pointer dict for a component, auto-saving if needed."""
    if component.store.uuid is None:
        component.store.save(message=message or f"auto-saved by Results.to_jsonl()", root=root)
    return {
        "uuid": component.store.uuid,
        "branch": component.store.current_branch,
        "commit": component.store.commit,
    }


def _save_cache_to_store(cache, root=None, message: str = "") -> dict:
    """Save a Cache to ObjectStore directly (Cache.store is shadowed by a method)."""
    from ..object_store import ObjectStore

    obj_store = ObjectStore(root) if root else ObjectStore()
    info = obj_store.save(cache, message=message or "auto-saved by Results.to_jsonl()")
    return {
        "uuid": info["uuid"],
        "branch": info["branch"],
        "commit": info["commit"],
    }


def _load_cache_from_store(pointer, root=None):
    """Load a Cache from ObjectStore by CAS pointer."""
    from ..object_store import ObjectStore

    obj_store = ObjectStore(root) if root else ObjectStore()
    cache, _meta = obj_store.load(
        pointer["uuid"],
        commit=pointer.get("commit"),
        branch=pointer.get("branch"),
    )
    return cache


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
    # CAS JSONL serialization (Jobs-style pointers)
    # ------------------------------------------------------------------

    def _build_header(self) -> dict:
        from .. import __version__

        return {
            "__header__": True,
            "edsl_class_name": "Results",
            "edsl_version": __version__,
            "n_results": len(self.results.data),
        }

    def _build_manifest(self, root=None, message: str = "") -> dict:
        """Build a manifest with CAS pointers for Survey and Cache."""
        manifest: dict = {
            "survey": _component_pointer(
                self.results.survey, "survey", root=root, message=message
            ),
            "created_columns": self.results.created_columns,
            "name": self.results.name,
        }
        # Only include cache pointer if cache is non-empty
        if hasattr(self.results, "cache") and len(self.results.cache) > 0:
            manifest["cache"] = _save_cache_to_store(
                self.results.cache, root=root, message=message
            )
        return manifest

    def to_jsonl(
        self,
        filename: Union[str, Path, None] = None,
        root=None,
        message: str = "",
        **kwargs,
    ) -> Optional[str]:
        """Export as JSONL with CAS pointers to Survey and Cache.

        Format:
          - Line 1: header
          - Line 2: manifest (CAS pointers + metadata)
          - Lines 3+: one Result.to_dict() per line
        """
        header = json.dumps(self._build_header())
        manifest = json.dumps(self._build_manifest(root=root, message=message))
        lines = [header, manifest]
        for result in self.results.data:
            lines.append(json.dumps(result.to_dict(add_edsl_version=True)))
        content = "\n".join(lines) + "\n"

        if filename is not None:
            with open(filename, "w") as f:
                f.write(content)
            return None
        return content

    @staticmethod
    def from_jsonl(
        source: Union[str, Path, Iterable[str]], root=None, **kwargs
    ) -> "Results":
        """Create a Results instance from a CAS JSONL source.

        Survey and Cache are loaded from the ObjectStore by their CAS pointers.
        Result objects are read inline from the remaining lines.
        """
        from .results import Results
        from .result import Result
        from ..surveys import Survey
        from ..caching import Cache
        from ..tasks import TaskHistory

        line_iter = iter(_open_lines(source))
        _header = json.loads(next(line_iter))  # noqa: F841
        manifest = json.loads(next(line_iter))

        # Load survey from CAS
        survey_ptr = manifest["survey"]
        survey = Survey.store.load(
            survey_ptr["uuid"],
            commit=survey_ptr["commit"],
            branch=survey_ptr["branch"],
            root=root,
        )

        # Load cache from CAS (if pointer exists)
        if "cache" in manifest:
            cache = _load_cache_from_store(manifest["cache"], root=root)
        else:
            cache = Cache()

        created_columns = manifest.get("created_columns", [])
        name = manifest.get("name", None)

        # Read inline Result objects
        results_data = []
        for line in line_iter:
            line = line.strip()
            if not line:
                continue
            results_data.append(Result.from_dict(json.loads(line)))

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

