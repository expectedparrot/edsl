from typing import Any, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
import inspect
    
class Path:
    def __init__(self, parent_object: Any):
        self.commands = []
        self.parent_object = parent_object
        self.object_sequence = [parent_object]

    @property
    def head(self):
        return self.object_sequence[-1]
        
    def available_commands(self):
        return self.head.polly_commands
    
    def _check_command(self, command_name, kwargs):
        # Find the command definition
        command_def = None
        for cmd in self.available_commands():
            if cmd['command_name'] == command_name:
                command_def = cmd
                break
        
        if command_def is None:
            raise ValueError(f"Command {command_name} not available for {self.head}")
        
        # Check that provided kwargs match expected kwargs
        expected_kwargs = set(command_def['kwargs'].keys())
        provided_kwargs = set(kwargs.keys())
        
        if expected_kwargs != provided_kwargs:
            raise ValueError(f"Command {command_name} expects kwargs {expected_kwargs}, but got {provided_kwargs}")
    
    def add_command(self, command_name: str, kwargs: dict):
        self._check_command(command_name, kwargs)
        self.commands.append({'command_name': command_name, 'kwargs': kwargs})
        next_object = self.head.copy()
        result = next_object.apply_command(command_name, kwargs)
        # If apply_command returns a different object (e.g., for transformations), use that
        if result is not next_object:
            next_object = result
        self.object_sequence.append(next_object)


if __name__ == "__main__":
    from edsl import AgentList 
    p = Path(AgentList.example())
    print(p.available_commands())
    p.add_command("add_instructions", {'instructions': "Do not harm humanity"})
    print(p.head[0].instruction)
