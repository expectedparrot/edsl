from typing import List, Optional, Union
from pathlib import Path
import sqlite3
from datetime import datetime
import tempfile
from platformdirs import user_cache_dir
import os

from .data_structures import LanguageModelInfo, AvailableModels
from ..enums import InferenceServiceLiteral


class AvailableModelCacheHandler:
    MAX_ROWS = 1000
    CACHE_VALIDITY_HOURS = 48

    def __init__(
        self,
        cache_validity_hours: int = 48,
        verbose: bool = False,
        testing_db_name: str = None,
    ):
        self.cache_validity_hours = cache_validity_hours
        self.verbose = verbose

        if testing_db_name:
            self.cache_dir = Path(tempfile.mkdtemp())
            self.db_path = self.cache_dir / testing_db_name
        else:
            self.cache_dir = Path(user_cache_dir("edsl", "model_availability"))
            self.db_path = self.cache_dir / "available_models.db"
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        if os.path.exists(self.db_path):
            if self.verbose:
                print(f"Using existing cache DB: {self.db_path}")
        else:
            self._initialize_db()

    @property
    def path_to_db(self):
        return self.db_path

    def _initialize_db(self):
        """Initialize the SQLite database with the required schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Drop the old table if it exists (for migration)
            cursor.execute("DROP TABLE IF EXISTS model_cache")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS model_cache (
                    timestamp DATETIME NOT NULL,
                    model_name TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    UNIQUE(model_name, service_name)
                )
            """
            )
            conn.commit()

    def _prune_old_entries(self, conn: sqlite3.Connection):
        """Delete oldest entries when MAX_ROWS is exceeded."""
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM model_cache")
        count = cursor.fetchone()[0]

        if count > self.MAX_ROWS:
            cursor.execute(
                """
                DELETE FROM model_cache 
                WHERE rowid IN (
                    SELECT rowid 
                    FROM model_cache 
                    ORDER BY timestamp ASC 
                    LIMIT ?
                )
            """,
                (count - self.MAX_ROWS,),
            )
            conn.commit()

    @classmethod
    def example_models(cls) -> List[LanguageModelInfo]:
        return [
            LanguageModelInfo(
                "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", "deep_infra"
            ),
            LanguageModelInfo("openai/gpt-4", "openai"),
        ]

    def add_models_to_cache(self, models_data: List[LanguageModelInfo]):
        """Add new models to the cache, updating timestamps for existing entries."""
        current_time = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for model in models_data:
                cursor.execute(
                    """
                    INSERT INTO model_cache (timestamp, model_name, service_name)
                    VALUES (?, ?, ?)
                    ON CONFLICT(model_name, service_name) 
                    DO UPDATE SET timestamp = excluded.timestamp
                """,
                    (current_time, model.model_name, model.service_name),
                )

            # self._prune_old_entries(conn)
            conn.commit()

    def reset_cache(self):
        """Clear all entries from the cache."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM model_cache")
            conn.commit()

    @property
    def num_cache_entries(self):
        """Return the number of entries in the cache."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM model_cache")
            count = cursor.fetchone()[0]
            return count

    def models(
        self,
        service: Optional[InferenceServiceLiteral],
    ) -> Union[None, AvailableModels]:
        """Return the available models within the cache validity period."""
        # if service is not None:
        #    assert service in get_args(InferenceServiceLiteral)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            valid_time = datetime.now().timestamp() - (self.cache_validity_hours * 3600)

            if self.verbose:
                print(f"Fetching all with timestamp greater than {valid_time}")

            cursor.execute(
                """
                SELECT DISTINCT model_name, service_name
                FROM model_cache
                WHERE timestamp > ?
                ORDER BY timestamp DESC
            """,
                (valid_time,),
            )

            results = cursor.fetchall()
            if not results:
                if self.verbose:
                    print("No results found in cache DB.")
                return None

            matching_models = [
                LanguageModelInfo(model_name=row[0], service_name=row[1])
                for row in results
            ]

            if self.verbose:
                print(f"Found {len(matching_models)} models in cache DB.")
            if service:
                matching_models = [
                    model for model in matching_models if model.service_name == service
                ]

            return AvailableModels(matching_models)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
    # cache_handler = AvailableModelCacheHandler(verbose=True)
    # models_data = cache_handler.example_models()
    # cache_handler.add_models_to_cache(models_data)
    # print(cache_handler.models())
    # cache_handler.clear_cache()
    # print(cache_handler.models())
