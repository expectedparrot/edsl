"""PersonaImprover class for generating improved persona candidates."""

import re
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from ...scenarios import Scenario, ScenarioList
    from ...agents import Agent, AgentList
    from ...comparisons import ResultPairComparison


from ...questions import QuestionYesNo, QuestionFreeText
from ...surveys import Survey


def sentences_to_lines(text):
    """Convert sentences in text to separate lines.
    
    Args:
        text: Input text with sentences
        
    Returns:
        Text with each sentence on a separate line
    """
    sentences = re.split(r"(?<=[.?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    return "\n".join(sentences)
import textwrap 

q_improve = QuestionFreeText(
    question_name="improvements",
    question_text=textwrap.dedent("""\
    An AI agent was asked to take a survey given to a real user. 
    The persona was supposed to represent the person in question. 
    This is the original persona:
    <original_persona>
    {{ scenario.original_persona }}
    <original_persona>

    This is run-down of the questions and answers that were not perfectly accurate:
    <delta_text>
    {{ scenario.delta_text }}
    <delta_text>

    Please suggest edits to the persona so that the agent's answers are more accurate.
    For each block, explain which questions you are referencing when suggestng the change. 
    Focus on questions were the agent's answer are very different in substance and 
    importance from the correct answers.

    Return response like so, creating as many blocks as needed:   
      
    <edit>
    Reference: ...
    Original text: ... 
    Replacement text: ... 
    </edit>

    <addition>
    New text to add:
    ...
    </addition>

    <deletion>
    Text to delete:
    ...
    </deletion>
    """),
)
q_new_persona = QuestionFreeText(
    question_name="new_persona",
    question_text="""
    This was the original persona:
    <original_persona>
    {{ scenario.original_persona }}
    <original_persona>

    This is the proposed edits:
    <improvements>
    {{ improvements.answer }}
    </improvements>

    Please apply the proposed edits to the original persona.
    Just return the new persona and no other text, comments or angle brackets.
    Whenever possible, make the persona more concise. 
    """,
)

survey = Survey([q_improve, q_new_persona])


class AgentPersonaImprover:
    """Class to generate improved persona candidates from comparison results."""

    def __init__(self, 
    result_pair_comparisons: List['ResultPairComparison'], 
    improvement_survey: Optional[Survey] = None,
    agent_trait_field: str = "persona",
    ):
        """Initialize with the survey used to generate improved personas.

        Args:
            improvement_survey: Survey containing questions to analyze differences
                              and generate improved persona text
        """
        if improvement_survey is None:
            improvement_survey = survey
        self.improvement_survey = improvement_survey
        self.result_pair_comparisons = result_pair_comparisons

        for comparison in self.result_pair_comparisons:
            agent = comparison.result_A.agent
            if agent_trait_field not in agent.traits:
                raise ValueError(f"Agent {agent.name} does not have a {agent_trait_field} trait")

        self._new_agent_list = None

    @property
    def new_agent_list(self) -> List[str]:
        """Return the new personas for the result pair comparisons."""
        if self._new_agent_list is None:
            self._new_agent_list = self._generate_new_agent_list()
        return self._new_agent_list

    @classmethod
    def example(cls) -> 'AgentPersonaImprover':
        """Return an example PersonaImprover instance with a Yes/No question.

        Returns:
            PersonaImprover instance with a survey asking if favorite color is Green
        """
        from .. import ResultPairComparison
        # q = QuestionYesNo(
        #     question_name="favorite_color_green",
        #     question_text="Is your favorite color Green?"
        # )
        # #survey = Survey(questions=[q])
        rc1 = ResultPairComparison.example(first_index=0, second_index=2)
        rc2 = ResultPairComparison.example(first_index=1, second_index=2)
        rc1.result_A.agent.traits["persona"] = "I am a friendly person who likes to help others."
        rc2.result_A.agent.traits["persona"] = "I am a disagreeable person who likes to harm others."
        rc1.result_A.agent.name = "Agent 1"
        rc2.result_A.agent.name = "Agent 2"
        return cls(result_pair_comparisons=[rc1, rc2])

    def _generate_scenario(self, comparison: 'ResultPairComparison') -> 'Scenario':
        """Generate a scenario from the comparison for persona improvement.

        Args:
            comparison: ResultPairComparison containing the current agent and comparison data

        Returns:
            Scenario with original_persona and delta_text for improvement survey
        """
        from ...scenarios import Scenario
        
        current_agent = comparison.result_A.agent
        original_persona = sentences_to_lines(current_agent.persona)
        from ...comparisons import ResultDifferences
        delta_text = ResultDifferences(comparison).generate_report()
        return Scenario(original_persona=original_persona, delta_text=delta_text)

    def _generate_new_agent_list(self) -> 'AgentList':
        """Generate multiple candidate agents with improved personas in parallel.

        Args:
            comparisons: List of ResultPairComparison objects to process

        Returns:
            AgentList containing agents with improved persona traits
        """
        from ...agents import Agent, AgentList
        from ...scenarios import ScenarioList
        
        # Create a ScenarioList from all comparisons
        scenario_list = ScenarioList([self._generate_scenario(comp) for comp in self.result_pair_comparisons])
        
        # Run improvement survey in parallel for all scenarios
        improve_results = self.improvement_survey.by(scenario_list).run()
        # Extract new personas as a list
        new_personas = improve_results.select("new_persona").to_list()
        
        # Create new agents with improved personas
        candidate_agents = []
        for i, comparison in enumerate(self.result_pair_comparisons):
            current_agent = comparison.result_A.agent
            candidate_agent = Agent(
                name=current_agent.name,
                traits={"persona": new_personas[i]},
            )
            candidate_agents.append(candidate_agent)
        
        return AgentList(candidate_agents)


if __name__ == "__main__":
    improver = AgentPersonaImprover.example()
    print(improver.new_agent_list)