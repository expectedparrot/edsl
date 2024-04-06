import os
import json
import shutil
import sqlite3
from typing import Literal
from edsl.config import CONFIG
from edsl.data.CacheEntry import CacheEntry
from edsl.data.Cache import Cache
from edsl.data.SQLiteDict import SQLiteDict

#EDSL_DATABASE_PATH = CONFIG.get("EDSL_DATABASE_PATH")

EDSL_DATABASE_PATH = ".edsl_cache/data.db"

class CacheHandler:
    """
    This CacheHandler figures out what caches are avaialble.
    """

    CACHE_PATH = ".edsl_cache/data.db"
    OLD_CACHE = "edsl_cache.db"

    def __init__(self):

        self.create_cache_directory()

        if os.path.exists(os.path.join(os.getcwd(), self.OLD_CACHE)):
            print(f"Found old cache at {self.OLD_CACHE}")
            data = self.from_old_sqlite_cache_db(self.OLD_CACHE)
            print(f"Found {len(data)} entries in old cache.")
        else:
            print("No old cache found")
            data = {}

        self.cache = self.gen_cache()
        breakpoint()
        self.cache.add_from_dict(data)

    def get_cache(self):
        return self.cache

    def gen_cache(self):
        uri = "sqlite:///" + os.path.join(os.getcwd(), EDSL_DATABASE_PATH)
        cache = Cache(data = SQLiteDict(uri))
        breakpoint()
        return cache

    def create_cache_directory(self):
        #directory_path = EDSL_DATABASE_PATH.replace("sqlite:///", "")
        directory_path = ".edsl_cache"
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
            print(f"Created directory: {directory_path}")

    def from_old_sqlite_cache_db(self, uri="edsl_cache.db"):
        """If there is an old-style cache, read that in and convert it to the new format."""
        conn = sqlite3.connect(uri)
        cur = conn.cursor()
        table_name = "responses"  # Replace with your table name
        cur.execute(f"PRAGMA table_info({table_name})")
        columns = cur.fetchall()
        schema = {column[1]: column[2] for column in columns}
        data = cur.execute(f"SELECT * FROM {table_name}").fetchall()
        d = {}
        for row in data:
            entry_dict = {k: row[i] for i, k in enumerate(schema.keys())}
            entry_dict.pop("id")
            entry_dict["user_prompt"] = entry_dict.pop("prompt")

            parameters = entry_dict["parameters"] #.replace("'", '"')
            import ast
            entry_dict["parameters"] = ast.literal_eval(parameters)
            entry = CacheEntry(**entry_dict)
            d[entry.key] = entry
        return d

    def from_new_sqlite_cache_db(uri="new_edsl_cache.db"):
        conn = sqlite3.connect(uri)
        cur = conn.cursor()
        data = cur.execute("SELECT key, value FROM data").fetchall()
        d = {}
        for key, value in data:
            entry = CacheEntry.from_dict(json.loads(value))
            d[entry.key] = entry.to_dict()
        return d

    def from_jsonl(filename="edsl_cache.jsonl"):
        with open(filename, "a+") as f:
            f.seek(0)
            lines = f.readlines()
        data = {}
        for line in lines:
            d = json.loads(line)
            key = list(d.keys())[0]
            value = list(d.values())[0]
            data[key] = value
        return data

if __name__ == "__main__":
    ch = CacheHandler()

    #print(ch.data)
