from abc import ABC, abstractmethod
import asyncio
from typing import Coroutine, Dict, Any, Optional, TYPE_CHECKING

from ..utilities.decorators import jupyter_nb_handler

if TYPE_CHECKING:
    from ..prompts import Prompt
    from ..caching import Cache
    from ..questions import QuestionBase
    from ..scenarios import Scenario
    from ..surveys.memory import MemoryPlan
    from ..language_models import LanguageModel
    from ..surveys import Survey
    from ..agents import Agent
    from ..key_management import KeyLookup

from ..data_transfer_models import EDSLResultObjectInput
from .prompt_constructor import PromptConstructor
from .prompt_helpers import PromptPlan


class InvigilatorBase(ABC):
    """
    Abstract base class for invigilators that administer questions to agents.
    
    An invigilator is responsible for the entire process of administering a question
    to an agent, including:
    1. Constructing appropriate prompts based on the question, scenario, and agent
    2. Handling agent-specific presentation of the question
    3. Processing model responses and validating them
    4. Managing memory and state across sequential questions
    5. Handling errors and validation failures
    
    This abstract base class defines the interface that all invigilators must implement
    and provides common functionality. Concrete subclasses implement the abstract
    async_answer_question method to define the specific question-answering behavior.
    
    Technical architecture:
    - Uses async/await pattern for efficient concurrent processing
    - Maintains references to agent, question, scenario, model and other components
    - Delegates prompt construction to the PromptConstructor class
    - Manages caching and memory for efficient execution
    
    Examples:
        >>> # Example usage, returning a test response
        >>> InvigilatorBase.example().answer_question()
        {'message': [{'text': 'SPAM!'}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}
        
        >>> # Example of error handling
        >>> InvigilatorBase.example().get_failed_task_result(failure_reason="Failed to get response").comment
        'Failed to get response'
        
    Implementation note:
    Concrete invigilator classes must implement the async_answer_question method,
    which performs the actual question administration and returns the result.
    """

    def __init__(
        self,
        agent: "Agent",
        question: "QuestionBase",
        scenario: "Scenario",
        model: "LanguageModel",
        memory_plan: "MemoryPlan",
        current_answers: dict,
        survey: Optional["Survey"],
        cache: Optional["Cache"] = None,
        iteration: Optional[int] = 1,
        additional_prompt_data: Optional[dict] = None,
        raise_validation_errors: Optional[bool] = True,
        prompt_plan: Optional["PromptPlan"] = None,
        key_lookup: Optional["KeyLookup"] = None,
    ):
        """
        Initialize a new Invigilator.
        
        This constructor sets up an invigilator with all the components required to
        administer a question to an agent. It establishes references to the agent,
        question, scenario, language model, and other components that participate in
        the question-asking process.
        
        Args:
            agent: The agent to which the question will be administered.
            question: The question to be asked.
            scenario: The scenario providing context for the question.
            model: The language model to use for generating responses (for AI agents).
            memory_plan: Plan for managing memory across questions in a survey.
            current_answers: Dictionary of answers to previous questions.
            survey: Optional reference to the parent survey.
            cache: Optional cache for storing and retrieving responses.
            iteration: Counter for tracking question repetitions (for retry logic).
            additional_prompt_data: Additional data to include in prompts.
            raise_validation_errors: Whether to raise exceptions on validation errors.
            prompt_plan: Custom prompt plan to use instead of the default.
            key_lookup: Optional key lookup for API key management.
            
        Technical Notes:
            - The current_answers dict allows for referencing previous answers in prompts
            - The memory_plan controls what information is carried forward between questions
            - The prompt_plan configures the structure of system and user prompts
            - The raw_model_response field stores the unprocessed response from the model
        """
        self.agent = agent
        self.question = question
        self.scenario = scenario
        self.model = model
        self.memory_plan = memory_plan
        self.current_answers = current_answers or {}
        self.iteration = iteration
        self.additional_prompt_data = additional_prompt_data
        self.cache = cache
        self.survey = survey
        self.raise_validation_errors = raise_validation_errors
        self.key_lookup = key_lookup

        # Initialize prompt plan (default or custom)
        if prompt_plan is None:
            self.prompt_plan = PromptPlan()
        else:
            self.prompt_plan = prompt_plan

        # Storage for the raw model response
        self.raw_model_response = None

    @property
    def prompt_constructor(self) -> PromptConstructor:
        """
        Get the prompt constructor for this invigilator.
        
        The prompt constructor is responsible for generating the prompts that will be
        sent to the language model based on the question, scenario, agent, and other 
        context. This property lazily creates and returns a PromptConstructor instance
        configured for this invigilator.
        
        Returns:
            PromptConstructor: A prompt constructor instance configured for this invigilator.
            
        Technical Notes:
            - This uses the factory method from_invigilator on PromptConstructor
            - The constructor has access to all the context of this invigilator
            - The prompt_plan controls the structure and components of the prompts
            - This is a key part of the separation of concerns in the invigilator architecture
        """
        return PromptConstructor.from_invigilator(self, prompt_plan=self.prompt_plan)

    def to_dict(self, include_cache: bool = False) -> Dict[str, Any]:
        """
        Serialize the invigilator to a dictionary.
        
        This method serializes the invigilator and all its attributes to a dictionary
        representation that can be stored, transmitted, or used to recreate an equivalent
        invigilator. It handles complex nested objects by recursively serializing them
        if they have a to_dict method.
        
        Args:
            include_cache: Whether to include the cache in the serialized output.
                          Defaults to False as the cache can be very large.
                          
        Returns:
            A dictionary representation of the invigilator.
            
        Technical Notes:
            - Objects with a to_dict method are serialized recursively
            - Primitive types (int, float, str, bool, dict, list) are included directly
            - Other objects are converted to strings
            - The cache is optionally included based on the include_cache parameter
        """
        attributes = [
            "agent",
            "question",
            "scenario",
            "model",
            "memory_plan",
            "current_answers",
            "iteration",
            "additional_prompt_data",
            "survey",
            "raw_model_response",
        ]
        if include_cache:
            attributes.append("cache")

        def serialize_attribute(attr):
            """Helper function to serialize a single attribute."""
            value = getattr(self, attr)
            if value is None:
                return None
            if hasattr(value, "to_dict"):
                return value.to_dict()
            if isinstance(value, (int, float, str, bool, dict, list)):
                return value
            return str(value)

        return {attr: serialize_attribute(attr) for attr in attributes}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InvigilatorBase":
        """
        Create an invigilator from a dictionary representation.
        
        This class method deserializes an invigilator from a dictionary, typically
        one created by the to_dict method. It recursively deserializes nested objects
        using their from_dict methods.
        
        Args:
            data: Dictionary representation of an invigilator.
            
        Returns:
            An invigilator instance reconstructed from the dictionary.
            
        Technical Notes:
            - This method implements the inverse of to_dict
            - Complex objects are reconstructed using their respective from_dict methods
            - The mapping between attribute names and classes is defined in attributes_to_classes
            - Special handling is provided for raw_model_response which is set after construction
            - This method supports the persistence and restoration of invigilator state
        """
        from ..agents import Agent
        from ..questions import QuestionBase
        from ..scenarios import Scenario
        from ..surveys.memory import MemoryPlan
        from ..language_models import LanguageModel
        from ..surveys import Survey
        from ..data import Cache

        # Map attribute names to their corresponding classes
        attributes_to_classes = {
            "agent": Agent,
            "question": QuestionBase,
            "scenario": Scenario,
            "model": LanguageModel,
            "memory_plan": MemoryPlan,
            "survey": Survey,
            "cache": Cache,
        }
        
        # Reconstruct complex objects
        d = {}
        for attr, cls_ in attributes_to_classes.items():
            if attr in data and data[attr] is not None:
                if attr not in data:
                    d[attr] = {}
                else:
                    d[attr] = cls_.from_dict(data[attr])

        # Copy primitive data directly
        d["current_answers"] = data["current_answers"]
        d["iteration"] = data["iteration"]
        d["additional_prompt_data"] = data["additional_prompt_data"]

        # Create the invigilator instance
        invigilator = cls(**d)
        
        # Set raw_model_response after construction
        invigilator.raw_model_response = data.get("raw_model_response")
        return invigilator

    def __repr__(self) -> str:
        """
        Get a string representation of the Invigilator.
        
        This method creates a detailed string representation of the invigilator
        including all its major components. This is useful for debugging and logging.
        
        Returns:
            A string representation of the invigilator.
            
        Examples:
            >>> InvigilatorBase.example().__repr__()
            'InvigilatorExample(...)'
        """
        return f"{self.__class__.__name__}(agent={repr(self.agent)}, question={repr(self.question)}, scenario={repr(self.scenario)}, model={repr(self.model)}, memory_plan={repr(self.memory_plan)}, current_answers={repr(self.current_answers)}, iteration={repr(self.iteration)}, additional_prompt_data={repr(self.additional_prompt_data)}, cache={repr(self.cache)})"

    def get_failed_task_result(self, failure_reason: str) -> EDSLResultObjectInput:
        """
        Create a result object for a failed question-answering task.
        
        This method constructs a standardized result object that represents a failed
        attempt to answer a question. The result includes the failure reason and
        context information, allowing for consistent handling of failures throughout
        the system.
        
        Args:
            failure_reason: Description of why the question-answering task failed.
            
        Returns:
            An EDSLResultObjectInput representing the failed task.
            
        Technical Notes:
            - Used for both expected failures (e.g., skip logic) and unexpected errors
            - Maintains a consistent structure for all results, regardless of success or failure
            - Includes the question name and prompts for context and debugging
            - Sets all response-related fields to None to indicate no response was obtained
        """
        data = {
            "answer": None,
            "generated_tokens": None,
            "comment": failure_reason,
            "question_name": self.question.question_name,
            "prompts": self.get_prompts(),
            "cached_response": None,
            "raw_model_response": None,
            "cache_used": None,
            "cache_key": None,
        }
        return EDSLResultObjectInput(**data)

    def get_prompts(self) -> Dict[str, "Prompt"]:
        """
        Get the prompts used by this invigilator.
        
        This base implementation returns placeholder prompts. Subclasses should
        override this method to provide the actual prompts used in question answering.
        
        Returns:
            A dictionary mapping prompt types to Prompt objects.
            
        Technical Notes:
            - This is a fallback implementation that returns "NA" prompts
            - Concrete invigilator implementations generate real prompts using the prompt_constructor
            - The returned dictionary uses standardized keys like "user_prompt" and "system_prompt"
        """
        from ..prompts import Prompt

        return {
            "user_prompt": Prompt("NA"),
            "system_prompt": Prompt("NA"),
        }

    @abstractmethod
    async def async_answer_question(self) -> Any:
        """
        Asynchronously administer a question to an agent and get the response.
        
        This abstract method must be implemented by concrete invigilator subclasses.
        It should handle the entire process of administering a question to an agent
        and processing the response.
        
        Returns:
            The processed response from the agent.
            
        Technical Notes:
            - This is an async method to support efficient concurrent execution
            - Different invigilator types implement this differently:
              - InvigilatorAI: Sends prompts to a language model
              - InvigilatorHuman: Displays questions to a human user
              - InvigilatorFunctional: Executes a function to generate responses
        """
        pass

    @jupyter_nb_handler
    def answer_question(self) -> Coroutine:
        """
        Get the answer to the question from the agent.
        
        This method creates and returns a coroutine that, when awaited, will
        administer the question to the agent and return the response. It
        handles the async execution details and provides a convenient interface
        for both async and sync contexts.
        
        Returns:
            A coroutine that, when awaited, returns the agent's response.
            
        Technical Notes:
            - The @jupyter_nb_handler decorator enables this to work properly in Jupyter notebooks
            - This method uses asyncio.gather to await the async_answer_question method
            - It acts as a bridge between the async and sync parts of the system
            - In synchronous contexts, this method can be called directly to get the response
        """
        async def main():
            """Execute the question-answering process and return the result."""
            results = await asyncio.gather(self.async_answer_question())
            return results[0]  # Since there's only one task, return its result

        return main()

    @classmethod
    def example(
        cls, 
        throw_an_exception: bool = False, 
        question: Optional["QuestionBase"] = None, 
        scenario: Optional["Scenario"] = None, 
        survey: Optional["Survey"] = None
    ) -> "InvigilatorBase":
        """
        Create an example invigilator for testing and documentation.
        
        This factory method creates a concrete implementation of the InvigilatorBase
        with predefined components suitable for testing, examples, and documentation.
        It supports customization through parameters and can be configured to simulate
        error conditions.
        
        Args:
            throw_an_exception: If True, the model will raise an exception when called.
            question: Custom question to use instead of the default.
            scenario: Custom scenario to use instead of the default.
            survey: Custom survey to use instead of the default.
            
        Returns:
            A concrete InvigilatorBase instance ready for testing.
            
        Examples:
            >>> # Basic example with default components
            >>> InvigilatorBase.example()
            InvigilatorExample(...)
            
            >>> # Example answering a question with a canned response
            >>> InvigilatorBase.example().answer_question()
            {'message': [{'text': 'SPAM!'}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}
            
            >>> # Example that simulates an error condition
            >>> InvigilatorBase.example(throw_an_exception=True).answer_question()
            Traceback (most recent call last):
            ...
            Exception: This is a test error
            
        Technical Notes:
            - Creates an anonymous subclass (InvigilatorExample) with a simplified implementation
            - Uses example() factory methods on other classes to create compatible components
            - The canned_response in the model provides predictable output for testing
            - The throw_exception parameter can be used to test error handling
        """
        from ..agents import Agent
        from ..scenarios import Scenario
        from ..surveys.memory import MemoryPlan
        from ..language_models import Model
        from ..surveys import Survey

        # Create a test model with predictable output
        model = Model("test", canned_response="SPAM!")

        # Configure the model to throw an exception if requested
        if throw_an_exception:
            model.throw_exception = True
            
        # Create or use the provided components
        agent = Agent.example()
        survey = survey or Survey.example()

        # Ensure the question is in the survey
        if question is not None and question not in survey.questions:
            survey.add_question(question)

        # Get or create the remaining required components
        question = question or survey.questions[0]
        scenario = scenario or Scenario.example()
        memory_plan = MemoryPlan(survey=survey)
        current_answers = None

        # Define a concrete implementation of the abstract class
        class InvigilatorExample(cls):
            """An example invigilator implementation for testing."""

            async def async_answer_question(self):
                """Implement the abstract method with simplified behavior."""
                return await self.model.async_execute_model_call(
                    user_prompt="Hello", system_prompt="Hi"
                )

        # Create and return the example invigilator
        return InvigilatorExample(
            agent=agent,
            question=question,
            scenario=scenario,
            survey=survey,
            model=model,
            memory_plan=memory_plan,
            current_answers=current_answers,
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
