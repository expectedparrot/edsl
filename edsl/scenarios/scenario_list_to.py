"""
Namespace class for ScenarioList conversion methods.

This module provides the `ScenarioListTo` class which is accessed via
the `.convert` property on ScenarioList instances, enabling a clean namespace
for conversion operations:

    sl.convert.agent_list()
    sl.convert.dataset()
    sl.convert.survey()

Created: 2026-01-08
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from ..agents import Agent, AgentList
    from ..dataset import Dataset
    from ..surveys import Survey
    from .scenario import Scenario
    from .scenario_list import ScenarioList


class ScenarioListTo:
    """Namespace for ScenarioList conversion methods.
    
    Access via the `.convert` property on ScenarioList:
    
        >>> sl = ScenarioList([Scenario({'age': 22, 'name': 'Alice'})])
        >>> al = sl.convert.agent_list()
        >>> ds = sl.convert.dataset()
    """
    
    def __init__(self, scenario_list: "ScenarioList"):
        self._sl = scenario_list
    
    def agent_list(self) -> "AgentList":
        """Convert the ScenarioList to an AgentList.

        This method supports special fields that map to Agent parameters:
        - "name": Will be used as the agent's name
        - "agent_parameters": A dictionary containing:
            - "instruction": The agent's instruction text
            - "name": The agent's name (overrides the "name" field if present)

        Example:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'age': 22, 'hair': 'brown', 'height': 5.5})])
            >>> al = s.convert.agent_list()
            >>> al
            AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])

            >>> s = ScenarioList([Scenario({'name': 'Alice', 'age': 22})])
            >>> al = s.convert.agent_list()
            >>> al[0].name
            'Alice'
        """
        from ..agents import AgentList
        return AgentList.from_scenario_list(self._sl)
    
    def agent_blueprint(
        self,
        *,
        seed: Optional[int] = None,
        cycle: bool = True,
        dimension_name_field: str = "dimension",
        dimension_values_field: str = "dimension_values",
        dimension_description_field: Optional[str] = None,
        dimension_probs_field: Optional[str] = None,
    ):
        """Create an AgentBlueprint from this ScenarioList.

        Args:
            seed: Optional seed for deterministic permutation order.
            cycle: Whether to continue cycling through permutations indefinitely.
            dimension_name_field: Field name to read the dimension name from.
            dimension_values_field: Field name to read the dimension values from.
            dimension_description_field: Optional field name for the dimension description.
            dimension_probs_field: Optional field name for probability weights.
        """
        from .agent_blueprint import AgentBlueprint
        return AgentBlueprint.from_scenario_list(
            self._sl,
            seed=seed,
            cycle=cycle,
            dimension_name_field=dimension_name_field,
            dimension_values_field=dimension_values_field,
            dimension_description_field=dimension_description_field,
            dimension_probs_field=dimension_probs_field,
        )
    
    def agent_traits(self, agent_name: Optional[str] = None) -> "Agent":
        """Convert all Scenario objects into traits of a single Agent.

        Aggregates each Scenario's key/value pairs into a single Agent's
        traits. If duplicate keys appear across scenarios, later occurrences
        are suffixed with an incrementing index (e.g., "key_1", "key_2").

        Args:
            agent_name: Optional custom agent name. Defaults to
                "Agent_from_{N}_scenarios" when not provided.

        Returns:
            Agent: An Agent instance whose traits include all fields from all scenarios.
        """
        from .scenario_list_transformer import ScenarioListTransformer
        return ScenarioListTransformer.to_agent_traits(self._sl, agent_name)
    
    def survey(self) -> "Survey":
        """Convert the ScenarioList to a Survey.
        
        Each Scenario should contain question data including:
        - question_type: The type of question (e.g., 'free_text', 'multiple_choice')
        - question_text: The question text
        - question_name: Optional name for the question
        - question_options: Options for multiple choice questions
        """
        from ..questions import QuestionBase
        from ..surveys import Survey

        s = Survey()
        for index, scenario in enumerate(self._sl):
            d = scenario.to_dict(add_edsl_version=False)
            if d.get("question_type") == "free_text":
                if "question_options" in d:
                    _ = d.pop("question_options")
            if "question_name" not in d or d["question_name"] is None:
                d["question_name"] = f"question_{index}"

            if d.get("question_type") is None:
                d["question_type"] = "free_text"
                d["question_options"] = None

            if "weight" in d:
                d["weight"] = float(d["weight"])

            question = QuestionBase.from_dict(d)
            s.add_question(question)

        return s
    
    def dataset(self) -> "Dataset":
        """Convert the ScenarioList to a Dataset.

        >>> s = ScenarioList.from_list("a", [1,2,3])
        >>> s.convert.dataset()
        Dataset([{'a': [1, 2, 3]}])
        """
        from ..dataset import Dataset

        if not self._sl.data:
            return Dataset([])

        keys = list(self._sl[0].keys())
        for scenario in self._sl:
            new_keys = list(scenario.keys())
            if new_keys != keys:
                keys = list(dict.fromkeys(keys + new_keys))
        data = [
            {key: [scenario.get(key, None) for scenario in self._sl.data]} 
            for key in keys
        ]
        return Dataset(data)
    
    def scenario_of_lists(self) -> "Scenario":
        """Collapse to a single Scenario with list-valued fields.

        For every key that appears anywhere in the list, creates a field whose
        value is the row-wise list of that key's values across the ScenarioList.

        Examples:
            >>> s = ScenarioList.from_list('a', [1, 2, 3])
            >>> s.convert.scenario_of_lists()
            Scenario({'a': [1, 2, 3]})
        """
        from .scenario_list_transformer import ScenarioListTransformer
        return ScenarioListTransformer.to_scenario_of_lists(self._sl)
    
    def key_value(self, field: str, value: Optional[str] = None) -> Union[dict, set]:
        """Return the set of values in the field, or a dict if value field specified.

        Args:
            field: The field to extract values from.
            value: An optional field to use as the value in the key-value pair.

        Example:
            >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
            >>> s.convert.key_value('name') == {'Alice', 'Bob'}
            True
        """
        if value is None:
            return {scenario[field] for scenario in self._sl}
        else:
            return {scenario[field]: scenario[value] for scenario in self._sl}
    
    def scenario_list(self) -> "ScenarioList":
        """Return a copy of this ScenarioList (identity conversion)."""
        return self._sl.duplicate()

