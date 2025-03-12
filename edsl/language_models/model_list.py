from typing import Optional, List, Union, TYPE_CHECKING
from collections import UserList

from simpleeval import EvalWithCompoundTypes, NameNotDefined

from ..base import Base
from ..language_models import Model

from ..utilities import remove_edsl_version, is_valid_variable_name, dict_hash
from ..utilities import Field, QueryExpression, apply_filter

if TYPE_CHECKING:
    from ..inference_services.data_structures import AvailableModels
    from ..language_models import LanguageModel

class ModelList(Base, UserList):
    __documentation__ = """https://docs.expectedparrot.com/en/latest/language_models.html#module-edsl.language_models.ModelList"""

    def __init__(self, data: Optional["LanguageModel"] = None):
        """Initialize the ScenarioList class.

        >>> from edsl import Model
        >>> m = ModelList(Model.available())

        """
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
        return f"ModelList({super().__repr__()})"

    def _summary(self):
        return {"models": len(self)}

    def __hash__(self):
        """Return a hash of the ModelList. This is used for comparison of ModelLists.

        >>> isinstance(hash(Model()), int)
        True

        """
        return dict_hash(self.to_dict(sort=True, add_edsl_version=False))

    def to_scenario_list(self):
        from ..scenarios import ScenarioList
        from ..scenarios import Scenario

        sl = ScenarioList()
        for model in self:
            d = {"model": model.model, "inference_service": model._inference_service_}
            d.update(model.parameters)
            sl.append(Scenario(d))
        return sl

    def tree(self, node_list: Optional[List[str]] = None):
        return self.to_scenario_list().tree(node_list)

    def table(
        self,
        *fields,
        tablefmt: Optional[str] = None,
        pretty_labels: Optional[dict] = None,
    ):
        """
        >>> ModelList.example().table('model')
        model
        -------
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
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        return ModelList([Model(model_name, **kwargs) for model_name in args])

    @classmethod
    def from_available_models(self, available_models_list: "AvailableModels"):
        """Create a ModelList from an AvailableModels object"""
        return ModelList(
            [
                Model(model.model_name, service_name=model.service_name)
                for model in available_models_list
            ]
        )

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

    def filter(self, expression: Union[str, QueryExpression]) -> "ModelList":
        """
        Filter models based on a boolean expression.

        Args:
            expression: Either a string containing a boolean expression or a QueryExpression
                created using Field objects (e.g., Field('model') == 'gpt-4').

        Returns:
            ModelList: A new ModelList containing only models that satisfy the expression.

        Examples:
            >>> from edsl import Model, ModelList, Field
            >>> models = ModelList([
            ...     Model('gpt-4o', temperature=0.7),
            ...     Model('claude-3-opus', temperature=0.5),
            ...     Model('gpt-3.5-turbo', temperature=0.9)
            ... ])
            >>> # Filter using string expression
            >>> models.filter("model == 'gpt-4o'")
            ModelList([Model('gpt-4o', temperature=0.7)])
            >>> # Filter using Field expression
            >>> models.filter(Field('temperature') > 0.6)
            ModelList([Model('gpt-4o', temperature=0.7), Model('gpt-3.5-turbo', temperature=0.9)])
            >>> # Combined expressions
            >>> models.filter((Field('model').contains('gpt')) & (Field('temperature') > 0.8))
            ModelList([Model('gpt-3.5-turbo', temperature=0.9)])
        """
        # Handle empty list case
        if len(self.data) == 0:
            return ModelList([])
            
        # If expression is a string, use string-based evaluation
        if isinstance(expression, str):
            def create_evaluator(model):
                """Create an evaluator for the given model."""
                # Combine model attributes into a dictionary for evaluation
                eval_dict = {
                    'model': model.model,
                    'inference_service': model._inference_service_
                }
                # Add all parameters
                eval_dict.update(model.parameters)
                return EvalWithCompoundTypes(names=eval_dict)

            try:
                # Filter models by evaluating the expression against each one
                new_data = []
                for model in self.data:
                    if create_evaluator(model).eval(expression):
                        new_data.append(model)
            except NameNotDefined as e:
                # If a field name doesn't exist, provide helpful error
                from ..language_models.exceptions import ModelListError
                sample_model = self.data[0] if self.data else None
                if sample_model:
                    available_fields = ", ".join(["model", "inference_service"] + list(sample_model.parameters.keys()))
                    error_msg = (
                        f"Error in filter: '{e}'. "
                        f"The field does not exist in model attributes. "
                        f"Available fields: {available_fields}"
                    )
                else:
                    error_msg = f"Error in filter: '{e}'. The ModelList is empty."
                raise ModelListError(error_msg) from None
            except Exception as e:
                from ..language_models.exceptions import ModelListError
                raise ModelListError(f"Error in filter. Exception: {e}")

        # If expression is a QueryExpression, use the field-based evaluation
        elif isinstance(expression, QueryExpression):
            try:
                # Create a list of dictionaries with model attributes for evaluation
                new_data = []
                for model in self.data:
                    # Create a dictionary representing all model attributes
                    model_dict = {
                        'model': model.model,
                        'inference_service': model._inference_service_
                    }
                    model_dict.update(model.parameters)
                    
                    # Evaluate the expression against this dictionary
                    if expression.evaluate(model_dict):
                        new_data.append(model)
            except Exception as e:
                from ..language_models.exceptions import ModelListError
                raise ModelListError(f"Error evaluating query expression: {str(e)}")
        else:
            from ..language_models.exceptions import ModelListError
            raise ModelListError(
                f"Expression must be a string or QueryExpression, got {type(expression)}"
            )

        return ModelList(new_data)
        
    def code(self):
        pass

    @classmethod
    def example(cls, randomize: bool = False) -> "ModelList":
        """
        Returns an example ModelList instance.

        :param randomize: If True, uses Model's randomize method.
        """

        return cls([Model.example(randomize) for _ in range(3)])


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
