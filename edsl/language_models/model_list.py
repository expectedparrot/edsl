"""
ModelList provides a collection of LanguageModel objects with git-like versioning.

The ModelList module extends the functionality of a simple list of Model objects,
providing operations for filtering, transformation, and serialization with
event-sourced versioning support.

Doctest (basic usage)
    >>> from edsl.language_models import ModelList
    >>> from edsl.language_models.model import Model
    >>> ml = ModelList([Model.example()])
    >>> len(ml)
    1
"""

from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING, Any, Union
from collections.abc import MutableSequence

from ..base import Base
from ..utilities import remove_edsl_version, dict_hash

if TYPE_CHECKING:
    from ..inference_services.data_structures import AvailableModels
    from ..language_models import LanguageModel

from edsl.versioning import GitMixin, event
from edsl.store import Store, AppendRowEvent, RemoveRowsEvent, ClearEntriesEvent, apply_event


class ModelCodec:
    """Codec for Model objects - handles encoding/decoding for the Store."""
    
    def encode(self, obj: Union["LanguageModel", dict[str, Any]]) -> dict[str, Any]:
        """Encode a Model object to a dictionary for storage."""
        if isinstance(obj, dict):
            return dict(obj)
        return obj.to_dict(add_edsl_version=False)
    
    def decode(self, data: dict[str, Any]) -> "LanguageModel":
        """Decode a dictionary back to a Model object."""
        from ..language_models import LanguageModel
        return LanguageModel.from_dict(data)


