import json
import hashlib
import time
import gzip

from typing import Literal

from collections import UserDict
from collections import defaultdict 

from edsl.data import CRUD
from edsl.exceptions import LanguageModelResponseNotJSONError


class CacheEntry:
    key_fields = ['model', 'parameters', 'system_prompt', 'user_prompt', 'iteration']

    def __init__(self, model, parameters, system_prompt, user_prompt, output, iteration, timestamp = None):
        self.model = model
        self.parameters = parameters
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.output = output
        self.iteration = iteration
        self.timestamp = timestamp or int(time.time())

    @classmethod
    def gen_key(self, model, parameters, system_prompt, user_prompt, iteration):
        long_key = f"{model}{parameters}{system_prompt}{user_prompt}{iteration}"
        return hashlib.md5(long_key.encode()).hexdigest()

    @property
    def key(self):
        d = {k:value for k, value in self.__dict__.items() if k in self.key_fields}
        return self.gen_key(**d)

    def to_dict(self):
        return {
            'model': self.model,
            'parameters': self.parameters,
            'system_prompt': self.system_prompt,
            'user_prompt': self.user_prompt,
            'output': self.output,
            'iteration': self.iteration,
            'timestamp': self.timestamp
        }
    
    def __repr__(self):
        return f"CacheEntry({self.model}, {self.parameters}, {self.system_prompt}, {self.user_prompt}, {self.output}, {self.iteration}, {self.timestamp})"
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)
    
    @classmethod
    def example(cls):
        return CacheEntry(
            model="gpt-3.5-turbo",
            parameters="{'temperature': 0.5}",
            system_prompt="The quick brown fox jumps over the lazy dog.",
            user_prompt="What does the fox say?",
            output="The fox says 'hello'",
            iteration=1,
            timestamp=int(time.time())
        )
        
        
class Cache(UserDict):
    """Class representing a Cache for storing the output of language models.

    They keys are generated from the model, parameters, system_prompt, user_prompt, and iteration.
    The values are the inputs and outputs from the language model.

    -- Add two caches together 
    -- Serialize/Deserialize the cache
    -- Store the cache in a database

    """

    def __init__(self, 
                 data = None, 
                 crud = None, 
                 method: Literal['memory', 'db'] = 'memory'):
        self.crud = crud or CRUD
        self.method = method

        if data is None:
            # creating an emptty cache
            self.by_factor_dict = defaultdict(lambda: defaultdict(list))
            self.timestamps = {}
            super().__init__(data)
        else:
            data = {k: CacheEntry.from_dict(v) for k, v in data.items()}
            super().__init__(data)
            # if there is data, we can re-generate the by_factor_dict and timestamps
            self.by_factor_dict = self._gen_by_factor_dict()
            self.timestamps = self._gen_timestamp_dict()

    def _gen_timestamp_dict(self):
        return {k: v.timestamp for k, v in self.data.items()}
    
    def _gen_by_factor_dict(self):
        fields = ['model', 'parameters', 'system_prompt', 'user_prompt', 'iteration']
        by_factor_dict = defaultdict(lambda: defaultdict(list))
        for field in fields:
            for key, entry in self.data.items():
                by_factor_dict[field][getattr(entry, field)].append(key)
        return by_factor_dict

    def to_dict(self):
        return {k:v.to_dict() for k, v in self.data.items()}
 
    @classmethod 
    def from_dict(cls, data, method = 'memory'):
        data = {k: CacheEntry.from_dict(v) for k, v in data}
        return cls(data = data, method = method)

    def save(self, filename):
        with open(filename, 'w') as f:
            f.write(json.dumps(self.to_dict()))

    @classmethod
    def load(cls, filename):
        with open(filename, 'r') as f:
            data = json.loads(f.read())
            return cls(data = data)

    def fetch(self, 
            model,
            parameters,
            system_prompt,
            user_prompt,
            iteration,
        ):
    
        if self.method == 'memory':
            memory_entry = self._fetch_from_memory(model, parameters, system_prompt, user_prompt, iteration)
            return memory_entry
        elif self.method == 'db':
            db_entry = self._fetch_from_db(model, parameters, system_prompt, user_prompt, iteration)
            return db_entry
    
    def _fetch_from_memory(self, 
            model,
            parameters,
            system_prompt,
            user_prompt,
            iteration,
        ):
        key = CacheEntry.gen_key(model, parameters, system_prompt, user_prompt, iteration)
        entry = self.data.get(key, None)
        if entry is None:
            return None
        else:
            return entry.output

    def _fetch_from_db(self, 
            model,
            parameters,
            system_prompt,
            user_prompt,
            iteration,
        ):
        """Get the response from the database."""
        cached_response = self.crud.get_LLMOutputData(
                model=model,
                parameters=parameters,
                system_prompt=system_prompt,
                prompt=user_prompt,
                iteration=iteration,
            )
        return json.loads(cached_response)


    def store(self,
            model,
            parameters,
            system_prompt,
            user_prompt,
            response,
            iteration,
        ):
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
        self._store_db(entry)
        self._store_memory(entry)

        # if self.method == 'memory':
        #     self._store_memory(entry)
        # elif self.method == 'db':
        #     self._store_db(entry)
        # else:
        #     raise ValueError("Invalid method")

        
    def _store_memory(self, entry: CacheEntry):     
           
        added_time = int(time.time())
        key = entry.key
        self.data[key] = entry
        self.timestamps[key] = added_time 
        fields = ['model', 'parameters', 'system_prompt', 'user_prompt', 'iteration']
        for field in fields:
            self.by_factor_dict[field][getattr(entry, field)].append(key)

    def _store_db(self, entry: CacheEntry):

        ## should timestamp be added here?
                
        self.crud.write_LLMOutputData(
                model=entry.model,
                parameters=entry.parameters,
                system_prompt=entry.system_prompt,
                prompt=entry.user_prompt,
                output=entry.output,
                iteration=entry.iteration,
                timestamp=entry.timestamp
            )
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass

if __name__ == "__main__":

    #c = CacheEntry.example()

    c = Cache(method='memory')
    from edsl import QuestionFreeText

    q = QuestionFreeText(question_text = "How are you feeling when you haven't slept well?",
                          question_name = "how_feeling")
    
    
    # # Run 1 
    results = q.run(cache = c, stop_on_exception = True, progress_bar = True)

    # # Run 2
    results = q.run(cache = c, stop_on_exception = True, progress_bar = True)

    c.save('cache.json') 

    new_cache = Cache.load('cache.json')   

    #ce = CacheEntry("gpt-3.5-turbo", "{'temperature': 0.5}", "The quick brown fox jumps over the lazy dog.", "What does the fox say?", "The fox says 'hello'", 1)
    #ce.gen_key()

    # c = Cache()
    # c._store_memory("gpt-3.5-turbo", "{'temperature': 0.5}", "The quick brown fox jumps over the lazy dog.", "What does the fox say?", "The fox says 'hello'", 1)