"""
Module for handling key selection and filtering operations on Scenario objects.

This module provides the ScenarioSelector class which handles the logic for 
selecting, keeping, and dropping keys from scenarios. It supports both 
collection-style arguments and variable string arguments for maximum flexibility.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Union, Iterable, List

if TYPE_CHECKING:
    from .scenario import Scenario


class ScenarioSelector:
    """
    Handles key selection and filtering operations on Scenario objects.
    
    This class provides functionality to select specific keys, drop unwanted keys,
    and keep desired keys from scenarios. It supports both backward-compatible
    collection arguments and modern variable string arguments.
    """
    
    def __init__(self, scenario: "Scenario"):
        """
        Initialize the selector with a scenario.
        
        Args:
            scenario: The Scenario object to perform selection operations on.
        """
        self.scenario = scenario
    
    def select(self, *args: Union[str, Iterable[str]]) -> "Scenario":
        """
        Select a subset of keys from the scenario to create a new scenario.
        
        This method creates a new scenario containing only the specified keys
        from the original scenario. It supports both individual string arguments
        and collection arguments for backward compatibility.
        
        Args:
            *args: Either a single collection of keys (for backward compatibility)
                   or individual string arguments for keys to select.
                   
        Returns:
            A new Scenario containing only the selected keys and their values.
            
        Raises:
            KeyError: If any of the specified keys don't exist in the scenario.
            
        Examples:
            Using individual string arguments:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"food": "chips", "drink": "water", "dessert": "cake"})
            >>> selector = ScenarioSelector(s)
            >>> result = selector.select("food", "drink")
            >>> result
            Scenario({'food': 'chips', 'drink': 'water'})
            
            Using a collection (backward compatible):
            >>> result = selector.select(["food", "dessert"])
            >>> result
            Scenario({'food': 'chips', 'dessert': 'cake'})
            
            Single string argument:
            >>> result = selector.select("food")
            >>> result
            Scenario({'food': 'chips'})
        """
        keys_to_select = self._parse_arguments(*args)
        return self._create_scenario_with_keys(keys_to_select, include=True)
    
    def drop(self, *args: Union[str, Iterable[str]]) -> "Scenario":
        """
        Drop specified keys from the scenario to create a new scenario.
        
        This method creates a new scenario containing all keys except the ones
        specified for dropping. It supports both individual string arguments
        and collection arguments for backward compatibility.
        
        Args:
            *args: Either a single collection of keys (for backward compatibility)
                   or individual string arguments for keys to drop.
                   
        Returns:
            A new Scenario containing all keys except the dropped ones.
            
        Examples:
            Using individual string arguments:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"food": "chips", "drink": "water", "dessert": "cake"})
            >>> selector = ScenarioSelector(s)
            >>> result = selector.drop("drink", "dessert")
            >>> result
            Scenario({'food': 'chips'})
            
            Using a collection (backward compatible):
            >>> result = selector.drop(["food"])
            >>> result
            Scenario({'drink': 'water', 'dessert': 'cake'})
            
            Single string argument:
            >>> result = selector.drop("dessert")
            >>> result
            Scenario({'food': 'chips', 'drink': 'water'})
        """
        keys_to_drop = self._parse_arguments(*args)
        return self._create_scenario_with_keys(keys_to_drop, include=False)
    
    def keep(self, *args: Union[str, Iterable[str]]) -> "Scenario":
        """
        Keep specified keys from the scenario (alias for select).
        
        This method is an alias for select() and creates a new scenario 
        containing only the specified keys from the original scenario.
        
        Args:
            *args: Either a single collection of keys (for backward compatibility)
                   or individual string arguments for keys to keep.
                   
        Returns:
            A new Scenario containing only the kept keys and their values.
            
        Examples:
            Using individual string arguments:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"food": "chips", "drink": "water", "dessert": "cake"})
            >>> selector = ScenarioSelector(s)
            >>> result = selector.keep("food", "drink")
            >>> result
            Scenario({'food': 'chips', 'drink': 'water'})
        """
        return self.select(*args)
    
    def _parse_arguments(self, *args: Union[str, Iterable[str]]) -> List[str]:
        """
        Parse the variable arguments to extract a list of keys.
        
        This method handles both the new variable string argument style and
        the legacy collection argument style for backward compatibility.
        
        Args:
            *args: Variable arguments that can be either individual strings
                   or a single collection of strings.
                   
        Returns:
            A list of key strings to operate on.
            
        Raises:
            ValueError: If no arguments are provided or if arguments are invalid.
            
        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"a": 1, "b": 2})
            >>> selector = ScenarioSelector(s)
            >>> selector._parse_arguments("a", "b")
            ['a', 'b']
            >>> selector._parse_arguments(["a", "b"])
            ['a', 'b']
            >>> selector._parse_arguments("a")
            ['a']
        """
        if not args:
            raise ValueError("At least one key must be specified")
            
        if len(args) == 1:
            first_arg = args[0]
            # Check if it's a single string or a collection
            if isinstance(first_arg, str):
                # Single string key
                return [first_arg]
            else:
                # Collection of keys (backward compatibility)
                try:
                    return list(first_arg)
                except TypeError:
                    raise ValueError(f"Invalid argument type: {type(first_arg)}. Expected string or iterable of strings.")
        else:
            # Multiple string arguments
            for arg in args:
                if not isinstance(arg, str):
                    raise ValueError(f"All arguments must be strings when using multiple arguments. Got: {type(arg)}")
            return list(args)
    
    def _create_scenario_with_keys(self, keys: List[str], include: bool) -> "Scenario":
        """
        Create a new scenario with specified keys included or excluded.
        
        Args:
            keys: List of keys to include or exclude.
            include: If True, include only these keys. If False, exclude these keys.
            
        Returns:
            A new Scenario with the specified keys included or excluded.
            
        Raises:
            KeyError: If trying to include keys that don't exist in the scenario.
        """
        # Import here to avoid circular imports
        try:
            from .scenario import Scenario
        except ImportError:
            # For doctest execution
            from edsl.scenarios.scenario import Scenario
            
        new_scenario = Scenario()
        keys_set = set(keys)
        
        if include:
            # Select mode: include only specified keys
            for key in keys:
                if key not in self.scenario:
                    raise KeyError(f"Key '{key}' not found in scenario")
                new_scenario[key] = self.scenario[key]
        else:
            # Drop mode: include all keys except specified ones
            for key in self.scenario.keys():
                if key not in keys_set:
                    new_scenario[key] = self.scenario[key]
                    
        return new_scenario
    
    def get_available_keys(self) -> List[str]:
        """
        Get all available keys in the scenario.
        
        Returns:
            A list of all keys present in the scenario.
            
        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"name": "Alice", "age": 30, "city": "NYC"})
            >>> selector = ScenarioSelector(s)
            >>> keys = selector.get_available_keys()
            >>> sorted(keys)
            ['age', 'city', 'name']
        """
        return list(self.scenario.keys())
    
    def has_keys(self, *keys: str) -> bool:
        """
        Check if the scenario contains all specified keys.
        
        Args:
            *keys: Keys to check for existence.
            
        Returns:
            True if all specified keys exist in the scenario, False otherwise.
            
        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"name": "Alice", "age": 30})
            >>> selector = ScenarioSelector(s)
            >>> selector.has_keys("name", "age")
            True
            >>> selector.has_keys("name", "city")
            False
        """
        return all(key in self.scenario for key in keys)
    
    def has_any_keys(self, *keys: str) -> bool:
        """
        Check if the scenario contains any of the specified keys.
        
        Args:
            *keys: Keys to check for existence.
            
        Returns:
            True if any of the specified keys exist in the scenario, False otherwise.
            
        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"name": "Alice", "age": 30})
            >>> selector = ScenarioSelector(s)
            >>> selector.has_any_keys("name", "city")
            True
            >>> selector.has_any_keys("city", "country")
            False
        """
        return any(key in self.scenario for key in keys)
    
    def filter_existing_keys(self, *keys: str) -> List[str]:
        """
        Filter the provided keys to only include those that exist in the scenario.
        
        Args:
            *keys: Keys to filter.
            
        Returns:
            A list containing only the keys that exist in the scenario.
            
        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"name": "Alice", "age": 30})
            >>> selector = ScenarioSelector(s)
            >>> selector.filter_existing_keys("name", "city", "age")
            ['name', 'age']
        """
        return [key for key in keys if key in self.scenario]


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
