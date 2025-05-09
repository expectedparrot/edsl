from typing import Optional, List, TYPE_CHECKING
from collections import UserList

from ..base import Base
from ..language_models import Model

from ..utilities import remove_edsl_version, dict_hash

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

    def code(self):
        pass
        
    def to_db(self, session):
        """Serialize this object to a database.
        
        This method persists the ModelList object to a database using the ORM implementation.
        
        Args:
            session: A SQLAlchemy session object for database operations
            
        Returns:
            The database ORM model representing this ModelList
            
        Examples:
            >>> from sqlalchemy import create_engine
            >>> from sqlalchemy.orm import sessionmaker
            >>> from edsl import Model
            >>> engine = create_engine('sqlite:///:memory:')
            >>> from edsl.language_models.orm import Base
            >>> Base.metadata.create_all(engine) # doctest: +SKIP
            >>> Session = sessionmaker(bind=engine)
            >>> session = Session() # doctest: +SKIP
            >>> ml = ModelList([Model.example()])
            >>> orm_obj = ml.to_db(session) # doctest: +SKIP
        """
        from ..language_models.orm import save_model_list
        return save_model_list(session, self)
    
    @classmethod
    def from_db(cls, session, model_list_id):
        """Create an instance from a database.
        
        This class method creates a ModelList instance from data stored in the database.
        
        Args:
            session: A SQLAlchemy session object for database operations
            model_list_id: The ID of the model list in the database
            
        Returns:
            ModelList: A reconstructed ModelList object from the database
            
        Examples:
            >>> from sqlalchemy import create_engine
            >>> from sqlalchemy.orm import sessionmaker
            >>> engine = create_engine('sqlite:///:memory:')
            >>> from edsl.language_models.orm import Base
            >>> Base.metadata.create_all(engine) # doctest: +SKIP
            >>> Session = sessionmaker(bind=engine)
            >>> session = Session() # doctest: +SKIP
            >>> ml = ModelList([Model.example()])
            >>> orm_obj = ml.to_db(session) # doctest: +SKIP
            >>> ml2 = ModelList.from_db(session, orm_obj.id) # doctest: +SKIP
        """
        from ..language_models.orm import load_model_list
        return load_model_list(session, model_list_id)

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
