"""

Datastore is the SQLite3 dict 
-- Cache can be run in real-time writing or at the end
-- testing, we just use a dictioary 
-- JSONL is only used for exporting

Maybe a Cache is intialized with a method of storage and the data

data = MemoryDict{} # python dictionary 
data = SQLiteDict() # SQLite3 database
data = RemoteDict() # Remote database

Persistance: 
- Advantage of SQLite3 is we can leave DB as-is between sessions
- Advantage of JSONL is that we can easily work with 'pieces' of the cache

Idea: 
- We leave an SQLite3 database on user's machine
- When we start a session, we check if there are any updates to the cache on remote server
- If there are, we download them and update the cache

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
import json
import time
import os
import tempfile

from typing import Literal, Union

from edsl.exceptions import LanguageModelResponseNotJSONError

from edsl.data.CacheEntry import CacheEntry
from edsl.data.SQLiteDict import SQLiteDict
from edsl.data.RemoteDict import RemoteDict
from collections import UserDict

class Cache:
    """A class to represent a cache of responses from a language model."""
    data = {}

    EXPECTED_PARROT_CACHE_URL = "https://f61709b5-4cdf-487d-a30c-a803ab910ca1-00-27digq3c8e2zg.worf.replit.dev"

    def __init__(self, data: Union[SQLiteDict, dict, None]  = None, 
                 immediate_write:bool = True, 
                 method = None):
        """Instantiate a new cache object.
        
        :param data: The data to initialize the cache with.
        :param immediate_write: Whether to write to the cache immediately after storing a new entry.
        :param method: The method of storage to use for the cache. (Deprecated). Will be removed in future versions.
        """
        self.data = data or {}
        
        self.new_entries = {} # New entries created during a __enter__ block
        self.new_entries_to_write_later = {} # storarge for entries that will be written to the cache later
        
        self.immediate_write = immediate_write
        self._check_value_types()

        if method is not None:
            import warnings
            warnings.warn("Method is deprecated", DeprecationWarning)

    def _check_value_types(self) -> None:
        """Check that all values in the cache are CacheEntry objects."""     
        for value in self.data.values():
            if not isinstance(value, CacheEntry):
                raise Exception("Not all values are CacheEntity")

    def __len__(self):
        """
        >>> c = Cache()
        >>> len(c)
        0

        >>> c = Cache(data = CacheEntry.example_dict())
        >>> len(c)
        1
        """
        return len(self.data)

    def __repr__(self):
        return f"Cache(data = {repr(self.data)}, immediate_write={self.immediate_write})"
    
    def __add__(self, other: 'Cache'):
        """Adds two caches together.
        
        :param other: The other cache to add to this one.

        >>> c1 = Cache.example()
        >>> c2 = Cache.example()
        >>> c3 = c1 + c2
        >>> list(c3.data.keys())
        ['55ce2e13d38aa7fb6ec848053285edb4']
        """
        if not isinstance(other, Cache):
            raise ValueError("Can only add two caches together")
        
        for key, value in other.data.items():
            self.data[key] = value
        return self
    
    @property
    def last_insertion(self) -> int:
        """
        Get the timestamp of the last insertion into the cache.

        >>> c = Cache()
        >>> input = CacheEntry.store_input_example()        
        >>> c.store(**input)
        >>> insert_time = list(c.data.values())[0].timestamp
        >>> c.last_insertion - insert_time
        0
        """
        keys = list(self.data.keys())
        if len(keys) > 0:
            last_key = keys[-1]
            entry = self.data[last_key]
            return getattr(entry, 'timestamp')
        else:
            raise Exception("Cache is empty!")

    def fetch_input_example(self) -> dict:
        return CacheEntry.fetch_input_example()

    def fetch(self, 
            *,
            model,
            parameters,
            system_prompt,
            user_prompt,
            iteration,
        ) -> Union[None, CacheEntry]:
        """Fetches the response from the cache.

        :param model: The model used to generate the response.
        :param parameters: The parameters used to generate the response.
        :param system_prompt: The system prompt used to generate the response.
        :param user_prompt: The user prompt used to generate the response.
        :param iteration: The iteration of the response.


        >>> c = Cache()
        >>> c.fetch(model="gpt-3.5-turbo", parameters="{'temperature': 0.5}", system_prompt="The quick brown fox jumps over the lazy dog.", user_prompt="What does the fox say?", iteration=1)

        >>> c = Cache.example()
        >>> input = c.fetch_input_example()
        >>> c.fetch(**input)
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
        """Adds the response to the cache.

        :param model: The model used to generate the response.
        :param parameters: The parameters used to generate the response.
        :param system_prompt: The system prompt used to generate the response.
        :param user_prompt: The user prompt used to generate the response.
        :param response: The response generated by the model.
        :param iteration: The iteration of the response.

        >>> c = Cache()
        >>> input = CacheEntry.store_input_example()        
        >>> c.store(**input)
        >>> list(c.data.keys())
        ['55ce2e13d38aa7fb6ec848053285edb4']

        >>> c = Cache(immediate_write = False)
        >>> input = CacheEntry.store_input_example()        
        >>> c.store(**input)
        >>> list(c.data.keys())
        []

       
        >>> delay_cache = Cache(immediate_write = False)
        >>> c = delay_cache.__enter__()
        >>> input = CacheEntry.store_input_example()
        >>> c.store(**input)
        >>> list(c.data.keys()) == []
        True
        >>> delay_cache.__exit__(None, None, None)
        >>> list(delay_cache.data.keys())
        ['55ce2e13d38aa7fb6ec848053285edb4']
        """
        try:
            output = json.dumps(response)
        except json.JSONDecodeError:
            raise LanguageModelResponseNotJSONError

        timestamp = int(time.time())
        entry = CacheEntry(
            model=model,
            parameters=parameters,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output=output,
            iteration=iteration,
            timestamp=timestamp
        )
           
        key = entry.key
        self.new_entries[key] = entry
        if self.immediate_write:
            self.data[key] = entry
        else:
            self.new_entries_to_write_later[key] = entry
        
    def __eq__(self, other_cache: 'Cache') -> bool:
        """
        Check if two caches are equal.

        >>> c1 = Cache(data = {'poo': CacheEntry.example()})
        >>> c2 = Cache(data = {'poo': CacheEntry.example()})
        >>> c1 == c2
        True

        >>> c3 = Cache(data = {'poop': CacheEntry.example()})
        >>> c1 == c3
        False
        """
        for key in self.data: 
            if key not in other_cache.data:
                return False
        for key in other_cache.data:
            if key not in self.data:
                return False
        return True

    def add_multiple_entries(self, new_data: dict, write_now:bool = True) -> None:
        """
        Add multiple entries to the cache.

        Example of immediate writing: 

        >>> c = Cache()
        >>> data = {'poo': CacheEntry.example(), 'bandits': CacheEntry.example()}
        >>> c.add_multiple_entries(new_data = data)
        >>> c.data['poo'] == CacheEntry.example()
        True

        Example of delayed writing 
        
        >>> c = Cache()
        >>> data = {'poo': CacheEntry.example(), 'bandits': CacheEntry.example()}
        >>> c.add_multiple_entries(new_data = data, write_now = False)
        >>> c.data 
        {}
        >>> c.__exit__(None, None, None)
        >>> c.data['poo'] == CacheEntry.example()
        True
        """
        for key, value in new_data.items():
            if key in self.data:
                if value != self.data[key]:
                    raise Exception("Mismatch in values")
            if not isinstance(value, CacheEntry):
                raise Exception("Wrong type")
    
        self.new_entries.update(new_data)
        if write_now:
            self.data.update(new_data)
        else:
            self.new_entries_to_write_later.update(new_data)

    def add_from_jsonl(self, filename: str, write_now = True) -> None:
        """Add entries from a JSONL file to the cache.

        >>> c = Cache(data = CacheEntry.example_dict())
        >>> c.write_jsonl("example.jsonl")
        >>> cnew = Cache()
        >>> cnew.add_from_jsonl(filename = 'example.jsonl')
        >>> c == cnew
        True
        """
        with open(filename, 'a+') as f:
            f.seek(0)
            lines = f.readlines()
        new_data = {}
        for line in lines:
            d = json.loads(line)
            key = list(d.keys())[0]
            value = list(d.values())[0]
            new_data[key] = CacheEntry(**value)
        self.add_multiple_entries(new_data, write_now = write_now)

    def add_from_sqlite(self, db_path, write_now = True):
        """Add entries from an SQLite database to the cache.
        """
        db = SQLiteDict(db_path)
        new_data = {}
        for key, value in db.items():
            new_data[key] = CacheEntry(**value)
        self.add_multiple_entries(new_data, write_now)

    @classmethod 
    def from_sqlite_db(cls, db_path:str) -> 'Cache':
        """Return a Cache object from an SQLite database.

        :param db_path: The path to the SQLite database.

        >>> c = Cache.example()
        >>> c.data['poo'] = CacheEntry.example()
        >>> c.write_sqlite("example.db")
        >>> cnew = Cache.from_sqlite_db("example.db")
        >>> c == cnew
        True
        """
        return cls(data = SQLiteDict(db_path))

    @classmethod
    def from_jsonl(cls, jsonlfile:str, db_path:str = None) -> 'Cache':
        if db_path is None:
            db_path = "./edsl_cache/data.db"
        db = SQLiteDict(db_path)
        cache = Cache(data = db)
        cache.add_from_jsonl(jsonlfile)
        return cache
    
    @classmethod
    def from_url(cls, base_url, db_path = None):
        import requests
        response = requests.get(f"{base_url}/items/all")
        if response.status_code == 404:
            raise KeyError(f"Key '{key}' not found.")
        response.raise_for_status()
        data = response.json()
        if db_path is None:
            db_path = "./edsl_cache/data.db"
        db = SQLiteDict(db_path)
        for key, value in data.items():
            db[key] = CacheEntry(**value)
        return Cache(data = db)
    
        #for key, value in self.data.items():
            #response = requests.post(f"{base_url}/items/{key}", json=value.to_dict())
            #response.raise_for_status()

    def write_sqlite(self, db_path):
        """
        Write the cache to an SQLite database.

        :param db_path: The path to the SQLite database.
        
        >>> c = Cache.example()
        >>> c.write_sqlite("example.db")
        """
        new_data = SQLiteDict(db_path)
        for key, value in self.data.items():
            new_data[key] = value
 
    def write_jsonl(self, filename):
        """Write the cache to a JSONL file."""
        dir_name = os.path.dirname(filename)
        with tempfile.NamedTemporaryFile(mode='w', dir=dir_name, delete=False) as tmp_file:
            for key, raw_value in self.data.items():
                value = raw_value if not hasattr(raw_value, "to_dict") else raw_value.to_dict()
                tmp_file.write(json.dumps({key: value}) + '\n')
            temp_name = tmp_file.name
        try:
            os.replace(temp_name, filename)
        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)
                os.replace(temp_name, filename)

    @classmethod
    def example(cls):
        return cls(data = {CacheEntry.example().key: CacheEntry.example()})

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        for key, entry in self.new_entries_to_write_later.items():
            self.data[key] = entry

        remote_cache = False
        if remote_cache:
            print("Writing to remote server")
            base_url = "https://f61709b5-4cdf-487d-a30c-a803ab910ca1-00-27digq3c8e2zg.worf.replit.dev"
            import requests
            items = [{"key": key, "item": value.to_dict()} for key, value in self.new_entries.items()]
            response = requests.post(f"{base_url}/items/batch", json=items)
            response.raise_for_status()
        
            # Handle the response
            print(response.json())

        
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


