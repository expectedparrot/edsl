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

        Example:
            Access through Results instance: results.columns
            Returns: ['agent.agent_index', ...]
        """
        return self._results._cache_manager.columns

    @property
    def answer_keys(self) -> dict[str, str]:
        """Return a mapping of answer keys to question text.

        Example:
            Access through Results instance: results.answer_keys
            Returns: {'how_feeling': 'How are you this {{ period }}?', ...}
        """
        from ..utilities.utilities import shorten_string

        if not self._results.survey:
            raise ResultsError("Survey is not defined so no answer keys are available.")

        answer_keys = self._results._cache_manager.data_type_to_keys["answer"]
        answer_keys = {k for k in answer_keys if "_comment" not in k}
        questions_text = [
            self._results.survey._get_question_by_name(k).question_text for k in answer_keys
        ]
        short_question_text = [shorten_string(q, 80) for q in questions_text]
        initial_dict = dict(zip(answer_keys, short_question_text))
        sorted_dict = {key: initial_dict[key] for key in sorted(initial_dict)}
        return sorted_dict

    @property
    def agents(self) -> "AgentList":
        """Return a list of all of the agents in the Results.

        Example:
            Access through Results instance: results.agents
            Returns: AgentList([Agent(traits = {'status': 'Joyful'}), ...])
        """
        from ..agents import AgentList

        return AgentList([r.agent for r in self._results.data])

    @property
    def models(self) -> "ModelList":
        """Return a list of all of the models in the Results.

        Example:
            Access through Results instance: results.models
            Returns: ModelList([Model(model_name = ...), ...])
        """
        from ..language_models import ModelList

        return ModelList([r.model for r in self._results.data])

    @property
    def scenarios(self) -> "ScenarioList":
        """Return a list of all of the scenarios in the Results.

        Example:
            Access through Results instance: results.scenarios
            Returns: ScenarioList([Scenario({'period': 'morning'}), ...])
        """
        from ..scenarios import ScenarioList

        return ScenarioList([r.scenario for r in self._results.data])

    @property
    def agent_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Agent data.

        Example:
            Access through Results instance: results.agent_keys
            Returns: ['agent_index', 'agent_instruction', 'agent_name', 'status']
        """
        return sorted(self._results._cache_manager.data_type_to_keys["agent"])

    @property
    def model_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the LanguageModel data.

        Example:
            Access through Results instance: results.model_keys
            Returns: ['frequency_penalty', 'inference_service', 'logprobs', ...]
        """
        return sorted(self._results._cache_manager.data_type_to_keys["model"])

    @property
    def scenario_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Scenario data.

        Example:
            Access through Results instance: results.scenario_keys
            Returns: ['period', 'scenario_index']
        """
        return sorted(self._results._cache_manager.data_type_to_keys["scenario"])

    @property
    def question_names(self) -> list[str]:
        """Return a list of all of the question names.

        Example:
            Access through Results instance: results.question_names
            Returns: ['how_feeling', 'how_feeling_yesterday']
        """
        if self._results.survey is None:
            return []
        return sorted(list(self._results.survey.question_names))

    @property
    def all_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Results.

        Example:
            Access through Results instance: results.all_keys
            Returns: ['agent_index', ...]
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

    @property
    def shelf_keys(self) -> set:
        """Return a copy of the set of shelved result keys.
        
        This property delegates to the ResultsSerializer class.
        """
        from .results_serializer import ResultsSerializer
        
        serializer = ResultsSerializer(self._results)
        return serializer.shelf_keys 