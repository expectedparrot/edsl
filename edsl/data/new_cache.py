"""

Desired features:
- Hard to corrupt (e.g., if the program crashes)
- Good transactional support
- Can easily combine two caches together w/o duplicating entries
- Can easily fetch another cache collection and add to own
- Can easily use a remote cache w/o changing edsl code 
- Easy to migrate 
- Can deal easily with cache getting too large 
- "Coopable" - could share a smaller cache with another user

- Good defaults
- Can export part of cache that was used for a particular run

Export methods: 
- JSONL
- SQLite3
- JSON

Remote persistence options:
- Database on Expected Parrot 

Local persistence options: 
- JSONL file
- SQLite3 database

Writing options: 
- Wait until the end to write to cache persistence layer
- Write to cache persistence layer incrementally, as proceeding

"""
from abc import ABC, ABCMeta, abstractmethod
import json
import hashlib
import time
import sqlite3
import shutil
import os
import tempfile

from typing import Literal, Union

from edsl.exceptions import LanguageModelResponseNotJSONError

from edsl.data.CacheEntry import CacheEntry
from edsl.data.SQLiteDict import SQLiteDict

class CacheABC(ABC):

    data = {}
    new_entries = []

    def __add__(self, other: 'CacheABC'):
        """Adds two caches together.
        
        >>> c1 = Cache.example()
        >>> c2 = Cache.example()
        >>> c3 = c1 + c2
        >>> c3.data.keys()
        dict_keys(['55ce2e13d38aa7fb6ec848053285edb4'])
        """

        if not isinstance(other, CacheABC):
            raise ValueError("Can only add two caches together")
        return self.__class__(data = self.data | other.data)
    
    def fetch(self, 
            *,
            model,
            parameters,
            system_prompt,
            user_prompt,
            iteration,
        ) -> Union[str, CacheEntry]:
        """Fetches the response from the cache.
        
        >>> c = Cache()
        >>> c.fetch(model="gpt-3.5-turbo", parameters="{'temperature': 0.5}", system_prompt="The quick brown fox jumps over the lazy dog.", user_prompt="What does the fox say?", iteration=1)

        >>> c = Cache.example()
        >>> inputs = CacheEntry.example().to_dict()
        >>> _ = inputs.pop('output')
        >>> _ = inputs.pop('timestamp')
        >>> c.fetch(**inputs)
        "The fox says 'hello'"
        """
        key = CacheEntry.gen_key(model=model, 
                                 parameters=parameters, 
                                 system_prompt=system_prompt, 
                                 user_prompt=user_prompt, 
                                 iteration=iteration)
        entry = self.data.get(key, None)
        return None if entry is None else entry.output

    def store(self,
            model,
            parameters,
            system_prompt,
            user_prompt,
            response,
            iteration,
        ):
        """Addds the response to the cache.

        >>> c = Cache()        
        >>> entry = CacheEntry.example()
        >>> inputs = entry.to_dict()
        >>> inputs['response'] = inputs.pop('output')
        >>> _ = inputs.pop('timestamp')
        >>> c.store(**inputs)
        >>> c.data.keys()
        dict_keys(['55ce2e13d38aa7fb6ec848053285edb4'])
        """
        try:
            output = json.dumps(response)
        except json.JSONDecodeError:
            raise LanguageModelResponseNotJSONError

        entry = CacheEntry(
            model=model,
            parameters=parameters,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output=output,
            iteration=iteration,
            timestamp=int(time.time())
        )
           
        added_time = int(time.time())
        key = entry.key
        self.data[key] = entry
        self.timestamps[key] = added_time 
        self.new_entries.append(entry)

    @classmethod
    def example(cls, method = 'jsonl'):
        return cls(data = {CacheEntry.example().key: CacheEntry.example()}, method = method)

    def incremental_write(self, entry):
        self._incremental_write(entry)

    def full_write(self):
        self._full_write()

    @abstractmethod
    def _full_write(self):
        pass

    @abstractmethod
    def _incremental_write(self, entry, filename):
        pass

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        ## Idea: This could differ based on the method of storage
        ## E.g., is SQLite, transactions are already committed
        ## If it's a jsonl file, we need to write the new entries
        for entry in self.new_entries:
            self.incremental_write(entry)
        
