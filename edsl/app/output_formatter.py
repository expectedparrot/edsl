import inspect

from typing import Any, Optional
from ..results import Results
from ..dataset import Dataset
from ..dataset.display.table_display import TableDisplay
from ..scenarios import ScenarioList, FileStore

relevant_classes = {
    Results: ['to_scenario_list', 'select', 'table', 'report_from_template'], 
    Dataset: ['table', 'expand', 'to_markdown', 'to_list'], 
    TableDisplay: ['flip'],
    FileStore: ['view', 'to_docx', 'save'],
    ScenarioList: ['to_survey', 'rename', 'zip', 'string_cat', 'add_value', 'to_ranked_scenario_list'],
}

white_list_methods = []
for cls, methods in relevant_classes.items():
    for method in methods:
        white_list_methods.append(getattr(cls, method))


white_list_commands = [f.__name__ for f in white_list_methods]
return_types = {f.__name__: inspect.signature(f).return_annotation for f in white_list_methods}

parent_class = {f.__name__: f.__qualname__.split('.')[0] for f in white_list_methods}

class OutputFormatter:

    def __init__(self, name: Optional[str] = None, description: Optional[str] = None, allowed_commands: Optional[list[str]] = None) -> None:
        self.name = name
        self.description = description
        if allowed_commands is None:
            allowed_commands = white_list_commands
        self.allowed_commands = allowed_commands

        self._stored_commands = []

    def __getattr__(self, name: str) -> Any:

        if name in self.allowed_commands:
    
            def method_proxy(*args, **kwargs):
                self._stored_commands.append((name, args, kwargs))
                return self

            return method_proxy

        # For unknown methods, raise AttributeError immediately
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'. "
            f"Use .then('{name}', ...) for post-run method chaining."
        )

    def render(self, results: Any) -> Any:
        if not self._stored_commands:
            return results

        for command, args, kwargs in self._stored_commands:
            results = getattr(results, command)(*args, **kwargs)

        return results

    # --- end of public API ---

    def to_dict(self) -> dict[str, Any]:
        """Serialize the formatter configuration and queued commands to a dict.

        Doctest:

        >>> of = OutputFormatter(name='calculator', description='demo', allowed_commands=['inc', 'mul']).inc(3).mul(2)
        >>> data = of.to_dict()
        >>> set(['name','description','allowed_commands','stored_commands']).issubset(set(data.keys()))
        True
        >>> data['name'], data['description']
        ('calculator', 'demo')
        >>> data['allowed_commands']
        ['inc', 'mul']
        >>> data['stored_commands'][0]['name']
        'inc'
        >>> isinstance(data['stored_commands'][0]['args'], list)
        True
        """
        return {
            "name": self.name,
            "description": self.description,
            "allowed_commands": list(self.allowed_commands),
            "stored_commands": [
                {"name": name, "args": list(args), "kwargs": kwargs}
                for name, args, kwargs in self._stored_commands
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutputFormatter":
        """Create an OutputFormatter from a dict produced by to_dict.

        Doctest:

        >>> data = {
        ...     'name': 'calculator',
        ...     'description': 'demo',
        ...     'allowed_commands': ['inc', 'mul'],
        ...     'stored_commands': [
        ...         {'name': 'inc', 'args': [3], 'kwargs': {}},
        ...         {'name': 'mul', 'args': [2], 'kwargs': {}},
        ...     ],
        ... }
        >>> of = OutputFormatter.from_dict(data)
        >>> of.name, of.description
        ('calculator', 'demo')
        >>> class Dummy:
        ...     def __init__(self):
        ...         self.value = 1
        ...     def inc(self, n):
        ...         self.value += n
        ...         return self
        ...     def mul(self, n):
        ...         self.value *= n
        ...         return self
        >>> d = Dummy()
        >>> of.render(d)
        <...Dummy object at ...>
        >>> d.value
        8
        """
        allowed = data.get("allowed_commands")
        instance = cls(name=data.get("name"), description=data.get("description"), allowed_commands=allowed)
        stored = []
        for item in data.get("stored_commands", []):
            name = item["name"]
            args = tuple(item.get("args", []))
            kwargs = dict(item.get("kwargs", {}))
            stored.append((name, args, kwargs))
        instance._stored_commands = stored
        return instance


from collections import UserList

class OutputFormatters(UserList):
    def __init__(self, data: list[OutputFormatter] = None):
        super().__init__(data)

        self.mapping = {f.name: f for f in (data or [])}
        self.default = None

    def __repr__(self) -> str:
        return f"OutputFormatters({self.data})"

    def set_default(self, name: str) -> None:
        if name not in self.mapping:
            raise ValueError(f"Formatter {name} not found")
        self.default = name

    def get_default(self) -> OutputFormatter:
        if self.default is not None:
            return self.mapping[self.default]
        return self.data[0]

    def get_formatter(self, name: str) -> OutputFormatter:
        """Get a formatter by name."""
        if name not in self.mapping:
            raise ValueError(f"Formatter '{name}' not found. Available formatters: {list(self.mapping.keys())}")
        return self.mapping[name]

    def to_dict(self, add_edsl_version: bool = True) -> dict[str, Any]:
        """Serialize the collection of formatters and default selection to a dict.

        Doctest:

        >>> of1 = OutputFormatter(name='a', description=None, allowed_commands=['table']).table()
        >>> of2 = OutputFormatter(name='b', description=None, allowed_commands=['flip'])
        >>> ofs = OutputFormatters([of1, of2])
        >>> ofs.set_default('a')
        >>> data = ofs.to_dict()
        >>> set(['formatters','default']).issubset(set(data.keys()))
        True
        >>> data['default']
        'a'
        >>> len(data['formatters'])
        2
        """
        return {
            "formatters": [formatter.to_dict() for formatter in self.data],
            "default": self.default,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutputFormatters":
        """Create an OutputFormatters instance from a dict produced by to_dict.

        Doctest:

        >>> payload = {
        ...   'formatters': [
        ...       {'name': 'a', 'description': None, 'allowed_commands': ['table'], 'stored_commands': [{'name':'table','args': [], 'kwargs': {}}]},
        ...       {'name': 'b', 'description': None, 'allowed_commands': ['flip'], 'stored_commands': []},
        ...   ],
        ...   'default': 'a',
        ... }
        >>> ofs = OutputFormatters.from_dict(payload)
        >>> isinstance(ofs, OutputFormatters)
        True
        >>> ofs.get_default().name
        'a'
        >>> len(ofs)
        2
        """
        formatter_dicts = data.get("formatters", [])
        formatters = [OutputFormatter.from_dict(fd) for fd in formatter_dicts]
        instance = cls(formatters)
        default_name = data.get("default")
        if default_name is not None:
            instance.set_default(default_name)
        return instance

if __name__ == "__main__":

    of = OutputFormatter().table().flip()
    from edsl.results import Results
    results = Results.example()
    print(of.render(results))
    