class ModelList(GitMixin, MutableSequence, Base):
    """
    A collection of LanguageModel objects with event-sourced versioning.
    """
    
    __documentation__ = """https://docs.expectedparrot.com/en/latest/language_models.html#module-edsl.language_models.ModelList"""

    # Event-sourcing configuration
    _versioned = 'store'
    _store_class = Store
    _event_handler = apply_event
    _codec = ModelCodec()

    _allowed_attrs = frozenset({
        'store',
        '_git', '_needs_git_init', '_last_push_result',
    })

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._allowed_attrs:
            super().__setattr__(name, value)
        else:
            raise AttributeError(
                f"Cannot set attribute '{name}' on ModelList. "
                f"ModelList is immutable - use event-based methods to modify data."
            )

    def __init__(self, data: Optional[List["LanguageModel"]] = None):
        """Initialize the ModelList."""
        super().__init__()
        
        if data is not None and isinstance(data, str):
            ml = ModelList.pull(data)
            self.store = Store(entries=list(ml.store.entries), meta=dict(ml.store.meta))
            return

        data_to_store = []
        for item in data or []:
            data_to_store.append(self._codec.encode(item))
        self.store = Store(entries=data_to_store, meta={})

    # ========== Properties (read from Store) ==========

    @property
    def data(self) -> List["LanguageModel"]:
        """Decode store entries to Model objects on read."""
        return [self._codec.decode(row) for row in self.store.entries]

    @property
    def names(self):
        """Return a set of model names.

        >>> ModelList.example().names
        {'...'}
        """
        return set([model.model for model in self])

    # ========== MutableSequence Abstract Methods ==========
    
    def __getitem__(self, index):
        if isinstance(index, slice):
            return ModelList(self.data[index])
        return self._codec.decode(self.store.entries[index])

    def __setitem__(self, index, value):
        raise TypeError("ModelList does not support item assignment. Use append().")

    def __delitem__(self, index):
        raise TypeError("ModelList does not support item deletion. Use remove().")

    def __len__(self):
        return len(self.store.entries)

    def insert(self, index, value):
        raise TypeError("ModelList does not support insert(). Use append().")

    def __iter__(self):
        for entry in self.store.entries:
            yield self._codec.decode(entry)

    # ========== Event-Sourced Mutations ==========

    @event
    def append(self, item: "LanguageModel") -> AppendRowEvent:
        """Append a model to the list."""
        return AppendRowEvent(row=self._codec.encode(item))

    @event
    def remove(self, item: "LanguageModel") -> RemoveRowsEvent:
        """Remove a model from the list."""
        item_dict = self._codec.encode(item)
        for i, entry in enumerate(self.store.entries):
            if entry == item_dict:
                return RemoveRowsEvent(indices=(i,))
        raise ValueError("Model not found in list")

    @event
    def clear(self) -> ClearEntriesEvent:
        """Remove all models from the list."""
        return ClearEntriesEvent()

    # ========== Representation ==========

    def _eval_repr_(self) -> str:
        items = [f"Model(model_name='{m.model}')" for m in self]
        return f"ModelList([{', '.join(items)}])"

    def _summary_repr(self, max_items: int = 5) -> str:
        from rich.console import Console
        from rich.text import Text
        import io
        from edsl.config import RICH_STYLES

        output = Text()
        output.append("ModelList(\n", style=RICH_STYLES["primary"])
        output.append(f"    num_models={len(self)},\n", style=RICH_STYLES["default"])

        if len(self) > 0:
            model_info = []
            for model in list(self):
                model_name = getattr(model, "model", getattr(model, "_model_", "unknown"))
                service_name = getattr(model, "_inference_service_", "unknown")
                model_info.append(f"{model_name} ({service_name})")

            output.append("    models: [\n", style=RICH_STYLES["default"])
            for info in model_info:
                output.append("        ", style=RICH_STYLES["default"])
                output.append(f"{info}", style=RICH_STYLES["secondary"])
                output.append(",\n", style=RICH_STYLES["default"])
            output.append("    ]\n", style=RICH_STYLES["default"])
        else:
            output.append("    models: []\n", style=RICH_STYLES["dim"])

        output.append(")", style=RICH_STYLES["primary"])

        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        console.print(output, end="")
        return console.file.getvalue()

    def _summary(self):
        return {"models": len(self)}

    # ========== Hashing & Equality ==========

    def __hash__(self):
        """Return a hash of the ModelList.

        >>> isinstance(hash(ModelList([])), int)
        True
        """
        return dict_hash(self.to_dict(sort=True, add_edsl_version=False))

    def __eq__(self, other):
        if not isinstance(other, ModelList):
            return False
        return self.to_dict(sort=True, add_edsl_version=False) == other.to_dict(sort=True, add_edsl_version=False)

    # ========== Conversion Methods ==========

    def to_scenario_list(self):
        """Convert to a ScenarioList."""
        from ..scenarios import ScenarioList, Scenario

        sl = ScenarioList()
        for model in self:
            d = {"model_name": model.model, "service_name": model._inference_service_}
            d.update(model.parameters)
            sl = sl.append(Scenario(d))
        return sl

    def filter(self, expression: str):
        """Filter models by an expression."""
        sl = self.to_scenario_list()
        filtered_sl = sl.filter(expression)
        return self.from_scenario_list(filtered_sl)

    def tree(self, node_list: Optional[List[str]] = None):
        return self.to_scenario_list().tree(node_list)

    def table(self, *fields, tablefmt: Optional[str] = None, pretty_labels: Optional[dict] = None):
        """Display as a table.
        
        >>> ModelList.example().table('model_name')
        model_name
        ------------
        gpt-4o
        gpt-4o
        gpt-4o
        """
        return self.to_scenario_list().to_dataset().table(*fields, tablefmt=tablefmt, pretty_labels=pretty_labels)

    def to_list(self) -> list:
        return self.to_scenario_list().to_list()

    # ========== Serialization ==========

    def to_dict(self, sort=False, add_edsl_version=True):
        """Serialize to a dictionary."""
        if sort:
            model_list = sorted(list(self), key=lambda x: hash(x))
            d = {"models": [model.to_dict(add_edsl_version=add_edsl_version) for model in model_list]}
        else:
            d = {"models": [model.to_dict(add_edsl_version=add_edsl_version) for model in self]}
        if add_edsl_version:
            from .. import __version__
            d["edsl_version"] = __version__
            d["edsl_class_name"] = "ModelList"
        return d

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data):
        """Create a ModelList from a dictionary.

        >>> newm = ModelList.from_dict(ModelList.example().to_dict())
        >>> assert ModelList.example() == newm
        """
        from ..language_models import LanguageModel
        return cls(data=[LanguageModel.from_dict(model) for model in data["models"]])

    # ========== Factory Methods ==========

    @classmethod
    def from_names(cls, *args, **kwargs):
        from .model import Model
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        return ModelList([Model(model_name, **kwargs) for model_name in args])

    @classmethod
    def from_available_models(cls, available_models_list: "AvailableModels"):
        from .model import Model
        return ModelList([Model(model.model_name, service_name=model.service_name) for model in available_models_list])

    @classmethod
    def from_scenario_list(cls, scenario_list):
        """Create a ModelList from a ScenarioList."""
        from .model import Model

        models = []
        for scenario in scenario_list:
            if hasattr(scenario, "model") and hasattr(scenario, "_inference_service_"):
                models.append(Model(scenario.model, service_name=scenario._inference_service_))
            elif isinstance(scenario, Model):
                models.append(scenario)
            else:
                try:
                    model_name = scenario["model_name"] if "model_name" in scenario else None
                    service_name = scenario["service_name"] if "service_name" in scenario else None
                except (TypeError, KeyError):
                    model_name = getattr(scenario, "model_name", None)
                    service_name = getattr(scenario, "service_name", None)

                if model_name and service_name:
                    models.append(Model(model_name, service_name=service_name))
                else:
                    missing = [f for f in ["model_name", "service_name"] if not locals().get(f.replace("_name", ""))]
                    raise ValueError(f"Scenario missing required fields: {missing}. Scenario: {scenario}")
        return cls(models)

    @classmethod
    def example(cls, randomize: bool = False) -> "ModelList":
        from .model import Model
        return cls([Model.example(randomize) for _ in range(3)])

    @classmethod
    def all(cls) -> "ModelList":
        from .model import Model
        return cls.from_scenario_list(Model.available())

    def code(self):
        pass


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

