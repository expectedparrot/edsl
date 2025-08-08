"""
This module contains the ResultTransformer class for transforming Result data into different formats.

The ResultTransformer class handles the conversion of Result objects into various structured formats
for analysis, including question-organized data and dataset representations.
"""

from collections import defaultdict
from typing import Any, Dict
from collections import UserDict

from abc import ABC, abstractmethod

class ResultComponentDict(UserDict, ABC):
    """Base class for result component dictionaries with automatic subclass registry."""
    
    _registry = {}    
    
    def __init_subclass__(cls, **kwargs):
        """Automatically register subclasses when they are defined."""
        super().__init_subclass__(**kwargs)
        cls._registry[cls.__name__] = cls
    
    @classmethod
    def get_registry(cls):
        """Get the complete registry of all subclasses."""
        return cls._registry.copy()
    
    @classmethod
    def get_class_by_name(cls, name: str):
        """Get a flat list of all registered instances."""
        for class_object in cls._registry.values():
            if class_object.name == name:
                return class_object
        return None
    
    @classmethod
    def get_subclass(cls, class_name: str):
        """Get a specific subclass by name."""
        return cls._registry.get(class_name)
    
    @classmethod
    def get_all_subclasses(cls):
        """Get a list of all registered subclass names."""
        return list(cls._registry.keys())
    
    @classmethod
    def get_subclasses_with_special_keys(cls):
        """Get all subclasses that have special_keys defined."""
        return {name: subclass for name, subclass in cls._registry.items() 
                if hasattr(subclass, 'special_keys') and subclass.special_keys is not None}
    
    @classmethod
    def clear_registry(cls):
        """Clear the entire registry (useful for testing)."""
        cls._registry.clear()

    @abstractmethod
    def generate_by_question_dict(self):
        pass

class ResultComponentDictNoPrependedKeys(ResultComponentDict):
    name = None
    rename_key = None

    def generate_by_question_dict(self):
        d = defaultdict(dict)
        for question_name, value in self.data.items():
            d[question_name][self.rename_key] = value
        return d

class AnswerDict(ResultComponentDictNoPrependedKeys):
    name = "answer"
    rename_key = "answer"

class CacheUsedDict(ResultComponentDictNoPrependedKeys):
    name = "cache_used_dict"
    rename_key = "cache_used"

class CacheKeysDict(ResultComponentDictNoPrependedKeys):
    name = "cache_keys"
    rename_key = "cache_key"


class ResultComponentPrependedKeys(ResultComponentDict):
    name = None
    special_keys = None

    @staticmethod
    def transform_value(value):
        return value if not hasattr(value, 'to_dict') else value.to_dict()

    def generate_by_question_dict(self):
        d = defaultdict(dict)
        for key, value in self.data.items():
            for special_key in self.special_keys:
                if special_key in key:
                    question_name = key.removesuffix(f"_{special_key}")
                    d[question_name][special_key] = self.transform_value(value)
        return d

class PromptDict(ResultComponentPrependedKeys):
    name = 'prompt'
    special_keys = ['user_prompt', 'system_prompt']

class RawModelResponseDict(ResultComponentPrependedKeys):
    name = "raw_model_response"
    special_keys = ['raw_model_response', 'input_tokens', 'output_tokens', 'input_price_per_million_tokens', 'output_price_per_million_tokens', 'cost', 'one_usd_buys']

class GeneratedTokensDict(ResultComponentPrependedKeys):
    name = "generated_tokens"
    special_keys = ['generated_tokens']

class CommentsDict(ResultComponentPrependedKeys):
    name = "comments_dict"
    special_keys = ['comment']

class ReasoningSummariesDict(ResultComponentPrependedKeys):
    name = "reasoning_summaries_dict"
    special_keys = ['reasoning_summary']

class ValidatedDict(ResultComponentPrependedKeys):
    name = "validated_dict"
    special_keys = ['validated']

class ResultComponentNested(ResultComponentDict):
    name = "question_to_attributes"
    special_keys = ['question_text', 'question_options', 'question_type']
 
    def generate_by_question_dict(self):
        d = defaultdict(dict)
        for question_name, value in self.data.items():
            for key, value in value.items():
                d[question_name][key] = value
        return d

