from typing import Optional, List, TYPE_CHECKING
from collections import UserList

from ..base import Base

if TYPE_CHECKING:
    pass

from ..utilities import remove_edsl_version, dict_hash

if TYPE_CHECKING:
    from ..inference_services.data_structures import AvailableModels
    from ..language_models import LanguageModel


class ModelList(Base, UserList):
    __documentation__ = """https://docs.expectedparrot.com/en/latest/language_models.html#module-edsl.language_models.ModelList"""

    def __init__(self, data: Optional["LanguageModel"] = None):
        """Initialize the ModelList class.

        # >>> from edsl import Model
        # >>> m = ModelList.from_scenario_list(Model.available())

        """
        if data is not None and isinstance(data, str):
            ml = ModelList.pull(data)
            self.__dict__.update(ml.__dict__)
            return
            
        if data is not None:
            super().__init__(data)
        else:
            super().__init__([])

    @property
    def names(self):
        """

        >>> ModelList.example().names
        {'...'}
        """
        return set([model.model for model in self])

    def __repr__(self):
        """Return a string representation of the ModelList.
        
        Uses traditional repr format when running doctests, otherwise uses
        rich-based display for better readability.
        """
        import os
        if os.environ.get("EDSL_RUNNING_DOCTESTS") == "True":
            return self._eval_repr_()
        else:
            return self._summary_repr()
    
    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the ModelList.
        
        This representation can be used with eval() to recreate the ModelList object.
        Used primarily for doctests and debugging.
        """
        return f"ModelList({super().__repr__()})"
    
    def _summary_repr(self, max_items: int = 5) -> str:
        """Generate a summary representation of the ModelList with Rich formatting.
        
        Args:
            max_items: Maximum number of items to show in lists before truncating
        """
        from rich.console import Console
        from rich.text import Text
        import io
        
        # Build the Rich text
        output = Text()
        output.append("ModelList(\n", style="bold cyan")
        output.append(f"    num_models={len(self)},\n", style="white")
        
        if len(self) > 0:
            # Collect model information
            model_info = []
            for model in list(self)[:max_items]:
                model_name = getattr(model, 'model', getattr(model, '_model_', 'unknown'))
                service_name = getattr(model, '_inference_service_', 'unknown')
                model_info.append(f"{model_name} ({service_name})")
            
            output.append("    models: [\n", style="white")
            for info in model_info:
                output.append(f"        ", style="white")
                output.append(f"{info}", style="yellow")
                output.append(",\n", style="white")
            
            if len(self) > max_items:
                output.append(f"        ... ({len(self) - max_items} more)\n", style="dim")
            
            output.append("    ]\n", style="white")
        else:
            output.append("    models: []\n", style="dim")
        
        output.append(")", style="bold cyan")
        
        # Render to string
        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        console.print(output, end="")
        return console.file.getvalue()

    def _summary(self):
        return {"models": len(self)}

    def __hash__(self):
        """Return a hash of the ModelList. This is used for comparison of ModelLists.

        >>> isinstance(hash(ModelList([])), int)
        True

        """
        return dict_hash(self.to_dict(sort=True, add_edsl_version=False))

    def to_scenario_list(self):
        from ..scenarios import ScenarioList
        from ..scenarios import Scenario

        sl = ScenarioList()
        for model in self:
            d = {"model_name": model.model, "service_name": model._inference_service_}
            d.update(model.parameters)
            sl.append(Scenario(d))
        return sl

    def filter(self, expression: str):
        sl = self.to_scenario_list()
        filtered_sl = sl.filter(expression)
        return self.from_scenario_list(filtered_sl)

    def tree(self, node_list: Optional[List[str]] = None):
        return self.to_scenario_list().tree(node_list)

    def table(
        self,
        *fields,
        tablefmt: Optional[str] = None,
        pretty_labels: Optional[dict] = None,
    ):
        """
        >>> ModelList.example().table('model_name')
        model_name
        ------------
        gpt-4o
        gpt-4o
        gpt-4o
        """
        return (
            self.to_scenario_list()
            .to_dataset()
            .table(*fields, tablefmt=tablefmt, pretty_labels=pretty_labels)
        )

    def to_list(self) -> list:
        return self.to_scenario_list().to_list()

    def to_dict(self, sort=False, add_edsl_version=True):
        if sort:
            model_list = sorted([model for model in self], key=lambda x: hash(x))
            d = {
                "models": [
                    model.to_dict(add_edsl_version=add_edsl_version)
                    for model in model_list
                ]
            }
        else:
            d = {
                "models": [
                    model.to_dict(add_edsl_version=add_edsl_version) for model in self
                ]
            }
        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "ModelList"

        return d

    @classmethod
    def from_names(self, *args, **kwargs):
        """A a model list from a list of names"""
        from .model import Model

        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        return ModelList([Model(model_name, **kwargs) for model_name in args])

    @classmethod
    def from_available_models(self, available_models_list: "AvailableModels"):
        """Create a ModelList from an AvailableModels object"""
        from .model import Model

        return ModelList(
            [
                Model(model.model_name, service_name=model.service_name)
                for model in available_models_list
            ]
        )

    @classmethod
    def from_scenario_list(cls, scenario_list):
        """Create a ModelList from a ScenarioList containing model_name and service_name fields.

        Args:
            scenario_list: ScenarioList with scenarios containing 'model_name' and 'service_name' fields

        Returns:
            ModelList with instantiated Model objects

        Example:
            >>> from edsl import Model
            >>> models_data = Model.available(service_name='openai')
            >>> model_list = ModelList.from_scenario_list(models_data)
        """
        from .model import Model

        models = []
        for scenario in scenario_list:
            # Check if scenario is already a Model-like object (from inference services)
            if hasattr(scenario, "model") and hasattr(scenario, "_inference_service_"):
                # Create a new Model object from the existing model-like object
                models.append(
                    Model(scenario.model, service_name=scenario._inference_service_)
                )
                continue
            elif isinstance(scenario, Model):
                models.append(scenario)
                continue

            # Handle scenario dict-like objects
            try:
                model_name = (
                    scenario["model_name"] if "model_name" in scenario else None
                )
                service_name = (
                    scenario["service_name"] if "service_name" in scenario else None
                )
            except (TypeError, KeyError):
                # Handle cases where scenario might not be dict-like
                model_name = getattr(scenario, "model_name", None)
                service_name = getattr(scenario, "service_name", None)

            if model_name and service_name:
                models.append(Model(model_name, service_name=service_name))
            else:
                missing_fields = []
                if not model_name:
                    missing_fields.append("model_name")
                if not service_name:
                    missing_fields.append("service_name")
                raise ValueError(
                    f"Scenario missing required fields: {missing_fields}. Scenario: {scenario}"
                )

        return cls(models)

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data):
        """
        Create a ModelList from a dictionary.

        >>> newm = ModelList.from_dict(ModelList.example().to_dict())
        >>> assert ModelList.example() == newm
        """
        from ..language_models import LanguageModel

        return cls(data=[LanguageModel.from_dict(model) for model in data["models"]])

    def code(self):
        pass

    @classmethod
    def example(cls, randomize: bool = False) -> "ModelList":
        """
        Returns an example ModelList instance.

        :param randomize: If True, uses Model's randomize method.
        """

        from .model import Model

        return cls([Model.example(randomize) for _ in range(3)])

    @classmethod
    def all(cls) -> "ModelList":
        """
        Returns all available models.
        """
        from .model import Model

        available_models = Model.available()
        return cls.from_scenario_list(available_models)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
