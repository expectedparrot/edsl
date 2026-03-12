"""ResultsProperties module for handling all property methods of Results objects.

This module contains the ResultsProperties class which provides access to various
metadata and derived collections from Results data, including agents, models,
scenarios, keys, and other properties.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents import AgentList
    from ..scenarios import ScenarioList
    from ..language_models import ModelList
    from ..results import Results

from .exceptions import ResultsError


class ResultsProperties:
    """Handles all property methods for Results objects.

    This class provides access to various metadata and derived collections
    from Results data, including agents, models, scenarios, column information,
    and other properties.
    """

    def __init__(self, results: "Results"):
        """Initialize the ResultsProperties with a reference to the Results object.

        Args:
            results: The Results object to provide properties for
        """
        self._results = results

    @property
    def columns(self) -> list[str]:
        """Return a list of all of the columns that are in the Results.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> r.columns
            ['agent.agent_index', ...]
        """
        return self._results._cache_manager.columns

    @property
    def answer_keys(self) -> dict[str, str]:
        """Return a mapping of answer keys to question text.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> r.answer_keys
            {'how_feeling': 'How are you this {{ period }}?', 'how_feeling_yesterday': 'How were you feeling yesterday {{ period }}?'}
        """
        from ..utilities.utilities import shorten_string

        if not self._results.survey:
            raise ResultsError("Survey is not defined so no answer keys are available.")

        answer_keys = self._results._cache_manager.data_type_to_keys["answer"]
        answer_keys = {k for k in answer_keys if "_comment" not in k}
        questions_text = [
            self._results.survey._get_question_by_name(k).question_text
            for k in answer_keys
        ]
        short_question_text = [shorten_string(q, 80) for q in questions_text]
        initial_dict = dict(zip(answer_keys, short_question_text))
        sorted_dict = {key: initial_dict[key] for key in sorted(initial_dict)}
        return sorted_dict

    @property
    def agents(self) -> "AgentList":
        """Return a list of all of the agents in the Results.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> r.agents
            AgentList([Agent(traits = {'status': 'Joyful'}), Agent(traits = {'status': 'Joyful'}), Agent(traits = {'status': 'Sad'}), Agent(traits = {'status': 'Sad'})])
        """
        from ..agents import AgentList

        return AgentList([r.agent for r in self._results.data])

    @property
    def models(self) -> "ModelList":
        """Return a list of all of the models in the Results.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> r.models[0]
            Model(...)
        """
        from ..language_models import ModelList

        return ModelList([r.model for r in self._results.data])

    @property
    def scenarios(self) -> "ScenarioList":
        """Return a list of all of the scenarios in the Results.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> r.scenarios
            ScenarioList([Scenario({'period': 'morning'}), Scenario({'period': 'afternoon'}), Scenario({'period': 'morning'}), Scenario({'period': 'afternoon'})])
        """
        from ..scenarios import ScenarioList

        return ScenarioList([r.scenario for r in self._results.data])

    @property
    def agent_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Agent data.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> r.agent_keys
            ['agent_index', 'agent_instruction', 'agent_name', 'status']
        """
        return sorted(self._results._cache_manager.data_type_to_keys["agent"])

    @property
    def model_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the LanguageModel data.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> r.model_keys
            ['canned_response', 'inference_service', 'model', 'model_index', 'temperature']
        """
        return sorted(self._results._cache_manager.data_type_to_keys["model"])

    @property
    def scenario_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Scenario data.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> r.scenario_keys
            ['period', 'scenario_index']
        """
        return sorted(self._results._cache_manager.data_type_to_keys["scenario"])

    @property
    def question_names(self) -> list[str]:
        """Return a list of all of the question names.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> r.question_names
            ['how_feeling', 'how_feeling_yesterday']
        """
        if self._results.survey is None:
            return []
        return sorted(list(self._results.survey.question_names))

    @property
    def all_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Results.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> r.all_keys
            ['agent_index', ...]
        """
        answer_keys = set(self.answer_keys)
        all_keys = (
            answer_keys.union(self.agent_keys)
            .union(self.scenario_keys)
            .union(self.model_keys)
        )
        return sorted(list(all_keys))

    @property
    def has_unfixed_exceptions(self) -> bool:
        """Return whether the results have unfixed exceptions."""
        return self._results.task_history.has_unfixed_exceptions

    @property
    def hashes(self) -> set:
        """Return a set of hashes for all result objects."""
        return set(hash(result) for result in self._results.data)

