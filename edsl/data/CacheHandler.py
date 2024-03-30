import os
import json
import shutil
import sqlite3
from edsl.data.CacheEntry import CacheEntry

class CacheHandler:

    CACHE_PATH = ".edsl_cache"
    OLD_CACHE = "edsl_cache.db"
    NEW_DB_CACHE = "./edsl_cache/edsl.db"
    NEW_JSONL_CACHE = "./edsl_cache/edsl.jsonl"

    def __init__(self, filename = None):

        # if a filename is passed, use that. 
        
        data_old_cache = {}    
        data_new_slite_cache = {}
        data_jsonl_cache = {}


        # 1. If the new cache directory doesn't exist, create it. 
        directory_path = os.path.join(os.getcwd(), self.CACHE_PATH)
        if not os.path.exists(directory_path):
            print("Created directory")
            os.makedirs(directory_path)

        # 2. Check for the old cache file. If it exists, get its data. Rename to .bak
        if os.path.exists(self.OLD_CACHE):
            print("Old cache found. Converting to new format.")
            data_old_cache = self.from_old_sqlite_cache_db(self.OLD_CACHE)
            shutil.move(self.OLD_CACHE, "edsl_cache.db.bak")

        # 3. Check for the new cache files. If they exist, get their data.
        if os.path.exists(self.NEW_DB_CACHE):
            print("New DB cache found.")
            data_new_slite_cache = self.from_new_sqlite_cache_db(self.NEW_DB_CACHE)
        
        # 4. Check for the new jsonl cache file. If it exists, get its data.
        if os.path.exists(self.NEW_JSONL_CACHE):
            print("JSONL cache found.")
            data_jsonl_cache = self.from_jsonl(self.NEW_JSONL_CACHE)

        # Data in JSONL not in DB: 
        diff = {k: v for k, v in data_jsonl_cache.items() if k not in data_new_slite_cache}
        print(f"Data in JSONL but not in DB: {diff}")

        # Data in DB not in JSONL:
        diff = {k: v for k, v in data_new_slite_cache.items() if k not in data_jsonl_cache}
        print(f"Data in DB but not in JSONL: {diff}")

        self._data = {**data_old_cache, **data_new_slite_cache, **data_jsonl_cache}

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


    def from_old_sqlite_cache_db(self, uri = "edsl_cache.db"):
        """If there is an old-style cache, read that in and convert it to the new format."""
        conn = sqlite3.connect(uri)
        cur = conn.cursor()
        table_name = 'responses'  # Replace with your table name
        cur.execute(f"PRAGMA table_info({table_name})")
        columns = cur.fetchall()
        schema = {column[1]: column[2] for column in columns}
        data = cur.execute(f"SELECT * FROM {table_name}").fetchall()
        d = {}
        for row in data:
            entry_dict = {k: row[i] for i, k in enumerate(schema.keys())}
            entry_dict.pop('id')
            entry_dict['user_prompt'] = entry_dict.pop('prompt')
            entry = CacheEntry(**entry_dict)
            d[entry.key] = entry.to_dict()
        return d
    
    def from_new_sqlite_cache_db(uri = "new_edsl_cache.db"):
        conn = sqlite3.connect(uri)
        cur = conn.cursor()
        data = cur.execute("SELECT key, value FROM data").fetchall()
        d = {}
        for key, value in data:
            entry = CacheEntry.from_dict(json.loads(value))
            d[entry.key] = entry.to_dict()
        return d

    def from_jsonl(filename = 'edsl_cache.jsonl'):
        with open(filename, 'a+') as f:
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