class Cache(CacheABC):
    """Class representing a Cache for storing the output of language models.

    - from_jsonl
    - from_json
    - from_old_sqlite_db
    - from_sqlite_db
    - backup_jsonl
    - to_jsonl
    """

    FILENAME = 'edsl_cache.jsonl'

    def __init__(self, data = None, method = "jsonl"):
        self.new_entries = []
        self.timestamps = {}

        if method == 'jsonl':
            self.data = {}
        elif method == 'sqlite3':
            self.data = SQLiteDict()

        if data is not None:
            for k, v in data.items():
                if k in self.data:
                    raise ValueError(f"Duplicate key: {k}")
                if not isinstance(v, CacheEntry):
                    self.data[k] = CacheEntry.from_dict(v)
                else:
                    self.data[k] = v

    def backup_jsonl(self, filename = 'edsl_cache.jsonl'):
        shutil.copy(filename, f"{filename}.bak")
        
    @classmethod
    def from_jsonl(cls, filename = 'edsl_cache.jsonl'):
        with open(filename, 'a+') as f:
            f.seek(0)
            lines = f.readlines()
        data = {}
        for line in lines:
            d = json.loads(line)
            key = list(d.keys())[0]
            value = list(d.values())[0]
            data[key] = value
        return cls(data = data)
    
    def _full_write(self, filename = None):
        filename = filename or self.FILENAME
        dir_name = os.path.dirname(filename)
        with tempfile.NamedTemporaryFile(mode='w', dir=dir_name, delete=False) as tmp_file:
            for key, value in self.data.items():
                tmp_file.write(json.dumps({key: value.to_dict()}) + '\n')
            temp_name = tmp_file.name
            os.replace(temp_name, filename)

    def _incremental_write(self, entry, filename = None):
        filename = filename or self.FILENAME
        key = entry.key
        value = entry.to_dict()
        with open(filename, 'a+') as f:
            f.write(json.dumps({key: value}) + '\n')
        
    # def __setitem__(self, key, value):
    #     super().__setitem__(key, value)
    #     self.timestamps[key] = value.timestamp

    def to_dict(self):
        return {k:v.to_dict() for k, v in self.data.items()}
 
    @classmethod 
    def from_dict(cls, data, method = 'memory'):
        data = {k: CacheEntry.from_dict(v) for k, v in data}
        return cls(data = data)
    
    ## Method for reading in an old sqlite database
    @classmethod
    def from_sqlite_db(cls, uri = "edsl_cache.db"):
        conn = sqlite3.connect(uri)
        cur = conn.cursor()
        table_name = 'responses'  # Replace with your table name
        cur.execute(f"PRAGMA table_info({table_name})")
        columns = cur.fetchall()
        schema = {column[1]: column[2] for column in columns}
        #return schema
        data = cur.execute(f"SELECT * FROM {table_name}").fetchall()
        d = {}
        for row in data:
            entry_dict = {k: row[i] for i, k in enumerate(schema.keys())}
            entry_dict.pop('id')
            entry_dict['user_prompt'] = entry_dict.pop('prompt')
            entry = CacheEntry(**entry_dict)
            d[entry.key] = entry.to_dict()
        return cls(data = d)


if __name__ == "__main__":

    import doctest
    doctest.testmod()

    #cache = Cache.from_jsonl('cache.jsonl')
    #from edsl import QuestionFreeText
    #results = QuestionFreeText.example().run(cache = cache)


    # start = time.monotonic()
    # for i in range(1_000_000):
    #     c = CacheEntry.example()
    #     c.iteration += i
    #     cache.add_to_jsonl(c)  
    # end = time.monotonic()
    # print(f"Time: {end - start} for 1_000_000 entries")
    # # c.save('cache.json') 

    # cache.to_jsonl(filename = 'test_cache.jsonl')

    # new_cache = Cache.load('cache.json')   

    #ce = CacheEntry("gpt-3.5-turbo", "{'temperature': 0.5}", "The quick brown fox jumps over the lazy dog.", "What does the fox say?", "The fox says 'hello'", 1)
    #ce.gen_key()

    # c = Cache()
    # c._store_memory("gpt-3.5-turbo", "{'temperature': 0.5}", "The quick brown fox jumps over the lazy dog.", "What does the fox say?", "The fox says 'hello'", 1)