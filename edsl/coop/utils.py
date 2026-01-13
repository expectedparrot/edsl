import math
from typing import Literal, Optional, Type, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents import Agent, AgentList
    from ..notebooks import Notebook
    from ..results import Results
    from ..scenarios import Scenario, ScenarioList
    from ..surveys import Survey
    from ..macros.macro import Macro
    from ..macros.composite_macro import CompositeMacro
    from ..questions import QuestionBase
    from ..caching import Cache
    from ..language_models import ModelList
    from ..language_models import LanguageModel

EDSLObject = Union[
    "Agent",
    "AgentList",
    "Cache",
    "LanguageModel",
    "ModelList",
    "Notebook",
    Type["QuestionBase"],
    "Results",
    "Scenario",
    "ScenarioList",
    "Survey",
    "Macro",
    "CompositeMacro",
]

ObjectType = Literal[
    "agent",
    "agent_list",
    "cache",
    "model",
    "model_list",
    "notebook",
    "question",
    "results",
    "scenario",
    "scenario_list",
    "survey",
    "macro",
    "composite_macro",
]


RemoteJobStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "cancelling",
    "partial_failed",
]

VisibilityType = Literal[
    "private",
    "public",
    "unlisted",
]


class ObjectRegistry:
    """
    Registry that maps between EDSL class types and their cloud storage object types.

    This utility class maintains a bidirectional mapping between EDSL Python classes
    (like Survey, Agent, Results) and their corresponding object type identifiers
    used in the cloud storage system. It enables the proper serialization,
    deserialization, and type checking for objects stored in Expected Parrot's
    cloud services.

    The registry is used by the Coop client to:
    1. Determine the correct object type when uploading EDSL objects
    2. Instantiate the correct class when downloading objects
    3. Validate that retrieved objects match expected types

    Attributes:
        objects (list): List of mappings between object types and EDSL classes
        object_type_to_edsl_class (dict): Maps object type strings to EDSL classes
        edsl_class_to_object_type (dict): Maps EDSL class names to object type strings
    """

    @classmethod
    def _get_objects(cls):
        """Lazy import of all EDSL classes to avoid circular imports and speed up module load"""
        from ..agents import Agent, AgentList
        from ..notebooks import Notebook
        from ..results import Results
        from ..scenarios import Scenario, ScenarioList
        from ..surveys import Survey
        from ..macros.macro import Macro
        from ..macros.composite_macro import CompositeMacro
        from ..questions import QuestionBase
        from ..language_models import LanguageModel, ModelList
        from ..caching import Cache

        return [
            {"object_type": "agent", "edsl_class": Agent},
            {"object_type": "agent_list", "edsl_class": AgentList},
            {"object_type": "cache", "edsl_class": Cache},
            {"object_type": "model", "edsl_class": LanguageModel},
            {"object_type": "model_list", "edsl_class": ModelList},
            {"object_type": "notebook", "edsl_class": Notebook},
            {"object_type": "question", "edsl_class": QuestionBase},
            {"object_type": "results", "edsl_class": Results},
            {"object_type": "scenario", "edsl_class": Scenario},
            {"object_type": "scenario_list", "edsl_class": ScenarioList},
            {"object_type": "survey", "edsl_class": Survey},
            {"object_type": "macro", "edsl_class": Macro},
            {"object_type": "composite_macro", "edsl_class": CompositeMacro},
        ]

    @property
    def objects(self):
        """Get the objects list with lazy imports"""
        return self._get_objects()

    @property
    def object_type_to_edsl_class(self):
        """Create mapping from object type to EDSL class with lazy imports"""
        return {o["object_type"]: o["edsl_class"] for o in self.objects}

    @property
    def edsl_class_to_object_type(self):
        """Create mapping from EDSL class name to object type with lazy imports"""
        return {o["edsl_class"].__name__: o["object_type"] for o in self.objects}

    @classmethod
    def get_object_type_by_edsl_class(cls, edsl_object: EDSLObject) -> ObjectType:
        """
        Get the object type identifier for an EDSL class or instance.

        This method determines the appropriate object type string for a given EDSL class
        or instance, which is needed when storing the object in the cloud.

        Parameters:
            edsl_object (EDSLObject): An EDSL class (type) or instance

        Returns:
            ObjectType: The corresponding object type string (e.g., "survey", "agent")

        Raises:
            ValueError: If no mapping exists for the provided object

        Notes:
            - Special handling for Question classes, which all map to "question"
            - Works with both class types and instances
        """
        # Handle both class objects and instances
        if isinstance(edsl_object, type):
            edsl_class_name = edsl_object.__name__
        else:
            edsl_class_name = type(edsl_object).__name__

        # Special handling for question classes
        if edsl_class_name.startswith("Question"):
            edsl_class_name = "QuestionBase"

        # Look up the object type
        edsl_class_to_object_type = {
            o["edsl_class"].__name__: o["object_type"] for o in cls._get_objects()
        }
        object_type = edsl_class_to_object_type.get(edsl_class_name)

        from ..scenarios import Scenario

        if isinstance(edsl_object, Scenario):
            return "scenario"

        if object_type is None:
            from .exceptions import CoopValueError

            raise CoopValueError(f"Object type not found for {edsl_object=}")

        return object_type

    @classmethod
    def get_edsl_class_by_object_type(cls, object_type: ObjectType) -> EDSLObject:
        """
        Get the EDSL class for a given object type identifier.

        This method returns the appropriate EDSL class for a given object type string,
        which is needed when retrieving objects from the cloud.

        Parameters:
            object_type (ObjectType): The object type string (e.g., "survey", "agent")

        Returns:
            EDSLObject: The corresponding EDSL class

        Raises:
            ValueError: If no mapping exists for the provided object type
        """
        object_type_to_edsl_class = {
            o["object_type"]: o["edsl_class"] for o in cls._get_objects()
        }
        EDSL_class = object_type_to_edsl_class.get(object_type)
        if EDSL_class is None:
            from .exceptions import CoopValueError

            raise CoopValueError(f"EDSL class not found for {object_type=}")
        return EDSL_class

    @classmethod
    def get_registry(
        cls,
        subclass_registry: Optional[dict] = None,
        exclude_classes: Optional[list] = None,
    ) -> dict:
        """
        Get a filtered registry of EDSL classes.

        This method returns a dictionary of EDSL classes, optionally excluding
        classes that are already registered elsewhere or explicitly excluded.

        Parameters:
            subclass_registry (dict, optional): Dictionary of classes to exclude
                because they are already registered elsewhere
            exclude_classes (list, optional): List of class names to explicitly exclude

        Returns:
            dict: Dictionary mapping class names to EDSL classes

        Notes:
            - This method is useful for building registries of classes that
              can be serialized and stored in the cloud
            - It helps avoid duplicate registrations of classes
        """
        if subclass_registry is None:
            subclass_registry = {}
        if exclude_classes is None:
            exclude_classes = []

        return {
            class_name: o["edsl_class"]
            for o in cls._get_objects()
            if (class_name := o["edsl_class"].__name__) not in subclass_registry
            and class_name not in exclude_classes
        }


