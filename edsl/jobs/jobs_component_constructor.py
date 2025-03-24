from typing import Union, Sequence, TYPE_CHECKING
from .exceptions import JobsValueError

if TYPE_CHECKING:
    from ..agents import Agent
    from ..language_models import LanguageModel
    from ..scenarios import Scenario
    from .jobs import Jobs

class JobsComponentConstructor:
    "Handles the creation of Agents, Scenarios, and LanguageModels in a job."

    def __init__(self, jobs: "Jobs"):
        self.jobs = jobs

    def by(
        self,
        *args: Union[
            "Agent",
            "Scenario",
            "LanguageModel",
            Sequence[Union["Agent", "Scenario", "LanguageModel"]],
        ],
    ) -> "Jobs":
        """
        Add Agents, Scenarios and LanguageModels to a job.

        :param args: objects or a sequence (list, tuple, ...) of objects of the same type

        If no objects of this type exist in the Jobs instance, it stores the new objects as a list in the corresponding attribute.
        Otherwise, it combines the new objects with existing objects using the object's `__add__` method.

        This 'by' is intended to create a fluent interface.

        >>> from edsl.surveys import Survey
        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText(question_name="name", question_text="What is your name?")
        >>> from edsl.jobs import Jobs
        >>> j = Jobs(survey = Survey(questions=[q]))
        >>> j
        Jobs(survey=Survey(...), agents=AgentList([]), models=ModelList([]), scenarios=ScenarioList([]))
        >>> from edsl import Agent; a = Agent(traits = {"status": "Sad"})
        >>> j.by(a).agents
        AgentList([Agent(traits = {'status': 'Sad'})])


        Notes:
        - all objects must implement the 'get_value', 'set_value', and `__add__` methods
        - agents: traits of new agents are combined with traits of existing agents. New and existing agents should not have overlapping traits, and do not increase the # agents in the instance
        - scenarios: traits of new scenarios are combined with traits of old existing. New scenarios will overwrite overlapping traits, and do not increase the number of scenarios in the instance
        - models: new models overwrite old models.
        """
        
        from ..dataset.dataset import Dataset

        if isinstance(
            args[0], Dataset
        ):  # let the user use a Dataset as if it were a ScenarioList
            args = args[0].to_scenario_list()

        passed_objects = self._turn_args_to_list(
            args
        )  # objects can also be passed comma-separated

        current_objects, objects_key = self._get_current_objects_of_this_type(
            passed_objects[0]
        )

        if not current_objects:
            new_objects = passed_objects
        else:
            new_objects = self._merge_objects(passed_objects, current_objects)

        setattr(self.jobs, objects_key, new_objects)  # update the job object
        return self.jobs

    @staticmethod
    def _turn_args_to_list(args):
        """Return a list of the first argument if it is a sequence, otherwise returns a list of all the arguments.

        Example:

        >>> JobsComponentConstructor._turn_args_to_list([1,2,3])
        [1, 2, 3]

        """

        def did_user_pass_a_sequence(args):
            """Return True if the user passed a sequence, False otherwise.

            Example:

            >>> did_user_pass_a_sequence([1,2,3])
            True

            >>> did_user_pass_a_sequence(1)
            False
            """
            return len(args) == 1 and isinstance(args[0], Sequence)

        if did_user_pass_a_sequence(args):
            container_class = JobsComponentConstructor._get_container_class(args[0][0])
            return container_class(args[0])
        else:
            container_class = JobsComponentConstructor._get_container_class(args[0])
            return container_class(args)

    def _get_current_objects_of_this_type(
        self, object: Union["Agent", "Scenario", "LanguageModel"]
    ) -> tuple[list, str]:
        
        from ..agents import Agent
        from ..scenarios import Scenario
        from ..language_models import LanguageModel

        """Return the current objects of the same type as the first argument.

        >>> from edsl.jobs import Jobs
        >>> j = JobsComponentConstructor(Jobs.example())
        >>> j._get_current_objects_of_this_type(j.agents[0])
        (AgentList([Agent(traits = {'status': 'Joyful'}), Agent(traits = {'status': 'Sad'})]), 'agents')
        """
        class_to_key = {
            Agent: "agents",
            Scenario: "scenarios",
            LanguageModel: "models",
        }
        for class_type in class_to_key:
            if isinstance(object, class_type) or issubclass(
                object.__class__, class_type
            ):
                key = class_to_key[class_type]
                break
        else:
            raise JobsValueError(
                f"First argument must be an Agent, Scenario, or LanguageModel, not {object}"
            )
        current_objects = getattr(self.jobs, key, None)
        return current_objects, key

    @staticmethod
    def _get_empty_container_object(object):
        from ..agents import AgentList
        from ..scenarios import ScenarioList

        return {"Agent": AgentList([]), "Scenario": ScenarioList([])}.get(
            object.__class__.__name__, []
        )

    @staticmethod
    def _merge_objects(passed_objects, current_objects) -> list:
        """
        Combine all the existing objects with the new objects.

        For example, if the user passes in 3 agents,
        and there are 2 existing agents, this will create 6 new agents
        >>> from edsl.jobs import Jobs
        >>> from edsl.surveys import Survey
        >>> JobsComponentConstructor(Jobs(survey = Survey.example()))._merge_objects([1,2,3], [4,5,6])
        [5, 6, 7, 6, 7, 8, 7, 8, 9]
        """
        new_objects = JobsComponentConstructor._get_empty_container_object(
            passed_objects[0]
        )
        for current_object in current_objects:
            for new_object in passed_objects:
                new_objects.append(current_object + new_object)
        return new_objects

    @staticmethod
    def _get_container_class(object):
        from ..agents import AgentList
        from ..agents import Agent
        from ..scenarios import Scenario
        from ..scenarios import ScenarioList
        from ..language_models import ModelList

        if isinstance(object, Agent):
            return AgentList
        elif isinstance(object, Scenario):
            return ScenarioList
        elif isinstance(object, ModelList):
            return ModelList
        else:
            return list


if __name__ == "__main__":
    """Run the module's doctests."""
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
