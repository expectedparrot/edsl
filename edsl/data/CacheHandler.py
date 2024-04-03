import os
import json
import shutil
import sqlite3
from typing import Literal
from edsl.config import CONFIG
from edsl.data.CacheEntry import CacheEntry
from edsl.data.Cache import Cache

EDSL_DATABASE_PATH = CONFIG.get("EDSL_DATABASE_PATH")


class CacheHandler:
    """
    This CacheHandler figures out what caches are avaialble.

    """

    CACHE_PATH = ".edsl_cache/data.db"
    OLD_CACHE = "edsl_cache.db"

    def __init__(self, cache_type: Literal["local", "api"] = "local"):
        self.cache_type = cache_type

        if cache_type not in ["local", "api"]:
            raise Exception("Cache type must be either 'local' or 'api'")

        if cache_type == "api":
            self.check_expected_parrot_account()
            self.sync_local_and_remote()

        self.collected_data = self.gather_data()

    def gen_cache(self):
        if self.catch_type == "local":
            cache = Cache.from_sqlite_db(EDSL_DATABASE_PATH)
            cache.add_multiple_entries(self.collected_data, write_now=True)
            return cache

    def gather_data():
        return {}

    def sync_local_and_remote(self):
        pass

    def check_expected_parrot_account():
        pass

    def find_old_caches(sef):
        "Return a list of all identified old Caches"
        pass

    def create_cache_directory(self):
        directory_path = EDSL_DATABASE_PATH.replace("sqlite:///", "")
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
            print(f"Created directory: {directory_path}")

    def backup_old_cache(self):
        # 2. Check for the old cache file. If it exists, get its data. Rename to .bak
        if os.path.exists(self.OLD_CACHE):
            print("Old cache found. Converting to new format.")
            data_old_cache = self.from_old_sqlite_cache_db(self.OLD_CACHE)
            shutil.move(self.OLD_CACHE, "edsl_cache.db.bak")

        # 3. Check for the new cache files. If they exist, get their data.
        if os.path.exists(self.NEW_DB_CACHE):
            print("New DB cache found.")
            data_new_slite_cache = self.from_new_sqlite_cache_db(self.NEW_DB_CACHE)

    @property
    def data(self):
        return self._data

        # if data is not None:
        #     for k, v in data.items():
        #         if k in self.data:
        #             raise ValueError(f"Duplicate key: {k}")
        #         if not isinstance(v, CacheEntry):
        #             self.data[k] = CacheEntry.from_dict(v)
        #         else:
        #             self.data[k] = v

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
            entry = CacheEntry(**entry_dict)
            d[entry.key] = entry.to_dict()
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

    print(ch.data)