class CostConverter:
    CENTS_PER_CREDIT = 1

    @staticmethod
    def _credits_to_minicredits(credits: float) -> float:
        """
        Converts credits to minicredits.

        Current conversion: minicredits = credits * 100
        """

        return credits * 100

    @staticmethod
    def _minicredits_to_credits(minicredits: float) -> float:
        """
        Converts minicredits to credits.

        Current conversion: credits = minicredits / 100
        """

        return minicredits / 100

    def _usd_to_minicredits(self, usd: float) -> float:
        """Converts USD to minicredits."""

        cents = usd * 100
        credits_per_cent = 1 / int(self.CENTS_PER_CREDIT)

        credits = cents * credits_per_cent

        minicredits = self._credits_to_minicredits(credits)

        return minicredits

    def _minicredits_to_usd(self, minicredits: float) -> float:
        """Converts minicredits to USD."""

        credits = self._minicredits_to_credits(minicredits)

        cents_per_credit = int(self.CENTS_PER_CREDIT)

        cents = credits * cents_per_credit
        usd = cents / 100

        return usd

    def usd_to_credits(self, usd: float) -> float:
        """Converts USD to credits."""

        minicredits = math.ceil(self._usd_to_minicredits(usd))
        credits = self._minicredits_to_credits(minicredits)
        return round(credits, 2)

    def credits_to_usd(self, credits: float) -> float:
        """Converts credits to USD."""

        minicredits = math.ceil(self._credits_to_minicredits(credits))
        usd = self._minicredits_to_usd(minicredits)
        return usd