if __name__ == "__main__":

    import doctest
    doctest.testmod()

    if False:
        #base_url = "https://f61709b5-4cdf-487d-a30c-a803ab910ca1-00-27digq3c8e2zg.worf.replit.dev"
        #cache = Cache(data = RemoteDict(base_url = base_url))
        #cache = Cache.from_url(base_url = base_url)

        cache = Cache()

        from edsl import QuestionFreeText, QuestionMultipleChoice
        # q = QuestionFreeText.example()
        # results = q.run(cache = cache)

        # q2 = QuestionMultipleChoice.example()
        # results = q2.run(cache = cache, progress_bar = True)

    #    with cache as c:
        from edsl import Model, Scenario
        m = Model(Model.available()[0])
        numbers = range(150, 250)
        scenarios = [Scenario({'number': number}) for number in numbers]
        q = QuestionFreeText(question_text = "Is {{number}} prime?", question_name = "prime")
        results = q.by(m).by(scenarios).run(cache = cache, progress_bar = True)


        # data = {'poo': CacheEntry.example()}

        # c = Cache(data = data)
        # c.data

        # print("Printing weird example")
        # c.write_sqlite("weird_example.db")

        # print(c.last_insertion)

        # delay_cache = Cache(immediate_write = False)
        # with delay_cache as c:
        #     input = CacheEntry.store_input_example()
        #     c.store(**input)
        #     print("Keys are currently:", list(c.data.keys()))

        # print("Keys are now:", delay_cache.data.keys())

        ##c.fetch(**CacheEntry.fetch_input_example())

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