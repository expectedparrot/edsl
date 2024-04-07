from __future__ import annotations
import os
import json
import shutil
import sqlite3
import ast
from pathlib import Path
from textwrap import dedent

from typing import Literal
from edsl.config import CONFIG
from edsl.data.CacheEntry import CacheEntry
from edsl.data.Cache import Cache
from edsl.data.SQLiteDict import SQLiteDict

#EDSL_DATABASE_PATH = CONFIG.get("EDSL_DATABASE_PATH")

# TODO: Use the .env file to get the path to the database.
EDSL_DATABASE_PATH = ".edsl_cache/data.db"

class CacheHandler:
    """
    This CacheHandler figures out what caches are availalble and does migrations, as needed.
    """

    CACHE_PATH = ".edsl_cache/data.db"
    OLD_CACHE = "edsl_cache.db"

    def __init__(self):

        self.create_cache_directory()

        if os.path.exists(os.path.join(os.getcwd(), self.OLD_CACHE)):
            try:
                newdata = self.from_old_sqlite_cache_db(self.OLD_CACHE)
                print(dedent(f"""\
                Found old cache at {self.OLD_CACHE} with {len(newdata)} entries. 
                We will convert this to the new cache format.
                The old cache is backed up to {self.OLD_CACHE}.bak"""))
                shutil.copy(self.OLD_CACHE, self.OLD_CACHE + ".bak")
                os.remove(self.OLD_CACHE)
            except sqlite3.OperationalError:
                print("Found an old Cache but could not convert old cache to new format.")
                newdata = {}
        else:
            newdata = {}

        self.cache = self.gen_cache()
        self.cache.add_from_dict(newdata)

    def get_cache(self) -> Cache:
        return self.cache

    def gen_cache(self) -> Cache:
        """Generate a cache object."""
        uri = "sqlite:///" + os.path.join(os.getcwd(), EDSL_DATABASE_PATH)
        cache = Cache(data = SQLiteDict(uri))
        return cache

    def create_cache_directory(self) -> None:
        """Create the cache directory if it does not exist."""
        #directory_path = EDSL_DATABASE_PATH.replace("sqlite:///", "")
        directory_path = ".edsl_cache"
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
            print(f"Created directory: {directory_path}")

    def from_old_sqlite_cache_db(self, uri="edsl_cache.db") -> dict[str, CacheEntry]:
        """If there is an old-style cache, read that in and convert it to the new format.
        
        NB: Not worth converting to sqlalchemy - this is a one-time operation.
        """
        conn = sqlite3.connect(uri)
        with conn:
            cur = conn.cursor()        
            table_name = "responses"  
            cur.execute(f"PRAGMA table_info({table_name})")
            columns = cur.fetchall()
            schema = {column[1]: column[2] for column in columns}
            data = cur.execute(f"SELECT * FROM {table_name}").fetchall()
            newdata = {}
            for row in data:
                entry = self._parse_old_cache_entry(row, schema)
                newdata[entry.key] = entry
        return newdata
    
    def _parse_old_cache_entry(self, row: tuple, schema) -> CacheEntry:
        """Parse an old cache entry."""
        entry_dict = {k: row[i] for i, k in enumerate(schema.keys())}
        _ = entry_dict.pop("id")
        entry_dict["user_prompt"] = entry_dict.pop("prompt")
        parameters = entry_dict["parameters"]
        entry_dict["parameters"] = ast.literal_eval(parameters)
        entry = CacheEntry(**entry_dict)
        return entry

    def from_new_sqlite_cache_db(uri="new_edsl_cache.db") -> dict[str, CacheEntry]:
        """Read in a new-style sqlite cache and return a dictionary of dictionaries."""
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

    #print(ch.data)
