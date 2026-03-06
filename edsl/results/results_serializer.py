"""Serialization functionality for Results objects.

This module provides the ResultsSerializer class which handles serialization and
deserialization operations for Results objects, including dictionary conversion,
object reconstruction, shelve operations, and disk persistence.
"""

from typing import TYPE_CHECKING, Any, Dict
from ..utilities import remove_edsl_version

if TYPE_CHECKING:
    from .results import Results
    from .result import Result

from .exceptions import ResultsDeserializationError, ResultsError


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

    def to_disk(self, filepath: str) -> None:
        """Serialize the Results object to a zip file, preserving the SQLite database.

        Creates a zip file containing:
        1. The SQLite database file from the data container
        2. A metadata.json file with the survey, created_columns, and other non-data info
        3. The cache data if present

        Args:
            filepath: Path where the zip file should be saved

        Raises:
            ResultsError: If there's an error during serialization
        """
        import zipfile
        import json
        import os
        import tempfile
        from pathlib import Path
        import shutil
        from .utilities import ResultsSQLList

        data_class = ResultsSQLList

        try:
            # Create a temporary directory to store files before zipping
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # 1. Handle the SQLite database
                db_path = temp_path / "results.db"

                if isinstance(self.results.data, list):
                    # If data is a list, create a new SQLiteList
                    new_db = data_class()
                    new_db.extend(self.results.data)
                    shutil.copy2(new_db.db_path, db_path)
                elif hasattr(self.results.data, "db_path") and os.path.exists(
                    self.results.data.db_path
                ):
                    # If data is already a SQLiteList, copy its database
                    shutil.copy2(self.results.data.db_path, db_path)
                else:
                    # If no database exists, create a new one
                    new_db = data_class()
                    new_db.extend(self.results.data)
                    shutil.copy2(new_db.db_path, db_path)

                # 2. Create metadata.json
                metadata = {
                    "survey": (
                        self.results.survey.to_dict() if self.results.survey else None
                    ),
                    "created_columns": self.results.created_columns,
                    "cache": (
                        self.results.cache.to_dict()
                        if hasattr(self.results, "cache")
                        else None
                    ),
                    "task_history": (
                        self.results.task_history.to_dict()
                        if hasattr(self.results, "task_history")
                        else None
                    ),
                    "completed": self.results.completed,
                    "job_uuid": (
                        self.results._job_uuid
                        if hasattr(self.results, "_job_uuid")
                        else None
                    ),
                    "total_results": (
                        self.results._total_results
                        if hasattr(self.results, "_total_results")
                        else None
                    ),
                }

                metadata_path = temp_path / "metadata.json"
                metadata_path.write_text(json.dumps(metadata, indent=4))

                # 3. Create the zip file
                with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zipf:
                    # Add all files from temp directory to zip
                    for file in temp_path.glob("*"):
                        zipf.write(file, file.name)

        except Exception as e:
            raise ResultsError(f"Error saving Results to disk: {str(e)}")

    @classmethod
    def from_disk(cls, filepath: str) -> "Results":
        """Load a Results object from a zip file.

        Extracts the SQLite database file, loads the metadata,
        and creates a new Results instance with the restored data.

        Args:
            filepath: Path to the zip file containing the serialized Results

        Returns:
            Results: A new Results instance with the restored data

        Raises:
            ResultsError: If there's an error during deserialization
        """
        import zipfile
        import json
        import tempfile
        from pathlib import Path
        from ..surveys import Survey
        from ..caching import Cache
        from ..tasks import TaskHistory
        from .utilities import ResultsSQLList

        data_class = ResultsSQLList

        try:
            # Import here to avoid circular imports
            from .results import Results

            # Create a temporary directory to extract files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract the zip file
                with zipfile.ZipFile(filepath, "r") as zipf:
                    zipf.extractall(temp_path)

                # 1. Load metadata
                metadata_path = temp_path / "metadata.json"
                metadata = json.loads(metadata_path.read_text())

                # 2. Create a new Results instance
                results = Results(
                    survey=(
                        Survey.from_dict(metadata["survey"])
                        if metadata["survey"]
                        else None
                    ),
                    created_columns=metadata["created_columns"],
                    cache=(
                        Cache.from_dict(metadata["cache"])
                        if metadata["cache"]
                        else None
                    ),
                    task_history=(
                        TaskHistory.from_dict(metadata["task_history"])
                        if metadata["task_history"]
                        else None
                    ),
                    job_uuid=metadata["job_uuid"],
                    total_results=metadata["total_results"],
                )

                # 3. Set the SQLite database path if it exists
                db_path = temp_path / "results.db"
                if db_path.exists():
                    # Create a new ResultsSQLList instance
                    new_db = data_class()
                    # Copy data from the source database - convert Path to string
                    new_db.copy_from(str(db_path))
                    # Set the new database as the results data
                    results.data = new_db

                results.completed = metadata["completed"]
                return results

        except Exception as e:
            raise ResultsError(f"Error loading Results from disk: {str(e)}")