class ResultTransformer:
    """Handles data transformation and formatting for Result objects.
    
    This class provides methods to transform Result data into different structured formats,
    such as organizing data by question or converting to dataset format for analysis.
    """
    
    def __init__(self, result_data: Dict[str, Any]):
        """Initialize the ResultTransformer with result data.
        
        Args:
            result_data: The data dictionary from a Result object.
        """
        self.data = result_data
    
    def by_question_data(self, flatten_nested_dicts: bool = False, separator: str = "_"):
        """Organize result data by question with optional flattening of nested dictionaries.
        
        This method reorganizes the result data structure to be organized by question name,
        making it easier to analyze answers and related metadata on a per-question basis.
        
        Args:
            flatten_nested_dicts: Whether to flatten nested dictionaries using the separator.
                Defaults to False.
            separator: The separator to use when flattening nested dictionaries.
                Defaults to "_".
                
        Returns:
            A dictionary organized by question name, with each question containing
            its associated data (answer, prompt, metadata, etc.).
        """
        # question_names = list(self.data['answer'].keys())
        # prepended_dicts = {
        #     'prompt': ['user_prompt', 'system_prompt'], 
        #     'raw_model_response': ['raw_model_response', 'input_tokens', 'output_tokens', 'input_price_per_million_tokens', 'output_price_per_million_tokens', 'cost', 'one_usd_buys'],                           
        #     'generated_tokens': ['generated_tokens'], 
        #     'comments_dict': ['comment'], 
        #     'reasoning_summaries_dict': ['reasoning_summary'], 
        #     'validated_dict': ['validated'],
        # }
        # raw_dicts = {'answer': None, 'cache_used_dict': 'cache_used', 'cache_keys': 'cache_key'} 
        # non_prepended_dicts = {'question_to_attributes': ['question_text', 'question_options', 'question_type']}
        new_dict = defaultdict(dict)
        for data_type, sub_dict in self.data.items():
            data_class = ResultComponentDict.get_class_by_name(data_type)
            if data_class is None:
                print("No class found for", data_type)
                continue
            for question_name, values in data_class(sub_dict).generate_by_question_dict().items():
                for key, value in values.items():
                    new_dict[question_name][key] = value

        return {'question_data': new_dict, 'agent_data': self.data['agent'].to_dict(), 'scenario_data': self.data['scenario'].to_dict()}
            
        # breakpoint()
        
        # d = defaultdict(dict)
        # for data_type, sub_keys in {**prepended_dicts, **non_prepended_dicts}.items():
        #     print("Now trying to get class for", data_type)
        #     data_class = ResultComponentDict.get_class_by_name(data_type)
        #     print("Found class", data_class)
        #     example = data_class(self.data[data_type])
        #     #f data_type == 'prompt':
        #         #npd = PromptDict(self.data[data_type])
        #         #breakpoint()
        #     data = self.data[data_type]
        #     for key in sub_keys:
        #         for question_name in question_names:
        #             prepended_key = question_name + f"_{key}"
        #             if prepended_key in data:
        #                 if key in d[question_name]:
        #                     raise ValueError(f"Question {question_name} already has a {prepended_key} key")
        #                 else:
        #                     value = data[prepended_key]
        #                     if flatten_nested_dicts and isinstance(value, dict):
        #                         for sub_key, sub_value in value.items():
        #                             d[question_name][key + f"{separator}{sub_key}"] = sub_value
        #                     else:
        #                         d[question_name][key] = value if not hasattr(value, 'to_dict') else value.to_dict()
        #             elif key in data[question_name]:
        #                 d[question_name][key] = data[question_name][key]
        #             else:
        #                 print("No match found for", key, " with ", question_name + "_" + key)
        # for data_type, replacement_name in raw_dicts.items():
        #     data = self.data[data_type]
        #     for question_name in question_names:
        #         if replacement_name is None:
        #             d[question_name][data_type] = data[question_name]
        #         else:
        #             d[question_name][replacement_name] = data[question_name]
        # return d
    
    def to_dataset(self, flatten_nested_dicts: bool = False, separator: str = "_"):
        """Convert the result to a dataset format.
        
        This method transforms the result data into a Dataset object suitable for
        analysis and data manipulation.
        
        Args:
            flatten_nested_dicts: Whether to flatten nested dictionaries using the separator.
                Defaults to False.
            separator: The separator to use when flattening nested dictionaries.
                Defaults to "_".
                
        Returns:
            A Dataset object containing the result data organized for analysis.
        """
        by_question_data = self.by_question_data(flatten_nested_dicts=flatten_nested_dicts, separator=separator)
        columns = []
        data = defaultdict(list)
        for question_name in by_question_data:
            for key in by_question_data[question_name]:
                if key not in columns:
                    columns.append(key)

        for column in columns:
            for question_name in by_question_data:
                data[column].append(by_question_data[question_name][column])
        
        for question_name in by_question_data:
            data['question_name'].append(question_name)

        from ..dataset import Dataset
        return Dataset([{key: data[key]} for key in data]) 
    
if __name__ == "__main__":
    print("Registered subclasses:", ResultComponentDict.get_all_subclasses())
    print("Registry:", ResultComponentDict.get_registry())
    print("Classes with special keys:", ResultComponentDict.get_subclasses_with_special_keys())