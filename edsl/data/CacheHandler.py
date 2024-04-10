from __future__ import annotations
import ast
import json
import os
import shutil
import sqlite3
from edsl.config import CONFIG
from edsl.data.Cache import Cache
from edsl.data.CacheEntry import CacheEntry
from edsl.data.SQLiteDict import SQLiteDict


class CacheHandler:
    """
    This CacheHandler figures out what caches are available and does migrations, as needed.
    """

    CACHE_PATH = CONFIG.get("EDSL_DATABASE_PATH")

    def __init__(self, test: bool = False):
        self.test = test
        self.create_cache_directory()
        self.cache = self.gen_cache()
        old_data = self.from_old_sqlite_cache()
        self.cache.add_from_dict(old_data)

    def create_cache_directory(self) -> None:
        """
        Create the cache directory if one is required and it does not exist.
        """
        path = self.CACHE_PATH.replace("sqlite:///", "")
        dir_path = os.path.dirname(path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"Created cache directory: {dir_path}")

    def gen_cache(self) -> Cache:
        """
        Generate a Cache object.
        """
        if self.test:
            return Cache(data={})
        cache = Cache(data=SQLiteDict(self.CACHE_PATH))
        return cache

    def from_old_sqlite_cache(
        self, path: str = "edsl_cache.db"
    ) -> dict[str, CacheEntry]:
        """
        Convert an old-style cache to the new format.
        - NB: Not worth converting to sqlalchemy - this is a one-time operation.
        """
        old_data = {}
        if not os.path.exists(os.path.join(os.getcwd(), path)):
            return old_data
        try:
            conn = sqlite3.connect(path)
            with conn:
                cur = conn.cursor()
                table_name = "responses"
                cur.execute(f"PRAGMA table_info({table_name})")
                columns = cur.fetchall()
                schema = {column[1]: column[2] for column in columns}
                data = cur.execute(f"SELECT * FROM {table_name}").fetchall()
                for row in data:
                    entry = self._parse_old_cache_entry(row, schema)
                    old_data[entry.key] = entry
            print(
                f"Found old cache at {path} with {len(old_data)} entries.\n"
                f"We will convert this to the new cache format.\n"
                f"The old cache is backed up to {path}.bak"
            )
            shutil.copy(path, f"{path}.bak")
            os.remove(path)
        except sqlite3.OperationalError:
            print("Found an old Cache but could not convert it to new format.")

        return old_data

    def _parse_old_cache_entry(self, row: tuple, schema) -> CacheEntry:
        """
        Parse an old cache entry.
        """
        entry_dict = {k: row[i] for i, k in enumerate(schema.keys())}
        _ = entry_dict.pop("id")
        entry_dict["user_prompt"] = entry_dict.pop("prompt")
        parameters = entry_dict["parameters"]
        entry_dict["parameters"] = ast.literal_eval(parameters)
        entry = CacheEntry(**entry_dict)
        return entry

    def get_cache(self) -> Cache:
        return self.cache

    ###############
    # NOT IN USE
    ###############
    def from_sqlite(uri="new_edsl_cache.db") -> dict[str, CacheEntry]:
        """
        Read in a new-style sqlite cache and return a dictionary of dictionaries.
        """
        conn = sqlite3.connect(uri)
        with conn:
            cur = conn.cursor()
            data = cur.execute("SELECT key, value FROM data").fetchall()
            newdata = {}
            for _, value in data:
                entry = CacheEntry.from_dict(json.loads(value))
                newdata[entry.key] = entry
        return newdata

    def from_jsonl(filename="edsl_cache.jsonl") -> dict[str, CacheEntry]:
        """Read in a jsonl file and return a dictionary of CacheEntry objects."""
        with open(filename, "a+") as f:
            f.seek(0)
            lines = f.readlines()
        newdata = {}
        for line in lines:
            d = json.loads(line)
            key = list(d.keys())[0]
            value = list(d.values())[0]
            newdata[key] = CacheEntry.from_dict(value)
        return newdata


if __name__ == "__main__":
    ch = CacheHandler()
