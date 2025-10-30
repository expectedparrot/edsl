"""PersonaGenerator class for creating agent personas.

The class is instantiated with an AgentList and a list of persona generation instructions.
The class then generates personas for the agents based on the instructions.
It returns an AgentList with the personas.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...agents import AgentList
    from ...results import Results
    from ...scenarios import ScenarioList

from ...questions import QuestionFreeText
from ...scenarios import Scenario, ScenarioList


def default_persona_instructions() -> "ScenarioList":
    """Return default persona instruction scenarios.

    Returns:
        ScenarioList with various persona generation strategies
    """
    return ScenarioList(
        [
            Scenario(
                {
                    "label": "nothing",
                    "instruction": "Write nothing.",
                }
            ),
            Scenario(
                {
                    "label": "generic_upwork_persona",
                    "instruction": "Write a persona for a general Upwork client.",
                }
            ),
            Scenario(
                {
                    "label": "demographics",
                    "instruction": "Write a one sentence, first persona persona for yourself focusing on basic demographic information.",
                }
            ),
            Scenario(
                {
                    "label": "freeform_persona",
                    "instruction": "Write a first persona persona for yourself.",
                }
            ),
            Scenario(
                {
                    "label": "causal_persona",
                    "instruction": """
Write a first person persona for yourself. 
The goal of this persona is that it could be used to answer other, unseen questions about yourself.
For this reason, it should be rich and detailed about causal explanations and reasons that would help explain behavior in future settings.

Follow these guidelines:
- Write in full sentences, not bullet points. 
- Break the persona into multiple paragraphs, with headings.
- It should be logically coherent and internally consistent. 
- Shorter is better, all else equal, but not expense of richness.        
- The persona should be psychologically-and economically realistic.
* For example, explanations should be interested in saving time or money; avoiding pain; don't like being bored, hungry, tired, etc.
- The persona should be theory-laden, not statement of facts.
* For example, explanations should be causally laden: I do (X) because of (Y)
""",
                }
            ),
        ]
    )


class PersonaGenerator:
    """Generate agent personas from survey results."""

    def __init__(
        self,
        agents: "AgentList",
        persona_instructions: Optional["ScenarioList"] = None,
        sample_size: Optional[int] = None,
    ):
        """Initialize with agents and persona generation instructions.

        Args:
            agents: AgentList containing agents with survey response traits
            persona_instructions: ScenarioList with persona generation instructions.
                                 If None, uses default instructions.
            sample_size: Number of agents to sample. If None, uses all agents.
        """
        self.agents = agents
        self.persona_instructions = (
            persona_instructions or default_persona_instructions()
        )
        self.sample_size = sample_size

    @classmethod
    def example(cls) -> "PersonaGenerator":
        """Return an example PersonaGenerator instance.

        Returns:
            PersonaGenerator instance with example data
        """
        from ...results import Results

        # Create minimal example results and extract agents
        results = Results.example()
        agents = results.agents
        return cls(agents=agents, sample_size=2)

    def generate_personas(
        self, instruction_indices: Optional[list] = None, verbose: bool = False
    ) -> "AgentList":
        """Generate personas for agents based on their survey responses.

        Args:
            instruction_indices: List of indices to select from persona_instructions.
                                If None, uses the first instruction only.
            verbose: Whether to print verbose output during generation

        Returns:
            AgentList with persona traits generated from the survey responses
        """
        # Select persona instructions
        if instruction_indices is None:
            selected_instructions = self.persona_instructions
        else:
            selected_instructions = ScenarioList(
                [self.persona_instructions[i] for i in instruction_indices]
            )

        # Sample agents if sample_size specified
        if self.sample_size is not None:
            agent_list = self.agents[: self.sample_size]
        else:
            agent_list = self.agents

        # Create persona generation question
        q = QuestionFreeText(
            question_name="persona",
            question_text="""{{ scenario.instruction }}""",
        )

        # Run persona generation
        jobs = q.by(agent_list).by(selected_instructions)
        new_results = jobs.run(verbose=verbose)

        # Return agent list with persona attributes
        return new_results.augmented_agents("persona")
