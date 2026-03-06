"""Agent augmentation functionality for Results objects."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..results import Results
    from ...agents import AgentList


class ResultsAugmenter:
    """Augments agents from a Results object by adding answer fields as traits.

    Instantiated with a Results object. Provides the ``augmented_agents``
    method that was previously on the Results class.

    Examples:
        >>> from edsl.results.extras import ResultsAugmenter
        >>> from edsl.results import Results
        >>> augmenter = ResultsAugmenter(Results.example())
    """

    def __init__(self, results: "Results") -> None:
        self._results = results

    def augmented_agents(
        self,
        *fields: str,
        include_existing_traits: bool = False,
        include_codebook: bool = False,
    ) -> "AgentList":
        """Augment the agent list by adding specified fields as new traits.

        Takes field names (similar to the select method) and adds them as new traits
        to the agents in the agent list. This only works when there is a one-to-one
        mapping between agents and results.

        Args:
            *fields: Field names to add as traits. Field identifiers follow the same
                rules as ``select`` -- they can be specified either as fully-qualified
                names (e.g. ``"answer.how_feeling"``) or by bare attribute name when
                unambiguous.
            include_existing_traits: If True, keep the agent's existing traits in
                addition to the new ones. Defaults to False.
            include_codebook: If True, keep the agent's codebook and
                traits_presentation_template. Defaults to False.

        Returns:
            AgentList: A new AgentList with the specified fields added as traits.

        Raises:
            ResultsError: If no fields are provided.

        Examples:
            >>> from edsl import QuestionFreeText, Agent, Survey
            >>> from edsl.language_models import LanguageModel
            >>> q1 = QuestionFreeText(question_name="color", question_text="What is your favorite color?")
            >>> q2 = QuestionFreeText(question_name="food", question_text="What is your favorite food?")
            >>> survey = Survey([q1, q2])
            >>> agents = [Agent(name="Alice"), Agent(name="Bob")]
            >>> m = LanguageModel.example(test_model=True, canned_response="Blue")
            >>> results = survey.by(agents).by(m).run(disable_remote_inference=True)
            >>> from edsl.results.extras import ResultsAugmenter
            >>> augmenter = ResultsAugmenter(results)
            >>> augmented = augmenter.augmented_agents("color", "food")
            >>> len(augmented) == len(agents)
            True
        """
        from ..results import ResultsError
        from ...agents import AgentList

        results = self._results

        if not fields:
            raise ResultsError("At least one field must be specified for augmentation.")

        al = AgentList()
        for result in results.data:
            agent = result.get("agent")
            new_agent = agent.copy()
            naming_dict = {"name": new_agent.name}
            if not include_existing_traits:
                new_agent.traits = {}
            if not include_codebook:
                new_agent.codebook = {}
                new_agent.traits_presentation_template = "Your traits: {{traits}}"
            naming_dict["scenario_index"] = result.sub_dicts["scenario"][
                "scenario_index"
            ]
            naming_dict["model_index"] = result.sub_dicts["model"]["model_index"]
            new_agent.traits = {
                k: v for k, v in result.sub_dicts["answer"].items() if k in fields
            }
            new_agent.name = repr(naming_dict)
            al.append(new_agent)
        return al
