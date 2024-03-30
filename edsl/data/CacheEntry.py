import time
import hashlib

class CacheEntry:
    key_fields = ['model', 'parameters', 'system_prompt', 'user_prompt', 'iteration']
    all_fields = key_fields + ['timestamp', 'output']
    def __init__(self, *, model, parameters, system_prompt, user_prompt, output, iteration = None, timestamp = None):
        self.model = model
        self.parameters = parameters
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.output = output
        self.iteration = iteration or 0 
        self.timestamp = timestamp or int(time.time())

    def __eq__(self, other_entry):
        for field in self.all_fields:
            if getattr(self, field) != getattr(other_entry, field):
                raise False
        return True

    @classmethod
    def example_dict(cls) -> dict:
        entity = cls.example()
        key = entity.key
        return {key: entity}

    @classmethod
    def fetch_input_example(cls) -> dict:
        """
        
        >>> CacheEntry.input_example()

        """
        input =cls.example().to_dict()
        _ = input.pop('timestamp')
        _ = input.pop('output')
        return input

    @classmethod    
    def store_input_example(cls) -> dict:
        input = cls.example().to_dict()
        _ = input.pop("timestamp")
        input['response'] = input.pop('output')
        return input

    @classmethod
    def gen_key(self, *, model, parameters, system_prompt, user_prompt, iteration):
        """Generate a key for the cache entry.
        
        >>> CacheEntry.gen_key(model = "gpt-3.5-turbo", parameters = "{'temperature': 0.5}", system_prompt = "The quick brown fox jumps over the lazy dog.", user_prompt = "What does the fox say?", iteration = 1)
        '55ce2e13d38aa7fb6ec848053285edb4'
        """

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
        return f"CacheEntry(model={self.model}, parameters={self.parameters}, system_prompt={self.system_prompt}, user_prompt={self.user_prompt}, output={self.output}, iteration={self.iteration}, timestamp={self.timestamp})"
    
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
