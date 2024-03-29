import json
import hashlib
import time
from typing import Literal

from collections import UserDict
from collections import defaultdict 

from edsl.data import CRUD
from edsl.exceptions import LanguageModelResponseNotJSONError

from dataclasses import dataclass, asdict


@dataclass
class CacheEntry:
    model: str
    parameters: str
    system_prompt: str
    user_prompt: str
    output: str
    iteration: int

    @classmethod
    def gen_key(self, model, parameters, system_prompt, user_prompt, iteration):
        long_key = f"{model}{parameters}{system_prompt}{user_prompt}{iteration}"
        return hashlib.md5(long_key.encode()).hexdigest()

    @property
    def key(self):
        d = asdict(self)
        d.pop('output')
        return self.gen_key(**d)
    
        
class Cache(UserDict):
    """Class representing a Cache
    """

    def __init__(self, data = None, method: Literal['memory', 'db'] = 'memory'):
        self.crud = CRUD
        super().__init__(data)
        self.by_factor_dict = defaultdict(lambda: defaultdict(list))
        self.method = method
        self.timestamps = {}

#        print(f"Cache instances created: {id(self)}")

    def to_dict(self):
        return self.data

    def fetch(self, 
            model,
            parameters,
            system_prompt,
            user_prompt,
            iteration,
        ):
        
        memory_entry = self._fetch_from_memory(model, parameters, system_prompt, user_prompt, iteration)
        db_entry = self._fetch_from_db(model, parameters, system_prompt, user_prompt, iteration)

        ## This works:
        # json.loads(db_entry) == json.loads(json.loads(memory_entry))

        #try:
        #    assert memory_entry == db_entry
        #except AssertionError:
        #    breakpoint()

        if self.method == 'memory':
            return memory_entry
        elif self.method == 'db':
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
        #breakpoint()
        if entry is None:
            return None
        else:
            return asdict(entry)["output"]

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
        #raise Exception("Store")
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
        # self.by_factor_dict['model'][model].append(key)
        # self.by_factor_dict['parameters'][parameters].append(key)
        # self.by_factor_dict['system_prompt'][system_prompt].append(key)
        # self.by_factor_dict['user_prompt'][user_prompt].append(key)
        # self.by_factor_dict['iteration'][iteration].append(key)

    def _store_db(self, entry: CacheEntry):
        
        self.crud.write_LLMOutputData(
                model=entry.model,
                parameters=entry.parameters,
                system_prompt=entry.system_prompt,
                prompt=entry.user_prompt,
                output=entry.output,
                iteration=entry.iteration,
            )
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass

if __name__ == "__main__":


    from edsl import QuestionFreeText

    q = QuestionFreeText(question_text = "How are you feeling when you haven't slept well?",
                         question_name = "how_feeling")
    
    c = Cache(method='memory')

    # Run 1 
    results = q.run(cache = c, stop_on_exception = True, progress_bar = True)

    # Run 2
    results = q.run(cache = c, stop_on_exception = True, progress_bar = True)

    

    #ce = CacheEntry("gpt-3.5-turbo", "{'temperature': 0.5}", "The quick brown fox jumps over the lazy dog.", "What does the fox say?", "The fox says 'hello'", 1)
    #ce.gen_key()

    # c = Cache()
    # c._store_memory("gpt-3.5-turbo", "{'temperature': 0.5}", "The quick brown fox jumps over the lazy dog.", "What does the fox say?", "The fox says 'hello'", 1)
