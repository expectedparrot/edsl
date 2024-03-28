import json
import hashlib
import time

from collections import UserDict
from collections import defaultdict 

from edsl.data import CRUD
from edsl.exceptions import LanguageModelResponseNotJSONError


# Entries
## (timestamp, model, parameters, system_prompt, prompt, iteration): output

class Cache(UserDict):

    def __init__(self, data = None):
        self.crud = CRUD
        super().__init__(data)

        self.by_factor_dict = defaultdict(lambda: defaultdict(list))
    
    def fetch(self, 
            model,
            parameters,
            system_prompt,
            user_prompt,
            iteration,
        ):
        return self._get_from_db(model, parameters, system_prompt, user_prompt, iteration)
    
    def _get_from_memory(self, 
            model,
            parameters,
            system_prompt,
            user_prompt,
            iteration,
        ):
        key = self._gen_key(model, parameters, system_prompt, user_prompt, iteration)
        return self.get(key)

    def _get_from_db(self, 
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
        return cached_response

    def _gen_key(self, 
            model,
            parameters,
            system_prompt,
            user_prompt,
            iteration,
        ):
        long_key = f"{model}{parameters}{system_prompt}{user_prompt}{iteration}"
        return hashlib.md5(long_key.encode()).hexdigest()

    def add_entry(self, 
            model,
            parameters,
            system_prompt,
            user_prompt,
            response,
            iteration,
        ):
        key = self._gen_key(model, parameters, system_prompt, user_prompt, iteration)
        output = json.dumps(response)
        added_time = int(time.time())
        self[(added_time, key)] = output
        self.by_factor_dict['model'][model].append(key)
        self.by_factor_dict['parameters'][parameters].append(key)
        self.by_factor_dict['system_prompt'][system_prompt].append(key)
        self.by_factor_dict['user_prompt'][user_prompt].append(key)
        self.by_factor_dict['iteration'][iteration].append(key)

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
        
        self.crud.write_LLMOutputData(
                model=model,
                parameters=parameters,
                system_prompt=system_prompt,
                prompt=user_prompt,
                output=output,
                iteration=iteration,
            )
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass

if __name__ == "__main__":
    
    c = Cache()
    c.add_entry("gpt-3.5-turbo", "{'temperature': 0.5}", "The quick brown fox jumps over the lazy dog.", "What does the fox say?", "The fox says 'hello'", 1)
