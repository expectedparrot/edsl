"""PersonaGenerationEvaluator class for end-to-end persona generation and evaluation."""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...results import Results
    from ...surveys import Survey
    from ...scenarios import ScenarioList
    from ..compare_results_to_gold import CompareResultsToGold

from .persona_generator import PersonaGenerator


class PersonaGenerationEvaluator:
    """End-to-end persona generation and evaluation against gold standard results."""

    def __init__(
        self,
        train_agents: "AgentList",
        gold_results: "Results",
        evaluation_survey: "Survey",
        sample_size: Optional[int] = None,
        persona_instructions: Optional["ScenarioList"] = None,
        instruction_indices: Optional[list] = None,
    ):
        """Initialize with training agents, gold standard results and evaluation survey.

        Args:
            train_agents: AgentList with training data to generate personas from
            gold_results: Gold standard Results object to compare against
            evaluation_survey: Survey to run with generated personas for evaluation
            sample_size: Number of agents to sample from train_agents. If None, uses all.
            persona_instructions: ScenarioList with persona generation instructions.
                                 If None, uses default instructions.
            instruction_indices: List of indices to select from persona_instructions.
                                If None, uses the first instruction only.
        """
        self.train_agents = train_agents
        self.gold_results = gold_results
        self.evaluation_survey = evaluation_survey
        self.sample_size = sample_size
        self.persona_instructions = persona_instructions
        self.instruction_indices = instruction_indices

    @classmethod
    def example(cls) -> "PersonaGenerationEvaluator":
        """Return an example PersonaGenerationEvaluator instance.

        Returns:
            PersonaGenerationEvaluator instance with example data
        """
        from ...results import Results
        from ...surveys import Survey

        results = Results.example()
        survey = Survey.example()
        return cls(
            train_agents=results.agents,
            gold_results=results,
            evaluation_survey=survey,
            sample_size=2,
        )

    def evaluate(self, verbose: bool = False) -> "CompareResultsToGold":
        """Generate personas and evaluate them against gold standard.

        Args:
            verbose: Whether to print verbose output during generation

        Returns:
            CompareResultsToGold object with evaluation results
        """
        from ..compare_results_to_gold import CompareResultsToGold

        # Generate personas from training agents
        persona_gen = PersonaGenerator(
            agents=self.train_agents,
            sample_size=self.sample_size,
            persona_instructions=self.persona_instructions,
        )

        agent_list = persona_gen.generate_personas(
            instruction_indices=self.instruction_indices, verbose=verbose
        )

        # Run evaluation survey with generated personas
        evaluation_results = self.evaluation_survey.by(agent_list).run(verbose=verbose)

        # Extract scenario names from persona instructions
        if self.instruction_indices is None:
            selected_instructions = persona_gen.persona_instructions[:1]
        else:
            selected_instructions = [
                persona_gen.persona_instructions[i] for i in self.instruction_indices
            ]

        scenario_names = {
            k: instr.get("label", f"instruction_{k}")
            for k, instr in enumerate(selected_instructions)
        }

        # Create and return comparison object
        return CompareResultsToGold(
            evaluation_results,
            self.gold_results,
            scenario_names=scenario_names,
        )
